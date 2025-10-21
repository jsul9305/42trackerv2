# crawler/engine.py
"""크롤링 엔진 - 메인 루프 및 작업 조정"""

import time
import random
import urllib.parse
import threading
from queue import Queue
from datetime import datetime
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any, Optional

from bs4 import BeautifulSoup

from core.database import get_db, init_database, migrate_database
from crawler.fetcher import fetch_cached
from crawler.worker import get_mr_worker
from parsers.utils import parse
from parsers.myresult import MyResultParser, extract_total_net_time
from utils.time_utils import first_time, looks_time
from utils.file_utils import save_certificate_to_disk
from config.settings import CRAWLER_MAX_WORKERS


class CrawlerEngine:
    """
    크롤링 엔진
    
    주요 기능:
    - 활성화된 대회별로 주기적 크롤링
    - 참가자 스플릿 데이터 수집
    - 기록증 이미지 다운로드
    - 배치 업데이트로 DB 부하 최소화
    """
    
    def __init__(self, use_adaptive_scheduler: bool = False):
        """
        Args:
            use_adaptive_scheduler: True면 적응형 스케줄러 사용 (실패 시 백오프)
        """
        # 스케줄러 (실행 주기 관리)
        from crawler.scheduler import CrawlerScheduler, AdaptiveScheduler
        
        if use_adaptive_scheduler:
            self.scheduler = AdaptiveScheduler()
            print("[Engine] Using AdaptiveScheduler (with backoff)")
        else:
            self.scheduler = CrawlerScheduler()
            print("[Engine] Using CrawlerScheduler (basic)")
        
        # 이미지 다운로드 큐
        self.image_queue: Queue = Queue()
        self.image_workers: List[threading.Thread] = []
        
        # 실행 상태
        self.running = False
    
    # ============= 메인 루프 =============
    
    def run(self):
        """크롤러 메인 루프 시작"""
        print("[Engine] Initializing...")
        init_database()
        migrate_database()
        
        print("[Engine] Starting image workers...")
        self._start_image_workers(num_workers=3)
        
        print(f"[Engine] Starting main loop (workers={CRAWLER_MAX_WORKERS})...")
        self.running = True
        
        try:
            self._main_loop()
        except KeyboardInterrupt:
            print("\n[Engine] Shutting down...")
            self.shutdown()
    
    def shutdown(self):
        """크롤러 종료"""
        self.running = False
        
        # 이미지 워커 종료
        for _ in self.image_workers:
            self.image_queue.put(None)
        
        for worker in self.image_workers:
            worker.join(timeout=5)
        
        print("[Engine] Shutdown complete")
    
    def _main_loop(self):
        """메인 크롤링 루프"""
        while self.running:
            tick = time.time()
            
            try:
                # 활성화된 대회 조회
                with get_db() as conn:
                    marathons = conn.execute(
                        "SELECT * FROM marathons WHERE enabled=1"
                    ).fetchall()
                
                # 각 대회 처리
                for marathon in marathons:
                    self._process_marathon(marathon)
                
            except Exception as e:
                print(f"[fatal] {type(e).__name__}: {e}")
            
            # 짧은 대기 (CPU 부하 감소)
            time.sleep(0.1)
    
    # ============= 대회별 처리 =============
    
    def _process_marathon(self, marathon):
        """특정 대회 크롤링 처리"""
        mid = marathon["id"]
        refresh_sec = int(marathon["refresh_sec"] or 60)
        
        # ✅ 스케줄러로 실행 가능 여부 확인
        if not self.scheduler.should_run_marathon(mid, refresh_sec):
            return
        
        tick = time.time()
        
        try:
            # 참가자 조회
            with get_db() as conn:
                participants = conn.execute(
                    "SELECT * FROM participants WHERE marathon_id=? AND active=1",
                    (mid,)
                ).fetchall()
            
            if not participants:
                # ✅ 참가자 없어도 실행 기록 (다음 주기까지 대기)
                self.scheduler.mark_marathon_run(mid)
                return
            
            # 크롤링 실행
            results = self._crawl_participants(marathon, participants)
            
            # DB 업데이트
            self._save_results(results, marathon)
            
            duration = round(time.time() - tick, 2)
            print(f"[ok] mid={mid} participants={len(participants)} dur={duration}s")
            
            # ✅ 성공 기록 (AdaptiveScheduler면 백오프 리셋)
            if hasattr(self.scheduler, 'record_success'):
                self.scheduler.record_success(mid)
            else:
                self.scheduler.mark_marathon_run(mid)
        
        except Exception as e:
            print(f"[err] mid={mid} -> {type(e).__name__}: {e}")
            
            # ✅ 실패 기록 (AdaptiveScheduler면 백오프 증가)
            if hasattr(self.scheduler, 'record_failure'):
                self.scheduler.record_failure(mid)
                backoff = self.scheduler.get_backoff_time(mid, refresh_sec)
                print(f"[backoff] mid={mid} next try in {backoff:.0f}s")
            else:
                self.scheduler.mark_marathon_run(mid)
    
    # ============= 참가자 크롤링 =============
    
    def _crawl_participants(
        self,
        marathon,
        participants: List
    ) -> List[Tuple]:
        """
        참가자들의 데이터 크롤링
        
        Returns:
            [(participant_id, splits, meta, assets), ...]
        """
        url_template = marathon["url_template"]
        usedata = marathon["usedata"] or ""
        
        results = []
        futures = []
        myresult_jobs = []
        
        # 작업 분배
        with ThreadPoolExecutor(max_workers=CRAWLER_MAX_WORKERS) as executor:
            for p in participants:
                pid = p["id"]
                
                # ✅ 스케줄러로 페치 가능 여부 확인 (rate limiting)
                if not self.scheduler.can_fetch_participant(pid):
                    continue
                
                # ✅ 페치 시작 기록
                self.scheduler.mark_participant_fetch(pid)
                
                # URL 생성
                url = self._build_url(url_template, p["nameorbibno"], usedata)
                host = (urllib.parse.urlsplit(url).hostname or "").lower()
                
                # MyResult는 직렬 처리 (워커 안정성)
                if "myresult.co.kr" in host:
                    myresult_jobs.append((pid, url, p["nameorbibno"], usedata))
                else:
                    # 나머지는 병렬 처리
                    future = executor.submit(
                        self._crawl_one,
                        pid, url, p["nameorbibno"], usedata
                    )
                    futures.append(future)
            
            # 병렬 작업 결과 수집
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result and isinstance(result, tuple):
                        results.append(result)
                except Exception as e:
                    print(f"[err] thread -> {type(e).__name__}: {e}")
        
        # MyResult 직렬 처리
        for pid, url, bib, usedata in myresult_jobs:
            try:
                result = self._crawl_one(pid, url, bib, usedata)
                if result and isinstance(result, tuple):
                    results.append(result)
            except Exception as e:
                print(f"[err] myresult -> {type(e).__name__}: {e}")
        
        return results
    
    def _crawl_one(
        self,
        pid: int,
        url: str,
        bib: Optional[str] = None,
        usedata: Optional[str] = None
    ) -> Tuple[int, List, Dict, List]:
        """
        단일 참가자 크롤링
        
        Returns:
            (participant_id, splits, meta, assets)
        """
        # HTML 페칭 (캐시 사용)
        html = fetch_cached(url)
        host = urllib.parse.urlsplit(url).hostname or ""
        
        # 파싱
        data = parse(html, host=host, url=url, usedata=usedata, bib=bib) or {}
        
        # MyResult JSON 특별 처리
        if isinstance(html, str) and html.startswith("JSON::"):
            data = self._handle_myresult_json(html, url, host, data) or data
        
        # 결과 추출
        splits = data.get("splits", []) or []
        meta = {
            "race_label": data.get("race_label"),
            "race_total_km": data.get("race_total_km")
        }
        assets = data.get("assets", []) or []
        
        return (pid, splits, meta, assets)
    
    def _handle_myresult_json(
        self,
        html: str,
        url: str,
        host: str,
        data: Dict
    ) -> Dict:
        """
        MyResult JSON 특별 처리
        
        JSON에 Finish가 없으면 HTML에서 추출하여 보강
        """
        if "myresult.co.kr" not in host.lower():
            return data
        
        # Finish 행 있는지 확인
        has_finish = any(
            (r.get("point_label") or "").lower() == "finish"
            for r in data.get("splits", [])
        )
        
        if has_finish:
            return data
        
        # HTML에서 Finish 정보 추출
        try:
            html2 = get_mr_worker().fetch(url, timeout=10) or ""
            if not html2 or html2.startswith("JSON::"):
                return data
            
            soup = BeautifulSoup(html2, "html.parser")
            
            # 대회 총 기록
            total = extract_total_net_time(soup)
            
            # 도착 시각
            finish_clock = ""
            for row in soup.select(".table-row.ant-row"):
                cols = row.select(".ant-col")
                if len(cols) >= 4 and "도착" in cols[0].get_text(" ", strip=True):
                    finish_clock = first_time(cols[1].get_text(" ", strip=True))
                    break
            
            # Finish 행 추가
            if looks_time(total):
                data.setdefault("splits", []).append({
                    "point_label": "Finish",
                    "point_km": None,
                    "net_time": total,
                    "pass_clock": finish_clock,
                    "pace": "",
                })
        
        except Exception:
            pass  # 실패해도 기존 데이터 유지
        
        return data
    
    # ============= URL 생성 =============
    
    def _build_url(
        self,
        template: str,
        nameorbibno: str,
        usedata: str
    ) -> str:
        """
        URL 템플릿에서 실제 URL 생성
        
        지원 플레이스홀더:
        - {nameorbibno}: 참가번호/이름
        - {usedata}: 대회 ID
        - {bib_spct6}: SPCT 6자리 제로패딩
        """
        url = template.replace("{nameorbibno}", nameorbibno)
        url = url.replace("{usedata}", usedata or "")
        
        # SPCT 6자리 제로패딩 지원
        if "{bib_spct6}" in url:
            bib6 = nameorbibno.zfill(6) if nameorbibno.isdigit() else nameorbibno
            url = url.replace("{bib_spct6}", bib6)
        
        return url
    
    # ============= DB 저장 =============
    
    def _save_results(self, results: List[Tuple], marathon):
        """
        크롤링 결과를 DB에 배치 저장
        
        배치 업데이트로 성능 최적화
        """
        if not results:
            return
        
        now_iso = datetime.now().isoformat()
        
        # 배치 데이터 준비
        split_batch = []
        meta_batch = []
        asset_batch = []
        
        for r in results:
            if not r:
                continue
            
            # 결과 언팩
            if isinstance(r, tuple):
                if len(r) == 4:
                    pid, splits, meta, assets = r
                elif len(r) == 3:
                    pid, splits, meta = r
                    assets = []
                else:
                    pid, splits = r
                    meta, assets = {}, []
            else:
                continue
            
            # 메타 데이터
            if meta:
                meta_batch.append((
                    meta.get("race_label"),
                    meta.get("race_total_km"),
                    pid
                ))
            
            # 스플릿 데이터
            for s in splits or []:
                split_batch.append((
                    pid,
                    s.get("point_label"),
                    s.get("point_km"),
                    s.get("net_time"),
                    s.get("pass_clock"),
                    s.get("pace"),
                    now_iso
                ))
            
            # 에셋 데이터
            for a in assets:
                if a.get("url"):
                    asset_batch.append((
                        pid,
                        a.get("kind") or "certificate",
                        a.get("host"),
                        a.get("url"),
                        None,
                        now_iso
                    ))
        
        # 배치 저장
        with get_db() as conn:
            # 메타 데이터 업데이트
            if meta_batch:
                conn.executemany(
                    """UPDATE participants
                       SET race_label = COALESCE(?, race_label),
                           race_total_km = COALESCE(?, race_total_km)
                       WHERE id = ?""",
                    meta_batch
                )
            
            # 스플릿 데이터 upsert
            if split_batch:
                conn.executemany(
                    """INSERT INTO splits(participant_id, point_label, point_km, 
                                          net_time, pass_clock, pace, seen_at)
                       VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(participant_id, point_label)
                       DO UPDATE SET net_time=excluded.net_time,
                                     pass_clock=excluded.pass_clock,
                                     pace=excluded.pace,
                                     seen_at=excluded.seen_at""",
                    split_batch
                )
            
            # 에셋 데이터 upsert
            if asset_batch:
                conn.executemany(
                    """INSERT INTO assets(participant_id, kind, host, url, 
                                          local_path, seen_at)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(participant_id, kind)
                       DO UPDATE SET url=excluded.url,
                                     host=excluded.host,
                                     seen_at=excluded.seen_at""",
                    asset_batch
                )
            
            conn.commit()
    
    # ============= 이미지 다운로드 워커 =============
    
    def _start_image_workers(self, num_workers: int = 3):
        """이미지 다운로드 워커 시작"""
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._image_worker,
                daemon=True,
                name=f"ImageWorker-{i+1}"
            )
            worker.start()
            self.image_workers.append(worker)
    
    def _image_worker(self):
        """이미지 다운로드 워커 (백그라운드)"""
        while True:
            task = self.image_queue.get()
            
            # 종료 신호
            if task is None:
                break
            
            try:
                host, usedata, bib, img_url, referer, pid = task
                
                # 이미지 저장
                saved_path = save_certificate_to_disk(
                    host, usedata, bib, img_url, referer
                )
                
                # DB 업데이트
                if saved_path:
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE participants SET finish_image_path=? WHERE id=?",
                            (saved_path, pid)
                        )
                        conn.commit()
            
            except Exception as e:
                print(f"[err] image save: {type(e).__name__}: {e}")
            
            finally:
                self.image_queue.task_done()


# ============= 실행 함수 =============

def main_loop():
    """
    레거시 함수 (호환성 유지)
    
    Deprecated: CrawlerEngine().run() 사용 권장
    """
    engine = CrawlerEngine()
    engine.run()


# ============= 사용 예시 =============

if __name__ == "__main__":
    print("=" * 50)
    print("SmartChip Crawler Engine")
    print("=" * 50)
    
    # 옵션 1: 기본 스케줄러 (고정 주기)
    print("\n[Option 1] Basic Scheduler")
    print("- Fixed refresh intervals")
    print("- No backoff on failures")
    engine = CrawlerEngine(use_adaptive_scheduler=False)
    
    # 옵션 2: 적응형 스케줄러 (실패 시 백오프)
    # print("\n[Option 2] Adaptive Scheduler")
    # print("- Exponential backoff on failures")
    # print("- Auto-recovery on success")
    # engine = CrawlerEngine(use_adaptive_scheduler=True)
    
    try:
        engine.run()
    except KeyboardInterrupt:
        print("\n[Shutdown] Stopping crawler...")
        engine.shutdown()
        print("Crawler stopped")