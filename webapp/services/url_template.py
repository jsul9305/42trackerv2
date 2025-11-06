# webapp/services/url_template.py
"""URL 템플릿 비즈니스 로직"""

from typing import Dict, List
from core.database import get_db

class UrlTemplateService:
    """
    URL 템플릿 관련 비즈니스 로직
    """

    @staticmethod
    def list_templates() -> List[Dict]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM url_templates ORDER BY name").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_template(name: str, template: str) -> Dict:
        if not name or not template:
            return {"success": False, "error": "Name and template are required"}
        
        try:
            with get_db() as conn:
                cursor = conn.execute(
                    "INSERT INTO url_templates (name, template) VALUES (?, ?)",
                    (name, template)
                )
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def delete_template(template_id: int) -> Dict:
        try:
            with get_db() as conn:
                conn.execute("DELETE FROM url_templates WHERE id = ?", (template_id,))
                conn.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}
