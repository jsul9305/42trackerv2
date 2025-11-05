# webapp/services/prediction.py
"""예측/분석 비즈니스 로직"""

from typing import List, Dict, Optional
import json
from datetime import datetime, timezone, date
import math
import re

from config.constants import FINISH_KEYWORDS_KO, FINISH_KEYWORDS_EN, DISTANCE_TOLERANCE
from utils.time_utils import looks_time, sec_from_mmss, eta_from_clock, sec_per_km
from utils.distance_utils import km_from_label, snap_distance, ensure_finish_label

# --- 로컬 정규화 유틸 ---
_ZWSP_RE = re.compile(r"[\u200b\u200c\u200d\uFEFF]")
_WS_RE   = re.compile(r"\s+")

def _clean(s: Optional[str]) -> str:
    if not isinstance(s, str):
        return ""
    s = _ZWSP_RE.sub("", s).replace("\xa0"," ").strip()
    return _WS_RE.sub(" ", s)

def _is_finish_label(label: Optional[str]) -> bool:
    raw = _clean(label)
    low = raw.lower()
    return any(k in raw for k in FINISH_KEYWORDS_KO) or any(k in low for k in FINISH_KEYWORDS_EN)

# --- New Helpers for Location Prediction ---
def _haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371  # Radius of Earth in kilometers
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

STANDARD_SPLIT_ORDER = ["Start", "3K", "5K", "10K", "15K", "20K", "Half", "25K", "30K", "32K", "35K", "40K", "Finish"]

