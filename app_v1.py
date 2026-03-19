# First outline version of UI - using flask

import os
import sqlite3

from flask import Flask, jsonify, render_template, request

from dognosis_db import DB_PATH, ensure_schema

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(_BASE_DIR, "templates-1")
_STATIC_DIR = os.path.join(_BASE_DIR, "static-1")

_TEMPLATE_DIR_1 = _TEMPLATE_DIR
_STATIC_DIR_1 = _STATIC_DIR
_TEMPLATE_DIR_FALLBACK = os.path.join(_BASE_DIR, "templates")
_STATIC_DIR_FALLBACK = os.path.join(_BASE_DIR, "static")

_USE_TEMPLATE_1 = os.path.exists(os.path.join(_TEMPLATE_DIR_1, "index.html"))
_USE_STATIC_1 = os.path.isdir(_STATIC_DIR_1)

if _USE_TEMPLATE_1 and _USE_STATIC_1:
    app = Flask(
        __name__,
        template_folder=_TEMPLATE_DIR_1,
        static_folder=_STATIC_DIR_1,
        static_url_path="/static-1",
    )
else:
    app = Flask(
        __name__,
        template_folder=_TEMPLATE_DIR_FALLBACK,
        static_folder=_STATIC_DIR_FALLBACK,
        static_url_path="/static",
    )


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    ensure_schema(conn)
    return conn

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/live-data")
def live_data():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, bpm, arrhythmia, raw_ir, raw_red
        FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT 300
    """)

    rows = cursor.fetchall()
    conn.close()

    result = [
        {
            "timestamp": r[0],
            "bpm": r[1],
            "arrhythmia": r[2],
            "raw_ir": r[3],
            "raw_red": r[4],
        }
        for r in rows
    ]

    return jsonify(result)


@app.route("/ingest", methods=["POST"])
def ingest():
    """
    Ingest live samples from the Raspberry Pi.
    Accepts either a single JSON object or a list of objects:
    {
      "timestamp": 1710360000,
      "bpm": 85,
      "arrhythmia": 0,
      "raw_ir": 123456,
      "raw_red": 120001
    }
    """
    payload = request.get_json(force=True, silent=True)

    if payload is None:
        return jsonify({"status": "error", "message": "Invalid or missing JSON"}), 400

    # Normalise to list
    if isinstance(payload, dict):
        samples = [payload]
    elif isinstance(payload, list):
        samples = payload
    else:
        return jsonify({"status": "error", "message": "Payload must be object or list"}), 400

    if not samples:
        return jsonify({"status": "error", "message": "No samples provided"}), 400

    conn = get_db()
    cursor = conn.cursor()

    rows = []
    for s in samples:
        try:
            ts = int(s["timestamp"])
            bpm = float(s.get("bpm") or 0)
            arrhythmia = int(s.get("arrhythmia", 0) or 0)
            raw_ir = int(s.get("raw_ir") or 0)
            raw_red = int(s.get("raw_red") or 0)
        except (KeyError, TypeError, ValueError) as exc:
            conn.close()
            return jsonify(
                {
                    "status": "error",
                    "message": f"Bad sample format: {exc}",
                    "sample": s,
                }
            ), 400

        rows.append((ts, bpm, arrhythmia, raw_ir, raw_red))

    cursor.executemany(
        """
        INSERT INTO sensor_data (timestamp, bpm, arrhythmia, raw_ir, raw_red)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "inserted": len(rows)}), 201

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


@app.route("/flags-add", methods=["POST"])
def flags_add():
    """
    Add a user-generated flag (v1 API).
    Expected JSON:
      {
        "timestamp": <unix seconds (number)>,
        "flag_type": "<category string>",
        "description": "<note string>"
      }
    """
    payload = request.get_json(force=True, silent=True) or {}

    ts = payload.get("timestamp")
    flag_type = payload.get("flag_type")
    description = payload.get("description", None)

    if ts is None or flag_type is None or str(flag_type).strip() == "":
        return jsonify({"status": "error", "message": "Missing timestamp or flag_type"}), 400

    try:
        ts_int = int(float(ts))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid timestamp"}), 400

    import datetime as _dt

    dt_str = _dt.datetime.fromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO flags (timestamp, datetime, flag_type, description, is_user_generated)
        VALUES (?, ?, ?, ?, 1)
        """,
        (ts_int, dt_str, str(flag_type), description),
    )
    flag_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "flag_id": flag_id}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)