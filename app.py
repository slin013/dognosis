# Flask UI — reads dog_harness.db (same file as sensor logging scripts)

import os
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, jsonify, render_template, request
import sqlite3

from dognosis_db import DB_PATH, connect as get_db
from dog_profile_hr import age_days_from_dob

BREED_LABELS = {
    "border_collie": "Border Collie",
    "ckcs": "Cavalier King Charles Spaniel (CKCS)",
    "golden_retriever": "Golden Retriever",
    "labrador_retriever": "Labrador Retriever",
    "springer_spaniel": "Springer Spaniel",
    "staffordshire_bull_terrier": "Staffordshire Bull Terrier",
    "west_highland_white_terrier": "West Highland White Terrier",
    "yorkshire_terrier": "Yorkshire Terrier",
    "other": "Other (not used in HR estimate)",
}


def _breed_display(breed_code: Optional[str], breed_other: Optional[str]) -> str:
    code = (breed_code or "").strip()
    other = (breed_other or "").strip()
    if code == "other" and other:
        return other
    if code == "other":
        return "Other"
    return BREED_LABELS.get(code, code or "")


def _age_years_from_dob(dob_str: Optional[str]) -> Optional[int]:
    ad = age_days_from_dob(dob_str)
    if ad is None:
        return None
    return int(ad // 365.25)

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
    cursor.execute(
        """
        SELECT id, timestamp, flag_type, description
        FROM flags
        WHERE flag_type != 'Arrhythmia'
        ORDER BY timestamp DESC
        LIMIT 50
        """
    )
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
        WHERE f.flag_type != 'Arrhythmia'
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
            unstable_hr
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


@app.route("/dog-profile", methods=["GET", "POST"])
def dog_profile():
    """
    Single-row dog profile (id=1). JSON uses same keys as the dashboard localStorage shape.
    """
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "GET":
        cursor.execute(
            """
            SELECT name, weight, date_of_birth, breed_code, breed_other, gender
            FROM dog_profile WHERE id = 1
            """
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify(
                {
                    "dogName": "",
                    "dogWeightKg": None,
                    "dogDateOfBirth": "",
                    "dogBreedSelect": "",
                    "dogBreedOther": "",
                    "dogGender": "male",
                }
            )
        name, weight, dob, breed_code, breed_other, gender = row
        return jsonify(
            {
                "dogName": name or "",
                "dogWeightKg": weight,
                "dogDateOfBirth": dob or "",
                "dogBreedSelect": breed_code or "",
                "dogBreedOther": breed_other or "",
                "dogGender": gender or "male",
            }
        )

    payload = request.get_json(force=True, silent=True) or {}
    dog_name = str(payload.get("dogName") or "").strip()
    dog_weight = payload.get("dogWeightKg")
    dog_dob = str(payload.get("dogDateOfBirth") or "").strip()
    breed_code = str(payload.get("dogBreedSelect") or "").strip()
    breed_other = str(payload.get("dogBreedOther") or "").strip()
    gender = str(payload.get("dogGender") or "male").strip() or "male"

    weight_val = None
    if dog_weight is not None and dog_weight != "":
        try:
            weight_val = float(dog_weight)
        except (TypeError, ValueError):
            weight_val = None

    breed_display = _breed_display(breed_code, breed_other)
    age_years = _age_years_from_dob(dog_dob if dog_dob else None)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cursor.execute(
        """
        UPDATE dog_profile SET
            name = ?,
            breed = ?,
            age = ?,
            weight = ?,
            date_of_birth = ?,
            breed_code = ?,
            breed_other = ?,
            gender = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            dog_name,
            breed_display,
            age_years,
            weight_val,
            dog_dob or None,
            breed_code or None,
            breed_other or None,
            gender,
            updated,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    get_db().close()
    app.run(host="0.0.0.0", port=5000, debug=True)
