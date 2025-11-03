from core.database import get_db
from typing import List, Dict, Any

from webapp.services.prediction import PredictionService
from utils.time_utils import sec_from_mmss, hms_from_sec
from utils.distance_utils import km_from_label

class ParticipantService:
    @staticmethod
    def list_participants(group_id: int) -> List[Dict]:
        """Lists all participants for a given group."""
        with get_db() as conn:
            cur = conn.execute(
                "SELECT * FROM participants WHERE group_id = ? ORDER BY id DESC",
                (group_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def list_participants_by_marathon(marathon_id: int) -> List[Dict]:
        """특정 마라톤의 모든 참가자 목록을 반환합니다."""
        with get_db() as conn:
            rows = conn.execute("""
                SELECT p.* FROM participants p
                JOIN groups g ON p.group_id = g.id
                WHERE g.marathon_id = ?
            """, (marathon_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_participant(group_id: int, nameorbibno: str, alias: str = None) -> Dict:
        """Creates a single participant in a group."""
        if not group_id or not nameorbibno:
            return {"success": False, "error": "Group ID and bib number are required."}
        try:
            with get_db() as conn:
                cur = conn.execute(
                    "INSERT INTO participants (group_id, nameorbibno, alias, active) VALUES (?, ?, ?, 1)",
                    (group_id, nameorbibno, alias)
                )
                participant_id = cur.lastrowid
                conn.commit()
                return {"success": True, "participant_id": participant_id}
        except Exception as e:
            # Handle potential UNIQUE constraint violation
            if "UNIQUE constraint failed" in str(e):
                return {"success": False, "error": f"Participant with bib number '{nameorbibno}' already exists in this group."}
            return {"success": False, "error": str(e)}

    @staticmethod
    def bulk_create_participants(group_id: int, participants: List[Dict[str, str]]) -> Dict:
        """Bulk creates participants in a group from a list."""
        created_count = 0
        skipped_count = 0
        errors = []
        
        with get_db() as conn:
            for p_data in participants:
                nameorbibno = p_data.get("nameorbibno")
                alias = p_data.get("alias")
                if not nameorbibno:
                    skipped_count += 1
                    continue
                
                try:
                    # Check if participant already exists
                    cur = conn.execute(
                        "SELECT id FROM participants WHERE group_id = ? AND nameorbibno = ?",
                        (group_id, nameorbibno)
                    )
                    if cur.fetchone():
                        skipped_count += 1
                        continue

                    # Insert new participant
                    conn.execute(
                        "INSERT INTO participants (group_id, nameorbibno, alias, active) VALUES (?, ?, ?, 1)",
                        (group_id, nameorbibno, alias)
                    )
                    created_count += 1
                except Exception as e:
                    errors.append(f"Failed to add '{nameorbibno}': {e}")
            
            conn.commit()

        return {
            "success": len(errors) == 0,
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors
        }

    @staticmethod
    def delete_participant(participant_id: int) -> Dict:
        """Deletes a participant."""
        try:
            with get_db() as conn:
                cur = conn.execute("DELETE FROM participants WHERE id = ?", (participant_id,))
                conn.commit()
                if cur.rowcount > 0:
                    return {"success": True}
                else:
                    return {"success": False, "error": "Participant not found."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_participant_data(participant_id: int) -> Dict:
        """Retrieves detailed data for a single participant, including marathon info."""
        with get_db() as conn:
            cur = conn.execute("""
                SELECT p.*, m.url_template, m.usedata, m.name as marathon_name, m.total_distance_km
                FROM participants p
                JOIN groups g ON p.group_id = g.id
                JOIN marathons m ON g.marathon_id = m.id
                WHERE p.id = ?
            """, (participant_id,))
            
            participant = cur.fetchone()
            if not participant:
                return {"error": "Participant not found"}

            participant_dict = dict(participant)
            
            # Construct the specific participant URL if url_template is available
            if participant_dict.get("url_template"):
                url = participant_dict["url_template"]
                url = url.replace("{nameorbibno}", participant_dict.get("nameorbibno") or "")
                url = url.replace("{usedata}", participant_dict.get("usedata") or "")
                if "{bib_spct6}" in url:
                    bib = participant_dict.get("nameorbibno") or ""
                    bib6 = bib.zfill(6) if bib.isdigit() else bib
                    url = url.replace("{bib_spct6}", bib6)
                participant_dict["url"] = url

            # Get and process splits
            splits_cur = conn.execute("SELECT * FROM splits WHERE participant_id = ? ORDER BY id ASC", (participant_id,))
            raw_splits = [dict(row) for row in splits_cur.fetchall()]
            
            processed_splits = []
            last_km = 0.0
            last_sec = 0

            for split in raw_splits:
                new_split = split.copy()
                current_km = new_split.get('point_km') or km_from_label(new_split.get('point_label')) or 0.0
                current_sec = sec_from_mmss(new_split.get('net_time'))

                interval_km = float(current_km) - last_km
                interval_sec = current_sec - last_sec if current_sec is not None else None

                new_split['interval'] = hms_from_sec(interval_sec) if interval_sec is not None else None

                if interval_km > 0 and interval_sec is not None and interval_sec > 0:
                    pace_sec_per_km = interval_sec / interval_km
                    new_split['pace'] = hms_from_sec(pace_sec_per_km, show_hour=False)
                else:
                    new_split['pace'] = None

                processed_splits.append(new_split)
                
                last_km = float(current_km)
                if current_sec is not None:
                    last_sec = current_sec

            participant_dict["splits"] = processed_splits

            # Add prediction data
            total_km = participant_dict.get('race_total_km') or participant_dict.get('total_distance_km')
            if total_km:
                prediction = PredictionService.calculate_prediction(processed_splits, float(total_km))
                participant_dict["prediction"] = prediction

            return participant_dict
