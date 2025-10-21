# webapp/services/marathon.py
"""마라톤 비즈니스 로직"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from core.database import get_db


class MarathonService:
    """
    마라톤 관련 비즈니스 로직
    
    주요 기능:
    - 마라톤 CRUD (생성, 조회, 수정, 삭제)
    - 마라톤 활성화/비활성화
    - 마라톤 통계
    """
    
    @staticmethod
    def list_marathons(enabled_only: bool = False) -> List[Dict]:
        """
        마라톤 목록 조회
        
        Args:
            enabled_only: True면 활성화된 마라톤만 조회
        
        Returns:
            마라톤 목록
        """
        with get_db() as conn:
            if enabled_only:
                query = "SELECT * FROM marathons WHERE enabled=1 ORDER BY id DESC"
            else:
                query = "SELECT * FROM marathons ORDER BY id DESC"
            
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_marathon(marathon_id: int) -> Optional[Dict]:
        """
        특정 마라톤 조회
        
        Args:
            marathon_id: 마라톤 ID
        
        Returns:
            마라톤 정보 또는 None
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM marathons WHERE id=?",
                (marathon_id,)
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
        cert_url_template: Optional[str] = None
    ) -> Dict:
        """
        마라톤 생성
        
        Args:
            name: 대회명
            url_template: URL 템플릿 ({nameorbibno}, {usedata} 포함)
            usedata: 대회 ID (선택)
            total_distance_km: 총 거리 (기본: 21.1km)
            refresh_sec: 새로고침 주기 (기본: 60초)
            enabled: 활성화 여부 (기본: True)
            cert_url_template: 기록증 URL 템플릿 (선택)
        
        Returns:
            {'success': bool, 'marathon_id': int, 'error': str}
        """
        # 유효성 검증
        if not name or not name.strip():
            return {'success': False, 'error': '대회명은 필수입니다'}
        
        if not url_template or '{nameorbibno}' not in url_template:
            return {'success': False, 'error': 'URL 템플릿에 {nameorbibno}를 포함해야 합니다'}
        
        if refresh_sec < 5:
            return {'success': False, 'error': '새로고침 주기는 최소 5초 이상이어야 합니다'}
        
        try:
            with get_db() as conn:
                cursor = conn.execute(
                    """INSERT INTO marathons(
                        name, url_template, usedata, 
                        total_distance_km, refresh_sec, enabled,
                        cert_url_template, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name.strip(),
                        url_template.strip(),
                        usedata.strip() if usedata else None,
                        total_distance_km,
                        refresh_sec,
                        1 if enabled else 0,
                        cert_url_template.strip() if cert_url_template else None,
                        datetime.now().isoformat()
                    )
                )
                conn.commit()
                
                return {
                    'success': True,
                    'marathon_id': cursor.lastrowid
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {e}'
            }
    
    @staticmethod
    def update_marathon(
        marathon_id: int,
        **updates
    ) -> Dict:
        """
        마라톤 정보 수정
        
        Args:
            marathon_id: 마라톤 ID
            **updates: 수정할 필드들
                - name: 대회명
                - url_template: URL 템플릿
                - usedata: 대회 ID
                - total_distance_km: 총 거리
                - refresh_sec: 새로고침 주기
                - enabled: 활성화 여부
                - cert_url_template: 기록증 URL 템플릿
        
        Returns:
            {'success': bool, 'error': str}
        """
        # 허용된 필드만 업데이트
        allowed_fields = {
            'name', 'url_template', 'usedata',
            'total_distance_km', 'refresh_sec', 'enabled',
            'cert_url_template'
        }
        
        fields = []
        values = []
        
        for key, value in updates.items():
            if key in allowed_fields:
                # URL 템플릿 검증
                if key == 'url_template':
                    if '{nameorbibno}' not in value:
                        return {
                            'success': False,
                            'error': 'URL 템플릿에 {nameorbibno}를 포함해야 합니다'
                        }
                
                # refresh_sec 검증
                if key == 'refresh_sec' and value < 5:
                    return {
                        'success': False,
                        'error': '새로고침 주기는 최소 5초 이상이어야 합니다'
                    }
                
                fields.append(f"{key}=?")
                values.append(value)
        
        if not fields:
            return {'success': False, 'error': '수정할 필드가 없습니다'}
        
        # updated_at 추가
        fields.append("updated_at=?")
        values.append(datetime.now().isoformat())
        
        # marathon_id 추가
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
        """
        마라톤 삭제 (CASCADE로 참가자/스플릿도 삭제됨)
        
        Args:
            marathon_id: 마라톤 ID
        
        Returns:
            {'success': bool, 'error': str}
        """
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
        """
        마라톤 활성화/비활성화 토글
        
        Args:
            marathon_id: 마라톤 ID
        
        Returns:
            {'success': bool, 'enabled': bool, 'error': str}
        """
        try:
            with get_db() as conn:
                # 현재 상태 조회
                row = conn.execute(
                    "SELECT enabled FROM marathons WHERE id=?",
                    (marathon_id,)
                ).fetchone()
                
                if not row:
                    return {
                        'success': False,
                        'error': '마라톤을 찾을 수 없습니다'
                    }
                
                # 토글
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
        """
        마라톤 통계
        
        Args:
            marathon_id: 마라톤 ID
        
        Returns:
            {
                'total_participants': int,
                'active_participants': int,
                'total_splits': int,
                'last_updated': str
            }
        """
        with get_db() as conn:
            # 참가자 수
            total_participants = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE marathon_id=?",
                (marathon_id,)
            ).fetchone()[0]
            
            active_participants = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE marathon_id=? AND active=1",
                (marathon_id,)
            ).fetchone()[0]
            
            # 스플릿 수
            total_splits = conn.execute(
                """SELECT COUNT(*) FROM splits 
                   WHERE participant_id IN (
                       SELECT id FROM participants WHERE marathon_id=?
                   )""",
                (marathon_id,)
            ).fetchone()[0]
            
            # 마지막 업데이트
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


# ============= 사용 예시 =============

if __name__ == "__main__":
    # 테스트
    print("Testing MarathonService...")
    
    # 1. 마라톤 생성
    result = MarathonService.create_marathon(
        name="2025 테스트 마라톤",
        url_template="https://smartchip.co.kr/data.asp?nameorbibno={nameorbibno}&usedata={usedata}",
        usedata="202550000158",
        total_distance_km=21.1,
        refresh_sec=60
    )
    print(f"Create: {result}")
    
    if result['success']:
        mid = result['marathon_id']
        
        # 2. 마라톤 조회
        marathon = MarathonService.get_marathon(mid)
        print(f"Get: {marathon['name']}")
        
        # 3. 마라톤 수정
        update_result = MarathonService.update_marathon(
            mid,
            refresh_sec=30
        )
        print(f"Update: {update_result}")
        
        # 4. 통계
        stats = MarathonService.get_marathon_stats(mid)
        print(f"Stats: {stats}")
        
        # 5. 삭제
        delete_result = MarathonService.delete_marathon(mid)
        print(f"Delete: {delete_result}")
    
    print("\n✓ Tests completed")