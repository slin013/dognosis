# Updated version for new bpm flags replacing arrythmia detection

import time
import sqlite3
import threading
from collections import deque
from datetime import datetime

from dognosis_db import DB_PATH as DB_NAME, ensure_schema
from dog_profile_hr import (
    compute_hr_thresholds,
    compute_predicted_hr,
    row_tuple_to_hr_dict,
)
from updated_heartrate_monitor_v3 import HeartRateMonitor
from dual_IMU_step_counter_2 import DualIMUStepAnalyzer

# -------------------------
# Config / Thresholds
# -------------------------

HIGH_TEMP_THRESHOLD = 110
LOW_TEMP_THRESHOLD = 60
ASYMMETRY_THRESHOLD = 3.0

HR_COOLDOWN = 300
LIMP_COOLDOWN = 300
TEMP_COOLDOWN = 300

# Emotional Distress: elevated avg HR over a window with low step activity (placeholders — tune with data)
EMOTIONAL_DISTRESS_WINDOW_SEC = 90
EMOTIONAL_DISTRESS_MAX_STEPS_PER_MIN = 10
EMOTIONAL_DISTRESS_MIN_VALID_BPM_FRACTION = 0.65
EMOTIONAL_DISTRESS_MIN_WINDOW_SAMPLES = 45
EMOTIONAL_DISTRESS_COOLDOWN = 600

# -------------------------
# Shared Data
# -------------------------
sensor_data = {
    "bpm": None,
    "high_hr": 0,
    "low_hr": 0,
    "rapid_change": 0,
    "unstable_hr": 0,
    "temperature": None,
    "steps": None,
    "latest_step_length": None,
    "avg_step_length": None,
    "asymmetry": None,
    "limp": None,
    "raw_temperature": None
}

data_lock = threading.Lock()

last_flag_times = {
    "High HR": 0,
    "Low HR": 0,
    "Rapid HR Change": 0,
    "Unstable HR": 0,
    "Emotional Distress": 0,
    "Limp": 0,
    "High Temperature": 0,
    "Low Temperature": 0,
}

emotional_distress_history = deque()

# -------------------------
# Sensor Manager Thread
# -------------------------
class SensorManager(threading.Thread):
    def __init__(self, hrm, step_counter, update_interval=0.05):
        super().__init__()
        self.hrm = hrm
        self.step_counter = step_counter
        self.running = True
        self.update_interval = update_interval

    def run(self):
        while self.running:
            # --- HEART RATE ---
            try:
                bpm = self.hrm.bpm

            #     # NEW FLAGS FROM HRM
            #     high_hr = int(self.hrm.bpm > 180)
            #     low_hr = int(self.hrm.bpm < 50 and self.hrm.bpm > 0)

            #     if len(self.hrm.bpm_history) >= 2:
            #         rapid_change = int(abs(self.hrm.bpm_history[-1] - self.hrm.bpm_history[-2]) > 30)
            #     else:
            #         rapid_change = 0

            #     if len(self.hrm.bpm_history) >= 5:
            #         unstable_hr = int(max(self.hrm.bpm_history) - min(self.hrm.bpm_history) > 30)
            #     else:
            #         unstable_hr = 0

            except Exception as e:
                print(f"HRM error: {e}")
                bpm = None
                high_hr = low_hr = rapid_change = unstable_hr = None

            # --- TEMPERATURE ---
            try:
                temp = self.step_counter.left.get_temp()
                temp = temp * 9/5 + 32
                rawTemp = temp
            except Exception as e:
                print(f"MPU temperature error: {e}")
                temp = None
                rawTemp = None

            # --- IMU STEP COUNTER ---
            try:
                steps = self.step_counter.get_total_steps()
                latest_len = self.step_counter.left.get_latest_step_length()
                avg_len = self.step_counter.get_average_step_length()
                asymmetry = self.step_counter.get_step_asymmetry()
                limp = int(self.step_counter.detect_limp())
            except Exception as e:
                print(f"IMU error: {e}")
                steps = latest_len = avg_len = asymmetry = limp = None

            # --- Update shared data ---
            with data_lock:
                sensor_data.update({
                    "bpm": bpm,
                    "arrhythmia": None,  # deprecated
                    "temperature": temp,
                    "steps": steps,
                    "latest_step_length": latest_len,
                    "avg_step_length": avg_len,
                    "asymmetry": asymmetry,
                    "limp": limp,
                    "raw_temperature": rawTemp,
                    "high_hr": int(hrm.high_hr_flag),
                    "low_hr": int(hrm.low_hr_flag),
                    "rapid_change": int(hrm.rapid_change_flag),
                    "unstable_hr": int(hrm.unstable_hr_flag)
                })

            time.sleep(self.update_interval)