class PredictionService:
    @staticmethod
    def predict_current_state(splits: List[Dict], total_km: float, course_geo_json_str: Optional[str]) -> Dict:
        """
        Calculates finish prediction AND current interpolated location.
        This is the new main entry point for predictions.
        """
        prediction = PredictionService.calculate_prediction(splits, total_km)

        if prediction.get("finished") or not splits:
            return prediction

        try:
            location_prediction = PredictionService._predict_intermediate_location(
                splits,
                prediction.get('avg_pace_spk'),
                course_geo_json_str
            )
            if location_prediction:
                prediction.update(location_prediction)
        except Exception as e:
            print(f"Error during location prediction: {e}")

        return prediction

    @staticmethod
    def _predict_intermediate_location(splits: List[Dict], avg_pace_spk: Optional[float], course_geo_json_str: Optional[str]) -> Optional[Dict]:
        if not avg_pace_spk or not course_geo_json_str or not splits:
            return None

        try:
            course_data = json.loads(course_geo_json_str)
            split_points_coords = course_data.get("properties", {}).get("split_points")
            if not split_points_coords:
                return None
        except (json.JSONDecodeError, AttributeError):
            return None

        last_runner_split = splits[-1]
        last_split_label = _clean(last_runner_split.get("point_label", ""))

        try:
            last_split_index = STANDARD_SPLIT_ORDER.index(last_split_label)
        except ValueError:
            return None
        
        next_split_label = None
        for i in range(last_split_index + 1, len(STANDARD_SPLIT_ORDER)):
            potential_next = STANDARD_SPLIT_ORDER[i]
            if potential_next in split_points_coords:
                next_split_label = potential_next
                break
        
        if not next_split_label:
            return None

        last_coords = split_points_coords.get(last_split_label)
        next_coords = split_points_coords.get(next_split_label)

        if not last_coords or not next_coords:
            return None

        last_lon, last_lat = last_coords
        next_lon, next_lat = next_coords

        pass_clock_str = _clean(last_runner_split.get("pass_clock"))
        try:
            today = date.today()
            pass_datetime = datetime.fromisoformat(f"{today}T{pass_clock_str}")
            pass_datetime = pass_datetime.astimezone()
            time_since_last_split = (datetime.now(timezone.utc) - pass_datetime.astimezone(timezone.utc)).total_seconds()
        except (ValueError, TypeError):
            return None

        if time_since_last_split < 0: time_since_last_split = 0

        distance_to_next = _haversine_distance(last_lon, last_lat, next_lon, next_lat)
        time_to_next_split = distance_to_next * avg_pace_spk
        
        if time_to_next_split <= 0:
            progress_ratio = 1.0
        else:
            progress_ratio = time_since_last_split / time_to_next_split
        
        progress_ratio = max(0.0, min(1.0, progress_ratio))

        current_lon = last_lon + progress_ratio * (next_lon - last_lon)
        current_lat = last_lat + progress_ratio * (next_lat - last_lat)

        return {
            "current_location": {
                "lat": current_lat,
                "lon": current_lon
            },
            "debug_location": {
                "progress_ratio": progress_ratio,
                "time_since_last_split": time_since_last_split,
                "time_to_next_split": time_to_next_split,
                "distance_to_next": distance_to_next,
                "last_split": last_split_label,
                "next_split": next_split_label,
                "avg_pace_spk": avg_pace_spk
            }
        }

    @staticmethod
    def calculate_prediction(splits: List[Dict], total_km: float) -> Dict:
        if not splits:
            return {"finished": False, "status_text": "대기중"}

        splits = ensure_finish_label(splits, total_km)

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

        last_split = splits[-1]
        psecs = [s.get("pace_spk") for s in splits if s.get("pace_spk") is not None]
        last_split_pace_spk = last_split.get("pace_spk")
        use_spk = last_split_pace_spk or (sum(psecs) / len(psecs) if psecs else None)
        
        if use_spk is None:
            return {"finished": False, "status_text": "주행중",
                    "next_point_km": None, "next_point_eta": None,
                    "finish_eta": None, "finish_net_pred": None, "avg_pace_spk": None}
        
        last_km = km_from_label(_clean(last_split.get("point_label"))) or last_split.get("point_km") or 0.0
        remain_fin = max(0.0, (total_km or 0.0) - float(last_km))
        delta_fin = int(remain_fin * use_spk)
        base_clock = _clean(last_split.get("pass_clock"))
        fin_eta = eta_from_clock(base_clock, delta_fin) if looks_time(base_clock) else None
        last_net = sec_from_mmss(_clean(last_split.get("net_time"))) or 0
        fin_net = last_net + delta_fin
        h, m, s = fin_net // 3600, (fin_net % 3600) // 60, fin_net % 60
        fin_net_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        
        return {"finished": False, "status_text": "주행중",
                "finish_eta": fin_eta, "finish_net_pred": fin_net_str, "avg_pace_spk": use_spk}

    @staticmethod
    def check_finish_status(splits: List[Dict], total_km: float) -> Dict:
        if not splits:
            return {'finished': False, 'finish_point': None, 'finish_net': None, 'finish_clock': None}

        finish_rows = [s for s in splits if _is_finish_label(s.get("point_label"))]
        if finish_rows:
            last_finish = finish_rows[-1]
            net = _clean(last_finish.get("net_time"))
            clk = _clean(last_finish.get("pass_clock"))
            if looks_time(net) or looks_time(clk) or net or clk:
                return {
                    'finished': True,
                    'finish_point': _clean(last_finish.get("point_label")) or "Finish",
                    'finish_net': net if looks_time(net) else (net or None),
                    'finish_clock': clk if looks_time(clk) else (clk or None)
                }

        snapped_km = snap_distance(total_km) or total_km
        tolerance = 0.5
        for (min_km, max_km), tol in DISTANCE_TOLERANCE.items():
            if min_km <= snapped_km < max_km:
                tolerance = tol
                break

        for s in reversed(splits):
            point_km = s.get("point_km") or km_from_label(_clean(s.get("point_label")))
            if point_km is None:
                continue
            if abs(float(point_km) - float(snapped_km)) <= tolerance:
                net = _clean(s.get("net_time"))
                clk = _clean(s.get("pass_clock"))
                if looks_time(net) or looks_time(clk) or net or clk:
                    return {
                        'finished': True,
                        'finish_point': _clean(s.get("point_label")) or "Finish",
                        'finish_net': net if looks_time(net) else (net or None),
                        'finish_clock': clk if looks_time(clk) else (clk or None)
                    }

        try:
            total = float(total_km or 0.0)
        except Exception:
            total = 0.0
        if total > 0:
            last = splits[-1]
            last_km = last.get("point_km") or km_from_label(_clean(last.get("point_label")))
            try:
                last_km_f = float(last_km) if last_km is not None else None
            except Exception:
                last_km_f = None
            if last_km_f is not None and (last_km_f / total) >= 0.9:
                net = _clean(last.get("net_time"))
                clk = _clean(last.get("pass_clock"))
                if looks_time(net) or looks_time(clk) or net or clk:
                    return {
                        'finished': True,
                        'finish_point': _clean(last.get("point_label")) or "Finish",
                        'finish_net': net if looks_time(net) else (net or None),
                        'finish_clock': clk if looks_time(clk) else (clk or None)
                    }

        return {'finished': False, 'finish_point': None, 'finish_net': None, 'finish_clock': None}

    @staticmethod
    def is_finish_label(label: Optional[str]) -> bool:
        return _is_finish_label(label)

    @staticmethod
    def ensure_finish_label(splits, race_total_km=None):
        return ensure_finish_label(splits, race_total_km)
