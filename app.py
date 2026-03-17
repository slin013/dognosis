# NEW Version with updated flask routes for replacing arrythmia with other bpm flags
# Old (working) version renamed --> app_v1.py

from flask import Flask, render_template
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


if __name__ == "__main__":
    # IMPORTANT: allows access from laptop on same WiFi
    app.run(host="0.0.0.0", port=5000, debug=True)