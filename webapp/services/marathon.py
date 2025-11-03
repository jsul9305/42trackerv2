# webapp/services/marathon.py
"""마라톤 비즈니스 로직"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import random
import string

from core.database import get_db


class MarathonService:
    """
    마라톤 관련 비즈니스 로직
    """    

    @staticmethod
    def generate_unique_code(conn, length: int = 8) -> str:
        """
        Generates a unique code for marathons or groups, ensuring it doesn't exist in either table.
        """
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            
            marathon_exists = conn.execute(
                "SELECT id FROM marathons WHERE join_code = ?", (code,)
            ).fetchone()
            if marathon_exists:
                continue

            group_exists = conn.execute(
                "SELECT id FROM groups WHERE join_code = ?", (code,)
            ).fetchone()
            if group_exists:
                continue
            
            return code
    
    @staticmethod
    def list_marathons(enabled_only: bool = False) -> List[Dict]:
        with get_db() as conn:
            if enabled_only:
                query = "SELECT * FROM marathons WHERE enabled=1 ORDER BY id DESC"
            else:
                query = "SELECT * FROM marathons ORDER BY id DESC"
            
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_marathon(marathon_id: int) -> Optional[Dict]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM marathons WHERE id=?",
                (marathon_id,)
            ).fetchone()
            
            return dict(row) if row else None
        
    @staticmethod
    def get_marathon_by_join_code(code: str) -> Optional[Dict]:
        if not code:
            return None
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM marathons WHERE join_code=?",
                (code.strip(),)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_marathon(
        name: str,
        url_template: str,
        usedata: Optional[str] = None,
        total_distance_km: float = 21.1,
        refresh_sec: int = 60,
        enabled: bool = True,
        cert_url_template: Optional[str] = None,
        event_date: Optional[str] = None,
        course_geo_json: Optional[str] = None
    ) -> Dict:
        if not name or not name.strip():
            return {'success': False, 'error': '대회명은 필수입니다'}

        if not url_template or '{nameorbibno}' not in url_template:
            return {'success': False, 'error': 'URL 템플릿에 {nameorbibno}를 포함해야 합니다'}

        if refresh_sec < 5:
            return {'success': False, 'error': '새로고침 주기는 최소 5초 이상이어야 합니다'}

        try:
            with get_db() as conn:
                join_code = MarathonService.generate_unique_code(conn, length=8)
                cursor = conn.execute(
                    """INSERT INTO marathons(
                        name, url_template, usedata, 
                        total_distance_km, refresh_sec, enabled,
                        cert_url_template, event_date, join_code, updated_at,
                        course_geo_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name.strip(),
                        url_template.strip(),
                        usedata.strip() if usedata else None,
                        total_distance_km,
                        refresh_sec,
                        1 if enabled else 0,
                        cert_url_template.strip() if cert_url_template else None,
                        event_date,
                        join_code,
                        datetime.now().isoformat(),
                        course_geo_json
                    )
                )
                conn.commit()

                return {
                    'success': True,
                    'marathon_id': cursor.lastrowid,
                    'join_code': join_code
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
        
    @staticmethod
    def regenerate_join_code(marathon_id: int) -> Dict:
        if not marathon_id:
            return {'success': False, 'error': 'marathon_id가 필요합니다'}

        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT id FROM marathons WHERE id=?",
                    (marathon_id,)
                ).fetchone()
                if not row:
                    return {'success': False, 'error': '마라톤을 찾을 수 없습니다'}

                new_code = MarathonService.generate_unique_code(conn, length=8)

                conn.execute(
                    "UPDATE marathons SET join_code=?, updated_at=? WHERE id=?",
                    (new_code, datetime.now().isoformat(), marathon_id)
                )
                conn.commit()

                return {'success': True, 'join_code': new_code}

        except Exception as e:
            return {'success': False, 'error': f'{type(e).__name__}: {e}'}
    
    @staticmethod
    def update_marathon(
        marathon_id: int,
        **updates
    ) -> Dict:
        allowed_fields = {
            'name', 'url_template', 'usedata',
            'total_distance_km', 'refresh_sec', 'enabled',
            'cert_url_template', 'event_date', 'course_geo_json'
        }
        
        fields = []
        values = []
        
        for key, value in updates.items():
            if key in allowed_fields:
                if key == 'url_template':
                    if not value or '{nameorbibno}' not in value:
                        return {
                            'success': False,
                            'error': 'URL 템플릿에 {nameorbibno}를 포함해야 합니다'
                        }
                
                if key == 'refresh_sec' and value is not None and value < 5:
                    return {
                        'success': False,
                        'error': '새로고침 주기는 최소 5초 이상이어야 합니다'
                    }
                
                fields.append(f"{key}=?")
                values.append(value)
        
        if not fields:
            return {'success': False, 'error': '수정할 필드가 없습니다'}
        
        fields.append("updated_at=?")
        values.append(datetime.now().isoformat())
        
        values.append(marathon_id)
        
        try:
            with get_db() as conn:
                conn.execute(
                    f"UPDATE marathons SET {', '.join(fields)} WHERE id=?",
                    values
                )
                conn.commit()
                
                return {'success': True}
        
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
    
    @staticmethod
    def delete_marathon(marathon_id: int) -> Dict:
        try:
            with get_db() as conn:
                conn.execute(
                    "DELETE FROM marathons WHERE id=?",
                    (marathon_id,)
                )
                conn.commit()
                
                return {'success': True}
        
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
    
    @staticmethod
    def toggle_enabled(marathon_id: int) -> Dict:
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT enabled FROM marathons WHERE id=?",
                    (marathon_id,)
                ).fetchone()
                
                if not row:
                    return {
                        'success': False,
                        'error': '마라톤을 찾을 수 없습니다'
                    }
                
                new_enabled = 0 if row['enabled'] else 1
                
                conn.execute(
                    "UPDATE marathons SET enabled=?, updated_at=? WHERE id=?",
                    (new_enabled, datetime.now().isoformat(), marathon_id)
                )
                conn.commit()
                
                return {
                    'success': True,
                    'enabled': bool(new_enabled)
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
    
    @staticmethod
    def get_marathon_stats(marathon_id: int) -> Dict:
        with get_db() as conn:
            total_participants = conn.execute("""
                SELECT COUNT(*) FROM participants p
                JOIN groups g ON p.group_id = g.id
                WHERE g.marathon_id = ?
            """, (marathon_id,)).fetchone()[0]
            
            active_participants = conn.execute("""
                SELECT COUNT(*) FROM participants p
                JOIN groups g ON p.group_id = g.id
                WHERE g.marathon_id = ? AND p.active = 1
            """, (marathon_id,)).fetchone()[0]
            
            total_splits = conn.execute("""
                SELECT COUNT(s.id) FROM splits s
                JOIN participants p ON s.participant_id = p.id
                JOIN groups g ON p.group_id = g.id
                WHERE g.marathon_id=?
            """, (marathon_id,)).fetchone()[0]
            
            last_updated_row = conn.execute(
                "SELECT updated_at FROM marathons WHERE id=?",
                (marathon_id,)
            ).fetchone()
            
            return {
                'total_participants': total_participants,
                'active_participants': active_participants,
                'total_splits': total_splits,
                'last_updated': last_updated_row['updated_at'] if last_updated_row else None
            }
