# webapp/services/course.py
"""코스 비즈니스 로직"""

from typing import Dict, List, Optional
from core.database import get_db


class CourseService:
    """
    코스 관련 비즈니스 로직
    """

    @staticmethod
    def get_courses_by_marathon(marathon_id: int) -> List[Dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM courses WHERE marathon_id = ? ORDER BY name",
                (marathon_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_course(
        marathon_id: int,
        name: str,
        total_distance_km: float,
        course_geo_json: str
    ) -> Dict:
        if not all([name, total_distance_km, course_geo_json]):
            return {"success": False, "error": "All fields are required"}

        try:
            with get_db() as conn:
                cursor = conn.execute(
                    """INSERT INTO courses (marathon_id, name, total_distance_km, course_geo_json)
                       VALUES (?, ?, ?, ?)""",
                    (marathon_id, name, total_distance_km, course_geo_json)
                )
                conn.commit()
                return {"success": True, "course_id": cursor.lastrowid}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def delete_course(course_id: int) -> Dict:
        try:
            with get_db() as conn:
                conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
                conn.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def update_course(course_id: int, **updates) -> Dict:
        allowed_fields = {"name", "total_distance_km", "course_geo_json"}
        
        fields = []
        values = []
        
        for key, value in updates.items():
            if key in allowed_fields:
                fields.append(f"{key}=?")
                values.append(value)
        
        if not fields:
            return {"success": False, "error": "No fields to update"}
        
        values.append(course_id)
        
        try:
            with get_db() as conn:
                conn.execute(
                    f"UPDATE courses SET {', '.join(fields)} WHERE id=?",
                    values
                )
                conn.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}
