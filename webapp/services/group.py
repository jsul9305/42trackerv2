import random
import string
from core.database import get_db

def generate_join_code(length=6):
    """Generates a random alphanumeric join code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        with get_db() as conn:
            cur = conn.execute("SELECT id FROM groups WHERE join_code = ?", (code,))
            if cur.fetchone() is None:
                return code

def create_group(marathon_id: int, name: str) -> dict:
    """Creates a new group for a given marathon."""
    if not marathon_id or not name:
        return {"success": False, "error": "Marathon ID and group name are required."}
    try:
        join_code = generate_join_code()
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO groups (marathon_id, name, join_code) VALUES (?, ?, ?)",
                (marathon_id, name, join_code),
            )
            group_id = cur.lastrowid
            conn.commit()

            cur = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
            group = dict(cur.fetchone())
            return {"success": True, "group": group}
    except Exception as e:
        return {"success": False, "error": str(e)}

def validate_code(join_code: str) -> dict:
    """Finds a group by its join code and returns its details if valid."""
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM groups WHERE join_code = ?", (join_code,))
        row = cur.fetchone()
        if row:
            return {"valid": True, "group": dict(row)}
        else:
            return {"valid": False, "message": "Invalid join code."}

def join_group(join_code: str, bib_number: str) -> dict:
    """Adds a participant to a group using a join code."""
    validation_result = validate_code(join_code)
    if not validation_result["valid"]:
        return {"success": False, "error": "Invalid join code."}
    
    group = validation_result["group"]
    group_id = group["id"]

    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO participants (group_id, nameorbibno, active) VALUES (?, ?, 1)",
                (group_id, bib_number),
            )
            conn.commit()

            if cur.rowcount == 0: # INSERT was ignored, participant already exists
                cur = conn.execute(
                    "SELECT * FROM participants WHERE group_id = ? AND nameorbibno = ?",
                    (group_id, bib_number)
                )
                participant = dict(cur.fetchone())
                return {"success": True, "participant": participant, "existed": True}
            else:
                participant_id = cur.lastrowid
                cur = conn.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
                participant = dict(cur.fetchone())
                return {"success": True, "participant": participant, "existed": False}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_participants_by_group(group_id: int) -> list[dict]:
    """Retrieves all participants for a given group."""
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM participants WHERE group_id = ?", (group_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows]

def get_groups_by_marathon(marathon_id: int) -> list[dict]:
    """Retrieves all groups for a given marathon."""
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM groups WHERE marathon_id = ?", (marathon_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows]

def get_group_by_id(group_id: int) -> dict | None:
    """Finds a group by its ID."""
    with get_db() as conn:
        cur = conn.execute("SELECT g.*, m.name as marathon_name FROM groups g JOIN marathons m ON g.marathon_id = m.id WHERE g.id = ?", (group_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_all_groups() -> list[dict]:
    """Retrieves all groups from all marathons."""
    with get_db() as conn:
        cur = conn.execute("""
            SELECT g.*, m.name as marathon_name 
            FROM groups g
            JOIN marathons m ON g.marathon_id = m.id
            ORDER BY g.created_at DESC
        """)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
