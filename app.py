# Flask UI — reads dog_harness.db (same file as sensor logging scripts)

import os

from flask import Flask, jsonify, render_template, request
import sqlite3

from dognosis_db import DB_PATH, ensure_schema

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(_BASE_DIR, "templates-1")
_STATIC_DIR = os.path.join(_BASE_DIR, "static-1")

# Use absolute paths so this works even if the working directory differs
# across Pi devices. Also fall back to default `templates/` + `static/`
# if `templates-1/` or `static-1/` are missing on another device.
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


@app.route("/incident-context/<int:flag_id>")
def incident_context(flag_id):
    """Full sensor log around one incident (default: ±15 minutes)."""
    window_minutes_raw = request.args.get("window_minutes", default="15")
    try:
        window_minutes = int(window_minutes_raw)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid window_minutes"}), 400

    # Keep bounds sensible for UI usage and DB safety.
    if window_minutes < 1 or window_minutes > 120:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "window_minutes must be between 1 and 120",
                }
            ),
            400,
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, timestamp, flag_type FROM flags WHERE id = ?", (flag_id,))
    flag_row = cursor.fetchone()
    if not flag_row:
        conn.close()
        return jsonify({"status": "error", "message": "Incident not found"}), 404

    incident_ts = int(float(flag_row[1]))
    window_seconds = window_minutes * 60
    start_ts = incident_ts - window_seconds
    end_ts = incident_ts + window_seconds

    cursor.execute(
        """
        SELECT
            id,
            timestamp,
            datetime,
            bpm,
            temperature,
            step_count,
            limp,
            asymmetry,
            high_hr,
            low_hr,
            rapid_change,
            unstable_hr,
            arrhythmia,
            latest_step_length,
            avg_step_length,
            raw_ir,
            raw_red,
            raw_temperature
        FROM sensor_data
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp ASC
        """,
        (start_ts, end_ts),
    )
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    conn.close()

    return jsonify(
        {
            "incident": {
                "id": flag_row[0],
                "timestamp": incident_ts,
                "flag_type": flag_row[2],
            },
            "window_minutes": window_minutes,
            "window_start": start_ts,
            "window_end": end_ts,
            "samples": [dict(zip(col_names, row)) for row in rows],
        }
    )


@app.route("/flags-add", methods=["POST"])
def flags_add():
    """
    Add a user-generated flag.
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

    # Convert to a human readable datetime for the DB
    # (store local time string; display uses JS locale formatting anyway)
    dt_str = None
    try:
        import datetime as _dt

        dt_str = _dt.datetime.fromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        dt_str = None

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


@app.route("/flags-update", methods=["POST"])
def flags_update():
    """
    Update a user-generated flag.
    Expected JSON:
      { "id": <flag_id>, "timestamp": <unix seconds>, "flag_type": "<category>", "description": "<note>" }
    """
    payload = request.get_json(force=True, silent=True) or {}

    flag_id = payload.get("id")
    ts = payload.get("timestamp")
    flag_type = payload.get("flag_type")
    description = payload.get("description", None)

    if flag_id is None or ts is None or flag_type is None or str(flag_type).strip() == "":
        return jsonify({"status": "error", "message": "Missing id/timestamp/flag_type"}), 400

    try:
        flag_id_int = int(float(flag_id))
        ts_int = int(float(ts))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid id or timestamp"}), 400

    import datetime as _dt
    dt_str = _dt.datetime.fromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE flags
        SET timestamp = ?, datetime = ?, flag_type = ?, description = ?
        WHERE id = ? AND is_user_generated = 1
        """,
        (ts_int, dt_str, str(flag_type), description, flag_id_int),
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"status": "error", "message": "Flag not found or not user-generated"}), 404

    return jsonify({"status": "ok", "flag_id": flag_id_int}), 200


@app.route("/flags-delete", methods=["POST"])
def flags_delete():
    """
    Delete a user-generated flag.
    Expected JSON: { "id": <flag_id> }
    """
    payload = request.get_json(force=True, silent=True) or {}
    flag_id = payload.get("id")

    if flag_id is None:
        return jsonify({"status": "error", "message": "Missing id"}), 400

    try:
        flag_id_int = int(float(flag_id))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid id"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM flags
        WHERE id = ? AND is_user_generated = 1
        """,
        (flag_id_int,),
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted == 0:
        return jsonify({"status": "error", "message": "Flag not found or not user-generated"}), 404

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    _c = sqlite3.connect(DB_PATH)
    ensure_schema(_c)
    _c.close()
    app.run(host="0.0.0.0", port=5000, debug=True)
