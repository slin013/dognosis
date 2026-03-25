"""
Shared SQLite path + schema so Flask and logger scripts use the same dog_harness.db.
Call ensure_schema() once before queries that need HR flag columns.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dog_harness.db")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Add columns expected by test_logging_sensor_data_9.py and app.py if missing."""
    c = conn.cursor()
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_data'"
    )
    if not c.fetchone():
        return
    c.execute("PRAGMA table_info(sensor_data)")
    sensor_cols = {row[1] for row in c.fetchall()}

    for col, sql_type in (
        ("datetime", "TEXT"),
        ("bpm", "REAL"),
        ("high_hr", "INTEGER DEFAULT 0"),
        ("low_hr", "INTEGER DEFAULT 0"),
        ("rapid_change", "INTEGER DEFAULT 0"),
        ("unstable_hr", "INTEGER DEFAULT 0"),
        ("temperature", "REAL"),
        ("step_count", "INTEGER"),
        ("limp", "INTEGER"),
        ("asymmetry", "REAL"),
    ):
        if col not in sensor_cols:
            try:
                c.execute(f"ALTER TABLE sensor_data ADD COLUMN {col} {sql_type}")
            except sqlite3.OperationalError:
                pass

    c.execute("PRAGMA table_info(flags)")
    flag_cols = {row[1] for row in c.fetchall()}
    if "datetime" not in flag_cols:
        try:
            c.execute("ALTER TABLE flags ADD COLUMN datetime TEXT")
        except sqlite3.OperationalError:
            pass

    if "is_user_generated" not in flag_cols:
        try:
            c.execute("ALTER TABLE flags ADD COLUMN is_user_generated INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dog_profile'"
    )
    if not c.fetchone():
        c.execute(
            """
            CREATE TABLE dog_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                breed TEXT,
                age INTEGER,
                weight REAL,
                size TEXT,
                date_of_birth TEXT,
                breed_code TEXT,
                breed_other TEXT,
                gender TEXT,
                updated_at TEXT
            )
            """
        )
    else:
        c.execute("PRAGMA table_info(dog_profile)")
        dog_cols = {row[1] for row in c.fetchall()}
        for col, sql_type in (
            ("date_of_birth", "TEXT"),
            ("breed_code", "TEXT"),
            ("breed_other", "TEXT"),
            ("gender", "TEXT"),
            ("updated_at", "TEXT"),
        ):
            if col not in dog_cols:
                try:
                    c.execute(f"ALTER TABLE dog_profile ADD COLUMN {col} {sql_type}")
                except sqlite3.OperationalError:
                    pass

    try:
        c.execute("INSERT OR IGNORE INTO dog_profile (id) VALUES (1)")
    except sqlite3.OperationalError:
        pass

    conn.commit()


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    ensure_schema(conn)
    return conn
