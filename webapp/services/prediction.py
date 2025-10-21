# webapp/services/prediction.py
"""예측/분석 비즈니스 로직"""

from typing import List, Dict, Optional

from config.constants import FINISH_KEYWORDS_KO, FINISH_KEYWORDS_EN, DISTANCE_TOLERANCE
from utils.time_utils import looks_time, sec_from_mmss, eta_from_clock, sec_per_km
from utils.distance_utils import km_from_label, snap_distance


class PredictionService:
    """
    예측/분석 관련 비즈니스 로직

    주요 기능:
    - 완주 여부 판정
    - 예상 완주 기록/시각 계산
    """

    @staticmethod
    def calculate_prediction(splits: List[Dict], total_km: float) -> Dict:
        """
        스플릿 데이터를 기반으로 예측 정보 계산

        Args:
            splits: 스플릿 데이터 리스트
            total_km: 총 거리

        Returns:
            예측 정보 딕셔너리
        """
        if not splits:
            return {"finished": False, "status_text": "대기중"}

        # 1. 완주 여부 판정
        finish_check = PredictionService.check_finish_status(splits, total_km)

        if finish_check['finished']:
            net = finish_check['finish_net'] or ""
            clk = finish_check['finish_clock'] or ""
            point = finish_check['finish_point'] or "완주"

            return {
                "finished": True,
                "status_text": "완주",
                "finish_point": point,
                "finish_eta": f"완주 @ {clk}" if clk else "완주",
                "finish_net_pred": net,
                "display_point_time": net or clk
            }

        # 2. 주행 중 - 예상 시간 계산
        last_split = splits[-1]

        psecs = [sec_per_km(s["pace"]) for s in splits if sec_per_km(s.get("pace")) is not None]
        use_spk = sec_per_km(last_split.get("pace")) or (sum(psecs) / len(psecs) if psecs else None)

        if use_spk is None:
            return {
                "finished": False,
                "status_text": "주행중",
                "next_point_km": None,
                "next_point_eta": None,
                "finish_eta": None,
                "finish_net_pred": None,
            }

        last_km = km_from_label(last_split.get("point_label")) or last_split.get("point_km") or 0.0
        remain_fin = max(0.0, total_km - last_km)
        delta_fin = int(remain_fin * use_spk)

        base_clock = (last_split.get("pass_clock") or "").strip()
        fin_eta = eta_from_clock(base_clock, delta_fin) if looks_time(base_clock) else None

        last_net = sec_from_mmss(last_split.get("net_time") or "") or 0
        fin_net = last_net + delta_fin
        h, m, s = fin_net // 3600, (fin_net % 3600) // 60, fin_net % 60
        fin_net_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

        return {
            "finished": False,
            "status_text": "주행중",
            "finish_eta": fin_eta,
            "finish_net_pred": fin_net_str,
        }

    @staticmethod
    def check_finish_status(splits: List[Dict], total_km: float) -> Dict:
        """
        더 정확한 완주 판정
        - 1순위: '완주' 라벨
        - 2순위: 목표 거리에 근접한 기록
        - 3순위: 90% 이상 진행
        """
        if not splits:
            return {'finished': False, 'finish_point': None, 'finish_net': None, 'finish_clock': None}

        # 1순위: 완주 라벨이 있는 행 찾기
        finish_rows = [s for s in splits if PredictionService._is_finish_label(s.get("point_label"))]
        if finish_rows:
            last_finish = finish_rows[-1]
            net = (last_finish.get("net_time") or "").strip()
            clk = (last_finish.get("pass_clock") or "").strip()
            if looks_time(net) or looks_time(clk):
                return {
                    'finished': True,
                    'finish_point': last_finish.get("point_label"),
                    'finish_net': net if looks_time(net) else None,
                    'finish_clock': clk if looks_time(clk) else None
                }

        # 2순위: 목표 거리에 가까운 지점 찾기
        snapped_km = snap_distance(total_km) or total_km
        tolerance = 0.5
        for (min_km, max_km), tol in DISTANCE_TOLERANCE.items():
            if min_km <= snapped_km < max_km:
                tolerance = tol
                break

        for s in reversed(splits):
            point_km = s.get("point_km") or km_from_label(s.get("point_label"))
            if point_km is not None and abs(float(point_km) - snapped_km) <= tolerance:
                net = (s.get("net_time") or "").strip()
                clk = (s.get("pass_clock") or "").strip()
                if looks_time(net) or looks_time(clk):
                    return {
                        'finished': True,
                        'finish_point': s.get("point_label"),
                        'finish_net': net if looks_time(net) else None,
                        'finish_clock': clk if looks_time(clk) else None
                    }

        # 3순위: 마지막 split이 총 거리의 90% 이상이면 완주로 간주
        if total_km > 0:
            last_split = splits[-1]
            last_km = last_split.get("point_km") or km_from_label(last_split.get("point_label"))
            if last_km is not None and (float(last_km) / total_km) >= 0.9:
                net = (last_split.get("net_time") or "").strip()
                clk = (last_split.get("pass_clock") or "").strip()
                if looks_time(net) or looks_time(clk):
                    return {
                        'finished': True,
                        'finish_point': last_split.get("point_label"),
                        'finish_net': net if looks_time(net) else None,
                        'finish_clock': clk if looks_time(clk) else None
                    }

        return {'finished': False, 'finish_point': None, 'finish_net': None, 'finish_clock': None}

    @staticmethod
    def _is_finish_label(label: Optional[str]) -> bool:
        """완주 지점인지 판단 (한/영 키워드)"""
        if not label:
            return False
        raw = label.strip()
        low = raw.lower()
        return any(k in raw for k in FINISH_KEYWORDS_KO) or any(k in low for k in FINISH_KEYWORDS_EN)
