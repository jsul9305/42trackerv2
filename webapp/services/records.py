# webapp/services/records.py
"""기록 조회 비즈니스 로직"""

import re
from typing import List, Dict, Optional

from core.database import get_db
from utils.distance_utils import label_for_distance
from utils.file_utils import to_web_static_url
from utils.time_utils import looks_time
from config.constants import FINISH_KEYWORDS_KO, FINISH_KEYWORDS_EN


class RecordsService:
    """
    기록 조회/처리 관련 비즈니스 로직

    주요 기능:
    - 전체 참가자 기록 조회 (필터링, 정렬 포함)
    - 참가자별 최종 기록 선택
    """

    @staticmethod
    def get_all_records(
        query: Optional[str] = None,
        marathon_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        모든 활성 참가자의 기록을 조회, 필터링, 정렬
        """
        with get_db() as conn:
            participants = conn.execute("""
                SELECT p.*, m.name AS marathon_name, m.total_distance_km AS default_km
                FROM participants p
                JOIN marathons m ON m.id = p.marathon_id
                WHERE p.active = 1
            """).fetchall()

            items = []
            for p in participants:
                best = RecordsService._pick_best_record(conn, p["id"])

                name = (p["alias"] or "").strip() or (p["nameorbibno"] or "").strip()
                dist = p["race_total_km"] if p["race_total_km"] is not None else p["default_km"]
                label = (p["race_label"] or "").strip() or label_for_distance(dist)

                asset = conn.execute(
                    "SELECT * FROM assets WHERE participant_id=? AND kind='certificate' ORDER BY id DESC LIMIT 1",
                    (p["id"],)
                ).fetchone()

                cert_web = None
                if asset:
                    cert_web = to_web_static_url(asset["local_path"]) or asset["url"]
                elif p["finish_image_path"] or p["finish_image_url"]:
                    cert_web = to_web_static_url(p["finish_image_path"]) or p["finish_image_url"]

                items.append({
                    "name": name,
                    "category": label,
                    "distance": float(dist or 0.0),
                    "marathon": p["marathon_name"],
                    "record": best.get("record") if best else "",
                    "clock": best.get("clock") if best else "",
                    "cert_web": cert_web,
                })

        # 필터링
        if query:
            q_lower = query.lower()
            items = [it for it in items if q_lower in (it["name"] or "").lower()]
        if marathon_filter:
            m_lower = marathon_filter.lower()
            items = [it for it in items if m_lower in (it["marathon"] or "").lower()]

        # 정렬
        items.sort(key=RecordsService._sort_key)
        return items

    @staticmethod
    def _pick_best_record(conn, participant_id: int) -> Optional[Dict]:
        """참가자의 최종 기록(net, clock) 선택"""
        splits = conn.execute(
            "SELECT * FROM splits WHERE participant_id=? ORDER BY id ASC",
            (participant_id,)
        ).fetchall()

        if not splits:
            return None

        def _is_finish(label: Optional[str]) -> bool:
            if not label:
                return False
            raw = label.strip()
            low = raw.lower()
            return any(k in raw for k in FINISH_KEYWORDS_KO) or any(k in low for k in FINISH_KEYWORDS_EN)

        finish_splits = [s for s in splits if _is_finish(s["point_label"])]
        best_split = finish_splits[-1] if finish_splits else splits[-1]

        record = (best_split["net_time"] or "").strip()
        if not looks_time(record):
            # 유효한 net_time이 아니면 마지막 split의 net_time을 다시 시도
            record = (splits[-1]["net_time"] or "").strip()

        clock = (best_split["pass_clock"] or "").strip()

        return {
            "point_label": best_split["point_label"],
            "record": record if looks_time(record) else "",
            "clock": clock if looks_time(clock) else "",
        }

    @staticmethod
    def _sort_key(item: Dict) -> tuple:
        """기록 정렬 키 생성: 이름 -> 거리(내림차순) -> 기록(오름차순)"""
        def _sec(t: Optional[str]) -> Optional[int]:
            if not t:
                return None
            s = t.strip()
            parts = s.split(':')
            try:
                if len(parts) == 3:
                    h, m, s_float = int(parts[0]), int(parts[1]), float(parts[2])
                    return int(h * 3600 + m * 60 + s_float)
                elif len(parts) == 2:
                    m, s_float = int(parts[0]), float(parts[1])
                    return int(m * 60 + s_float)
            except (ValueError, IndexError):
                return None
            return None

        dist = float(item.get("distance") or 0.0)
        record_sec = _sec(item.get("record"))
        sortable_record = record_sec if record_sec is not None else float('inf')
        return (item["name"], -dist, sortable_record)
