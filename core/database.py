import sqlite3
from contextlib import contextmanager
from typing import Generator
from config.settings import DB_PATH

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS marathons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  url_template TEXT NOT NULL,
  usedata TEXT,
  total_distance_km REAL NOT NULL DEFAULT 21.1,
  refresh_sec INTEGER NOT NULL DEFAULT 60,
  enabled INTEGER NOT NULL DEFAULT 1,
  cert_url_template TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS participants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  marathon_id INTEGER NOT NULL REFERENCES marathons(id) ON DELETE CASCADE,
  alias TEXT,
  nameorbibno TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  race_label TEXT,
  race_total_km REAL,
  cert_key TEXT,
  finish_image_url TEXT,
  finish_image_path TEXT,
  UNIQUE(marathon_id, nameorbibno)
);

CREATE TABLE IF NOT EXISTS splits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
  point_label TEXT NOT NULL,
  point_km REAL,
  net_time TEXT,
  pass_clock TEXT,
  pace TEXT,
  seen_at TEXT,
  UNIQUE(participant_id, point_label)
);

CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  host TEXT,
  url TEXT,
  local_path TEXT,
  seen_at TEXT,
  UNIQUE(participant_id, kind)
);
"""

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """DB 연결 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """데이터베이스 초기화"""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

def migrate_database():
    """스키마 마이그레이션"""
    migrations = [
        "ALTER TABLE participants ADD COLUMN race_label TEXT",
        "ALTER TABLE participants ADD COLUMN race_total_km REAL",
            # ▼ 추가: 스마트칩 Bally_no 같은 별도 키 저장용
            "ALTER TABLE participants ADD COLUMN cert_key TEXT",
            # ▼ 추가: 완주증 최종 이미지 URL 저장
            "ALTER TABLE participants ADD COLUMN finish_image_url TEXT",
            # ▼ 로컬 파일 경로 저장
            "ALTER TABLE participants ADD COLUMN finish_image_path TEXT",
            # ▼ 추가: 대회별 완주증 URL 템플릿(있으면 사용)
            "ALTER TABLE marathons ADD COLUMN cert_url_template TEXT"
    ]
    
    with get_db() as conn:
        for sql in migrations:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # 컬럼이 이미 존재
        conn.commit()
