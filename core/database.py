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
  refresh_sec INTEGER NOT NULL DEFAULT 60,
  enabled INTEGER NOT NULL DEFAULT 1,
  cert_url_template TEXT,
  event_date TEXT,
  updated_at TEXT,
  -- 아래 4개 컬럼은 과거 DB에 없을 수 있음 (마이그레이션에서 보장)
  join_code TEXT UNIQUE,
  join_code_expires_at DATETIME,
  join_code_try_window_start DATETIME,
  join_code_try_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  marathon_id INTEGER NOT NULL REFERENCES marathons(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  total_distance_km REAL NOT NULL,
  course_geo_json TEXT,
  UNIQUE(marathon_id, name)
);

CREATE TABLE IF NOT EXISTS groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  marathon_id INTEGER NOT NULL REFERENCES marathons(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  join_code TEXT NOT NULL UNIQUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_groups_marathon ON groups(marathon_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_groups_join_code ON groups(join_code);

CREATE TABLE IF NOT EXISTS participants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  alias TEXT,
  nameorbibno TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  race_label TEXT,
  race_total_km REAL,
  cert_key TEXT,
  finish_image_url TEXT,
  finish_image_path TEXT,
  UNIQUE(group_id, nameorbibno)
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

CREATE TABLE IF NOT EXISTS url_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  template TEXT NOT NULL
);
"""

DEFAULT_TEMPLATES = {
    "Smartchip": "https://smartchip.co.kr/return_data_livephoto.asp?nameorbibno={nameorbibno}&usedata={usedata}",
    "SPCT": "http://time.spct.co.kr/m2.php?{usedata}&BIB_NO={nameorbibno}",
    "MyResult": "https://myresult.co.kr/{usedata}/{nameorbibno}",
}

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """DB 연결 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 외래키 강제 & busy timeout
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()

def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    return any(row["name"] == column for row in cur.fetchall())

def init_database():
    """데이터베이스 초기화"""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        
        # Insert default templates if the table is empty
        count = conn.execute("SELECT COUNT(*) FROM url_templates").fetchone()[0]
        if count == 0:
            for name, template in DEFAULT_TEMPLATES.items():
                conn.execute("INSERT INTO url_templates (name, template) VALUES (?, ?)", (name, template))
        
        conn.commit()

def migrate_database():
    """스키마 마이그레이션"""
    with get_db() as conn:
        # marathons 보강
        for col, ddl in [
            ("cert_url_template", "ALTER TABLE marathons ADD COLUMN cert_url_template TEXT"),
            ("event_date", "ALTER TABLE marathons ADD COLUMN event_date TEXT"),
            ("join_code", "ALTER TABLE marathons ADD COLUMN join_code TEXT UNIQUE"),
            ("join_code_expires_at", "ALTER TABLE marathons ADD COLUMN join_code_expires_at DATETIME"),
            ("join_code_try_window_start", "ALTER TABLE marathons ADD COLUMN join_code_try_window_start DATETIME"),
            ("join_code_try_count", "ALTER TABLE marathons ADD COLUMN join_code_try_count INTEGER DEFAULT 0"),
        ]:
            try:
                if not _column_exists(conn, "marathons", col):
                    conn.execute(ddl)
            except sqlite3.OperationalError:
                pass

        # ✅ join_code 컬럼이 있을 때만 인덱스 생성
        if _column_exists(conn, "marathons", "join_code"):
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_marathons_join_code ON marathons(join_code)")
            except sqlite3.OperationalError:
                pass

        conn.commit()