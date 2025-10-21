from typing import List, Dict, Optional
from core.database import get_db

class ParticipantService:
    """참가자 관련 비즈니스 로직"""
    
    @staticmethod
    def get_participant_data(participant_id: int) -> Dict:
        """참가자 상세 데이터 조회 (스플릿, 예측 포함)"""
        with get_db() as conn:
            # 참가자 기본 정보
            participant = conn.execute(
                """SELECT p.*, m.total_distance_km, m.url_template, m.usedata
                   FROM participants p
                   JOIN marathons m ON p.marathon_id = m.id
                   WHERE p.id = ?""",
                (participant_id,)
            ).fetchone()
            
            if not participant:
                return {'error': 'Participant not found'}
            
            # 스플릿 데이터
            splits = conn.execute(
                "SELECT * FROM splits WHERE participant_id=? ORDER BY id ASC",
                (participant_id,)
            ).fetchall()
            
            # 예측 계산
            from webapp.services.prediction import PredictionService
            prediction = PredictionService.calculate_prediction(
                splits, participant['race_total_km'] or participant['total_distance_km']
            )
            
            return {
                'participant': dict(participant),
                'splits': [dict(s) for s in splits],
                'prediction': prediction,
            }
    
    @staticmethod
    def create_participant(marathon_id: int, alias: str, nameorbibno: str) -> Dict:
        """참가자 추가"""
        with get_db() as conn:
            try:
                conn.execute(
                    """INSERT INTO participants(marathon_id, alias, nameorbibno, active)
                       VALUES(?, ?, ?, 1)""",
                    (marathon_id, alias, nameorbibno)
                )
                conn.commit()
                return {'success': True}
            except Exception as e:
                return {'error': str(e)}