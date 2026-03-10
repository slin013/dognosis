# First outline version of UI - using flask

from flask import Flask, jsonify, render_template
import sqlite3

app = Flask(__name__)
DB = "dog_harness.db"

def get_db():
    return sqlite3.connect(DB)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/live-data")
def live_data():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT 300
    """)

    rows = cursor.fetchall()
    conn.close()

    return jsonify(rows)

@app.route("/flags")
def flags():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM flags
        ORDER BY timestamp DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return jsonify(rows)

@app.route("/flag/<int:flag_id>")
def flag_details(flag_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT timestamp FROM flags WHERE id=?", (flag_id,))
    timestamp = cursor.fetchone()[0]

    cursor.execute("""
        SELECT * FROM sensor_data
        WHERE timestamp BETWEEN ? AND ?
    """, (timestamp - 1800, timestamp + 1800))

    rows = cursor.fetchall()
    conn.close()

    return jsonify(rows)

@app.route("/profile")
def profile():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM dog_profile WHERE id=1")
    row = cursor.fetchone()

    conn.close()
    return jsonify(row)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)