# NEW Version with updated flask routes for replacing arrythmia with other bpm flags
# Old (working) version renamed --> app_v1.py

from flask import Flask, render_template, jsonify
import sqlite3

app = Flask(__name__)

DB_NAME = "dog_harness.db"

@app.route("/")
def index():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -------------------------
    # Latest sensor data
    # -------------------------
    cursor.execute("""
        SELECT datetime, bpm, high_hr, low_hr, rapid_change, unstable_hr,
               temperature, step_count
        FROM sensor_data
        ORDER BY timestamp DESC LIMIT 1
    """)
    latest = cursor.fetchone()

    # -------------------------
    # Graph data (last 100 points)
    # -------------------------
    cursor.execute("""
        SELECT datetime, bpm, temperature, step_count
        FROM sensor_data
        ORDER BY timestamp DESC LIMIT 100
    """)
    rows = cursor.fetchall()

    conn.close()

    # Reverse for chronological order
    rows = rows[::-1]

    return render_template(
    "index.html",
    rows=rows[::-1],
    latest=latest
                )


@app.route("/flags-summary")
def flags_summary():
    """
    Recent flags enriched with nearby sensor context for the Flags & Insights tab.
    """
    conn = sqlite3.connect(DB_NAME)
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

    data = [dict(zip(col_names, row)) for row in rows]
    return jsonify(data)


if __name__ == "__main__":
    # IMPORTANT: allows access from laptop on same WiFi
    app.run(host="0.0.0.0", port=5000, debug=True)