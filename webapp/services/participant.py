# webapp/services/participant.py
"""참가자 비즈니스 로직"""

from typing import Dict, List, Optional, Any
from urllib.parse import urlsplit

from core.database import get_db


class ParticipantService:
    """
    참가자 관련 비즈니스 로직
    
    주요 기능:
    - 참가자 CRUD
    - 참가자 데이터 조회 (스플릿, 예측 포함)
    - BIB 번호 정규화 (SPCT 6자리 등)
    """
    
    @staticmethod
    def list_participants(
        marathon_id: Optional[int] = None,
        active_only: bool = False
    ) -> List[Dict]:
        """
        참가자 목록 조회
        
        Args:
            marathon_id: 특정 마라톤의 참가자만 (None이면 전체)
            active_only: True면 active=1인 참가자만
        
        Returns:
            참가자 목록
        """
        with get_db() as conn:
            if marathon_id:
                if active_only:
                    query = "SELECT * FROM participants WHERE marathon_id=? AND active=1 ORDER BY id DESC"
                    params = (marathon_id,)
                else:
                    query = "SELECT * FROM participants WHERE marathon_id=? ORDER BY id DESC"
                    params = (marathon_id,)
            else:
                if active_only:
                    query = "SELECT * FROM participants WHERE active=1 ORDER BY id DESC"
                    params = ()
                else:
                    query = "SELECT * FROM participants ORDER BY id DESC"
                    params = ()
            
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_participant(participant_id: int) -> Optional[Dict]:
        """
        특정 참가자 조회
        
        Args:
            participant_id: 참가자 ID
        
        Returns:
            참가자 정보 또는 None
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM participants WHERE id=?",
                (participant_id,)
            ).fetchone()
            
            return dict(row) if row else None
    
    @staticmethod
    def create_participant(
        marathon_id: int,
        nameorbibno: str,
        alias: Optional[str] = None
    ) -> Dict:
        """
        참가자 생성
        
        Args:
            marathon_id: 마라톤 ID
            nameorbibno: 참가번호 또는 이름
            alias: 표시명 (선택)
        
        Returns:
            {'success': bool, 'participant_id': int, 'error': str}
        """
        # 유효성 검증
        if not nameorbibno or not nameorbibno.strip():
            return {'success': False, 'error': '참가번호/이름은 필수입니다'}
        
        nameorbibno = nameorbibno.strip()
        
        # SPCT 6자리 정규화
        nameorbibno = ParticipantService._normalize_bib_for_spct(
            marathon_id, nameorbibno
        )
        
        try:
            with get_db() as conn:
                cursor = conn.execute(
                    """INSERT INTO participants(marathon_id, alias, nameorbibno, active)
                       VALUES(?, ?, ?, 1)""",
                    (marathon_id, alias.strip() if alias else None, nameorbibno)
                )
                conn.commit()
                
                return {
                    'success': True,
                    'participant_id': cursor.lastrowid,
                    'normalized_bib': nameorbibno
                }
        
        except Exception as e:
            # UNIQUE 제약 위반 (이미 존재)
            if 'UNIQUE constraint failed' in str(e):
                return {
                    'success': False,
                    'error': '이미 등록된 참가자입니다'
                }
            
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
    
    @staticmethod
    def update_participant(
        participant_id: int,
        **updates
    ) -> Dict:
        """
        참가자 정보 수정
        
        Args:
            participant_id: 참가자 ID
            **updates: 수정할 필드들
                - alias: 표시명
                - nameorbibno: 참가번호
                - active: 활성화 여부
        
        Returns:
            {'success': bool, 'error': str}
        """
        allowed_fields = {'alias', 'nameorbibno', 'active'}
        
        fields = []
        values = []
        
        for key, value in updates.items():
            if key in allowed_fields:
                fields.append(f"{key}=?")
                values.append(value)
        
        if not fields:
            return {'success': False, 'error': '수정할 필드가 없습니다'}
        
        values.append(participant_id)
        
        try:
            with get_db() as conn:
                conn.execute(
                    f"UPDATE participants SET {', '.join(fields)} WHERE id=?",
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
    def delete_participant(participant_id: int) -> Dict:
        """
        참가자 삭제 (CASCADE로 스플릿도 삭제됨)
        
        Args:
            participant_id: 참가자 ID
        
        Returns:
            {'success': bool, 'error': str}
        """
        try:
            with get_db() as conn:
                conn.execute(
                    "DELETE FROM participants WHERE id=?",
                    (participant_id,)
                )
                conn.commit()
                
                return {'success': True}
        
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
    
    @staticmethod
    def get_participant_data(participant_id: int) -> Dict:
        """
        참가자 상세 데이터 (스플릿, 예측 포함)
        
        Args:
            participant_id: 참가자 ID
        
        Returns:
            {
                'participant': Dict,
                'splits': List[Dict],
                'prediction': Dict,
                'url': str
            }
        """
        with get_db() as conn:
            # 참가자 + 마라톤 정보
            p = conn.execute(
                """SELECT p.*, m.total_distance_km, m.url_template, m.usedata
                   FROM participants p
                   JOIN marathons m ON p.marathon_id = m.id
                   WHERE p.id = ?""",
                (participant_id,)
            ).fetchone()
            
            if not p:
                return {'error': 'Participant not found'}
            
            # 스플릿 데이터
            splits = conn.execute(
                "SELECT * FROM splits WHERE participant_id=? ORDER BY id ASC",
                (participant_id,)
            ).fetchall()
            
            # URL 생성
            url = (p['url_template'] or '').replace(
                '{nameorbibno}', p['nameorbibno']
            ).replace(
                '{usedata}', p['usedata'] or ''
            )
            
            # 예측 계산 (간단 버전)
            from webapp.services.prediction import PredictionService
            prediction = PredictionService.calculate_prediction(
                [dict(s) for s in splits],
                p['race_total_km'] or p['total_distance_km']
            )
            
            return {
                'participant': dict(p),
                'splits': [dict(s) for s in splits],
                'prediction': prediction,
                'url': url
            }
    
    @staticmethod
    def _normalize_bib_for_spct(marathon_id: int, bib: str) -> str:
        """
        SPCT 대회인 경우 BIB을 6자리로 정규화
        
        Args:
            marathon_id: 마라톤 ID
            bib: 참가번호
        
        Returns:
            정규화된 참가번호
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT url_template FROM marathons WHERE id=?",
                (marathon_id,)
            ).fetchone()
            
            if not row:
                return bib
            
            url_template = row['url_template'] or ''
            host = (urlsplit(url_template).hostname or '').lower()
            
            # SPCT 호스트이고 숫자면 6자리 제로패딩
            if 'spct' in host and bib.isdigit():
                return bib.zfill(6)
            
            return bib


# ============= 사용 예시 =============

if __name__ == "__main__":
    print("Testing ParticipantService...")
    
    # 1. 참가자 생성 (SPCT)
    result = ParticipantService.create_participant(
        marathon_id=1,
        nameorbibno="123",  # → 000123으로 정규화됨
        alias="홍길동"
    )
    print(f"Create: {result}")
    
    if result['success']:
        pid = result['participant_id']
        
        # 2. 참가자 조회
        participant = ParticipantService.get_participant(pid)
        print(f"Get: {participant}")
        
        # 3. 참가자 수정
        update_result = ParticipantService.update_participant(
            pid,
            alias="홍길동 (수정)"
        )
        print(f"Update: {update_result}")
        
        # 4. 목록 조회
        participants = ParticipantService.list_participants(
            marathon_id=1,
            active_only=True
        )
        print(f"List: {len(participants)} participants")
        
        # 5. 삭제
        delete_result = ParticipantService.delete_participant(pid)
        print(f"Delete: {delete_result}")
    
    print("\n✓ Tests completed")