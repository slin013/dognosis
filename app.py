# Flask UI — reads dog_harness.db (same file as sensor logging scripts)

import os

from flask import Flask, render_template, jsonify
import sqlite3

from dognosis_db import DB_PATH, ensure_schema

app = Flask(
    __name__,
    template_folder="templates-1",
    static_folder="static-1",
    static_url_path="/static-1",
)


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    ensure_schema(conn)
    return conn


@app.route("/")
def index():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT datetime, bpm, high_hr, low_hr, rapid_change, unstable_hr,
               temperature, step_count, timestamp
        FROM sensor_data
        ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    latest = None
    if row:
        latest = {
            "datetime": row[0],
            "bpm": row[1],
            "high_hr": row[2],
            "low_hr": row[3],
            "rapid_change": row[4],
            "unstable_hr": row[5],
            "temperature": row[6],
            "step_count": row[7],
            "timestamp": row[8],
        }

    cursor.execute("""
        SELECT timestamp, datetime, bpm, temperature, step_count
        FROM sensor_data
        ORDER BY timestamp DESC LIMIT 100
    """)
    raw_rows = cursor.fetchall()
    conn.close()

    rows = [
        {
            "timestamp": r[0],
            "datetime": r[1],
            "bpm": r[2],
            "temperature": r[3],
            "step_count": r[4],
        }
        for r in reversed(raw_rows)
    ]

    return render_template("index.html", rows=rows, latest=latest)


@app.route("/live-data")
def live_data():
    """JSON for charts — polled by the UI; always reflects current DB."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, bpm, temperature, step_count,
               high_hr, low_hr, rapid_change, unstable_hr, datetime
        FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT 400
    """)
    raw = cursor.fetchall()
    conn.close()

    data = [
        {
            "timestamp": r[0],
            "bpm": r[1],
            "temperature": r[2],
            "step_count": r[3],
            "high_hr": r[4],
            "low_hr": r[5],
            "rapid_change": r[6],
            "unstable_hr": r[7],
            "datetime": r[8],
        }
        for r in raw
    ]
    return jsonify(data)


@app.route("/flags")
def flags_list():
    """Recent flags for the Overview sidebar."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, flag_type, description
        FROM flags
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    rows = cursor.fetchall()
    conn.close()
    return jsonify(
        [
            {
                "id": r[0],
                "timestamp": r[1],
                "flag_type": r[2],
                "description": r[3],
            }
            for r in rows
        ]
    )


@app.route("/flags-summary")
def flags_summary():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            f.id,
            f.timestamp,
            f.flag_type,
            f.description,
            f.is_user_generated,
            s.bpm,
            s.temperature,
            s.step_count,
            s.limp,
            s.asymmetry
        FROM flags f
        LEFT JOIN sensor_data s
            ON s.timestamp = (
                SELECT sd.timestamp
                FROM sensor_data sd
                WHERE sd.timestamp <= f.timestamp
                ORDER BY sd.timestamp DESC
                LIMIT 1
            )
        ORDER BY f.timestamp DESC
        LIMIT 200
        """
    )

    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]

    conn.close()

    return jsonify([dict(zip(col_names, row)) for row in rows])


if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    _c = sqlite3.connect(DB_PATH)
    ensure_schema(_c)
    _c.close()
    app.run(host="0.0.0.0", port=5000, debug=True)
