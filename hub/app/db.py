import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from pathlib import Path

# Database file path — stored in project root
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "app.db"
SCHEMA_PATH = BASE_DIR / "app" / "schema.sql"


@contextmanager
def get_db():
    """Get a database connection — use with 'with' statement"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # So rows act like dicts
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(force: bool = False):
    """Create tables from schema.sql — run once at startup"""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"schema.sql not found at {SCHEMA_PATH}")
    
    # Skip if DB already exists unless forced
    if DB_PATH.exists() and not force:
        print(f"✅ Database already exists at {DB_PATH}")
        return
    
    # Read and execute schema
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(schema)
        print(f"✅ Database initialized at {DB_PATH}")
    finally:
        conn.close()


def seed_students(students_data: List[Dict[str, Any]]):
    """Bulk insert student data from Registrar"""
    with get_db() as db:
        for s in students_data:
            db.execute("""
                INSERT OR REPLACE INTO students 
                (student_id, program_code, year_level, status, first_name, last_name)
                VALUES (:student_id, :program_code, :year_level, :status, :first_name, :last_name)
            """, s)
    print(f"✅ Seeded {len(students_data)} students")


def get_all_students(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch all students from local DB"""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM students ORDER BY last_name, first_name")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_student(student_id: str) -> Optional[Dict[str, Any]]:
    """Fetch one student by ID"""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
