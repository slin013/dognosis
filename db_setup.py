# RUN ONCE TO CREATE DB : python db_setup.py

import sqlite3

from dognosis_db import DB_PATH

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # -------------------------
    # SENSOR DATA TABLE
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        datetime TEXT,
        bpm REAL,
        arrhythmia INTEGER,
        temperature REAL,
        step_count INTEGER,
        latest_step_length REAL,
        avg_step_length REAL,
        asymmetry REAL,
        limp INTEGER,
        raw_ir REAL,
        raw_red REAL,
        raw_temperature REAL,
        high_hr INTEGER DEFAULT 0,
        low_hr INTEGER DEFAULT 0,
        rapid_change INTEGER DEFAULT 0,
        unstable_hr INTEGER DEFAULT 0,
        core_temp_est_f REAL,
        core_temp_confidence REAL
    );
    """)

    # Timestamp index (CRITICAL for ±30min queries)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
    ON sensor_data(timestamp);
    """)

    # -------------------------
    # FLAGS TABLE
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        datetime TEXT,
        flag_type TEXT NOT NULL,
        description TEXT,
        is_user_generated INTEGER DEFAULT 0
    );
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_flag_timestamp
    ON flags(timestamp);
    """)

    # -------------------------
    # DOG PROFILE TABLE
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dog_profile (
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
    );
    """)

    conn.commit()
    conn.close()
    # Add any columns missing on older DBs
    from dognosis_db import ensure_schema
    _c = sqlite3.connect(DB_PATH)
    ensure_schema(_c)
    _c.close()
    print(f"Database initialized successfully at {DB_PATH}")

if __name__ == "__main__":
    initialize_database()