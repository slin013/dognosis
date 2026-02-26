# RUN ONCE TO CREATE DB : python db_setup.py

import sqlite3

DB_NAME = "dog_harness.db"

def initialize_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -------------------------
    # SENSOR DATA TABLE
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
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
        raw_temperature REAL
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
        size TEXT
    );
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    initialize_database()