# -------------------------
# Initialize Sensors
# -------------------------
hrm = HeartRateMonitor(print_raw=False, print_result=False)
step_counter = DualIMUStepAnalyzer()

step_counter.calibrate()
step_counter.start()
hrm.start_sensor()

sensor_manager = SensorManager(hrm, step_counter)
sensor_manager.start()

# -------------------------
# Database Connection
# -------------------------
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()
ensure_schema(conn)

print("Logging data to SQLite...")

try:
    while True:
        timestamp = time.time()
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with data_lock:
            bpm = sensor_data["bpm"]
            high_hr = sensor_data["high_hr"]
            low_hr = sensor_data["low_hr"]
            rapid_change = sensor_data["rapid_change"]
            unstable_hr = sensor_data["unstable_hr"]
            temp = sensor_data["temperature"]
            steps = sensor_data["steps"]
            latest_len = sensor_data["latest_step_length"]
            avg_len = sensor_data["avg_step_length"]
            asymmetry = sensor_data["asymmetry"]
            limp = sensor_data["limp"]
            rawTemp = sensor_data["raw_temperature"]

        cursor.execute(
            "SELECT weight, resting_hr, date_of_birth, breed_code FROM dog_profile WHERE id = 1"
        )
        prof_row = cursor.fetchone()
        prof_cols = [d[0] for d in cursor.description] if cursor.description else []
        profile_dict = row_tuple_to_hr_dict(prof_row, prof_cols) if prof_row else None
        if prof_row:
            pred_hr = compute_predicted_hr(profile_dict)
        else:
            pred_hr = None

        thresholds = compute_hr_thresholds(profile_dict, pred_hr)
        high_threshold = thresholds["high"]
        low_threshold = thresholds["low"]
        emotional_distress_min_avg = thresholds["emotional_distress_min_avg"]
        baseline_type = thresholds["baseline_type"]
        baseline_value = thresholds["baseline_value"]

        if bpm is not None and bpm > 0:
            if high_threshold is not None:
                high_hr = int(bpm > high_threshold)
            if low_threshold is not None:
                low_hr = int(bpm < low_threshold)

        emotional_distress_history.append((timestamp, bpm, steps))
        while (
            emotional_distress_history
            and emotional_distress_history[0][0] < timestamp - EMOTIONAL_DISTRESS_WINDOW_SEC
        ):
            emotional_distress_history.popleft()

        rawIR = None
        rawRed = None

        # -------------------------
        # Insert sensor data
        # -------------------------
        # -------------------------
        cursor.execute("""
            INSERT INTO sensor_data (
                timestamp, datetime, bpm, temperature,
                step_count, latest_step_length, avg_step_length,
                asymmetry, limp, raw_temperature,
                high_hr, low_hr, rapid_change, unstable_hr,
                arrhythmia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            dt,
            bpm,
            temp,
            steps,
            latest_len,
            avg_len,
            asymmetry,
            limp,
            rawTemp,
            int(high_hr),               # dynamic profile/baseline threshold
            int(low_hr),                # dynamic profile/baseline threshold
            int(rapid_change),          # rapid BPM change from monitor
            int(unstable_hr),           # unstable BPM from monitor
            None                        # arrhythmia intentionally left blank
        ))

        # -------------------------
        # Flag helper
        # -------------------------
        def insert_flag(flag_type, description):
            cursor.execute("""
                INSERT INTO flags (timestamp, datetime, flag_type, description, is_user_generated)
                VALUES (?, ?, ?, ?, 0)
            """, (timestamp, dt, flag_type, description))

        # -------------------------
        # HR FLAGS (NEW)
        # -------------------------
        if high_hr and timestamp - last_flag_times["High HR"] > HR_COOLDOWN:
            if bpm is not None and high_threshold is not None:
                if baseline_type and baseline_value is not None:
                    insert_flag(
                        "High HR",
                        f"BPM elevated: {bpm:.1f} (> {high_threshold:.1f}, {baseline_type} baseline {baseline_value:.1f})",
                    )
                else:
                    insert_flag("High HR", f"BPM elevated: {bpm:.1f} (> {high_threshold:.1f})")
            else:
                insert_flag("High HR", f"BPM elevated: {bpm:.1f}")
            last_flag_times["High HR"] = timestamp

        if low_hr and timestamp - last_flag_times["Low HR"] > HR_COOLDOWN:
            if bpm is not None and low_threshold is not None:
                if baseline_type and baseline_value is not None:
                    insert_flag(
                        "Low HR",
                        f"BPM low: {bpm:.1f} (< {low_threshold:.1f}, {baseline_type} baseline {baseline_value:.1f})",
                    )
                else:
                    insert_flag("Low HR", f"BPM low: {bpm:.1f} (< {low_threshold:.1f})")
            else:
                insert_flag("Low HR", f"BPM low: {bpm:.1f}")
            last_flag_times["Low HR"] = timestamp

        if rapid_change and timestamp - last_flag_times["Rapid HR Change"] > HR_COOLDOWN:
            insert_flag("Rapid HR Change", "Sudden BPM spike/drop detected.")
            last_flag_times["Rapid HR Change"] = timestamp

        if unstable_hr and timestamp - last_flag_times["Unstable HR"] > HR_COOLDOWN:
            insert_flag("Unstable HR", "Heart rate unstable over time.")
            last_flag_times["Unstable HR"] = timestamp

        # Emotional Distress: sustained elevated HR with low movement (does not replace Rapid HR Change)
        if len(emotional_distress_history) >= EMOTIONAL_DISTRESS_MIN_WINDOW_SAMPLES:
            pts = list(emotional_distress_history)
            bpms = [p[1] for p in pts if p[1] is not None and p[1] > 0]
            if len(bpms) >= len(pts) * EMOTIONAL_DISTRESS_MIN_VALID_BPM_FRACTION:
                avg_bpm = sum(bpms) / len(bpms)
                step_pts = [(p[0], p[2]) for p in pts if p[2] is not None]
                if len(step_pts) >= 2:
                    t0, s0 = step_pts[0]
                    t1, s1 = step_pts[-1]
                    dur = t1 - t0
                    if dur > 5:
                        steps_per_min = max(0.0, (float(s1) - float(s0)) / dur) * 60.0
                        if (
                            avg_bpm >= emotional_distress_min_avg
                            and steps_per_min <= EMOTIONAL_DISTRESS_MAX_STEPS_PER_MIN
                            and timestamp - last_flag_times["Emotional Distress"] > EMOTIONAL_DISTRESS_COOLDOWN
                        ):
                            insert_flag(
                                "Emotional Distress",
                                f"Elevated avg BPM ({avg_bpm:.0f}) vs threshold {emotional_distress_min_avg:.0f} "
                                f"over {EMOTIONAL_DISTRESS_WINDOW_SEC:.0f}s "
                                f"with low activity (~{steps_per_min:.0f} steps/min).",
                            )
                            last_flag_times["Emotional Distress"] = timestamp

        # -------------------------
        # EXISTING FLAGS
        # -------------------------
        if limp and timestamp - last_flag_times["Limp"] > LIMP_COOLDOWN:
            insert_flag("Limp", "Step asymmetry exceeds threshold.")
            last_flag_times["Limp"] = timestamp

        if temp is not None:
            if temp > HIGH_TEMP_THRESHOLD and timestamp - last_flag_times["High Temperature"] > TEMP_COOLDOWN:
                insert_flag("High Temperature", f"Temperature reached {temp:.2f}F.")
                last_flag_times["High Temperature"] = timestamp

            if temp < LOW_TEMP_THRESHOLD and timestamp - last_flag_times["Low Temperature"] > TEMP_COOLDOWN:
                insert_flag("Low Temperature", f"Temperature dropped to {temp:.2f}F.")
                last_flag_times["Low Temperature"] = timestamp

        conn.commit()

        print(f"BPM={bpm} | Temp={temp} | Steps={steps} | Limp={limp} | High HR = {high_hr}| Low HR = {low_hr} | Unstable HR = {unstable_hr} | Rapid Change in BPM = {rapid_change}")

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    sensor_manager.running = False
    sensor_manager.join()
    step_counter.stop()
    hrm.stop_sensor()
    conn.close()