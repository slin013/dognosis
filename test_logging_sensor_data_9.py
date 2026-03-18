# Updated version for new bpm flags replacing arrythmia detection

import time
import sqlite3
import threading
from datetime import datetime

from dognosis_db import DB_PATH as DB_NAME
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
    "Limp": 0,
    "High Temperature": 0,
    "Low Temperature": 0
}

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
            int(hrm.high_hr_flag),      # 1 if high HR, else 0
            int(hrm.low_hr_flag),       # 1 if low HR, else 0
            int(hrm.rapid_change_flag), # 1 if rapid BPM change, else 0
            int(hrm.unstable_hr_flag),  # 1 if unstable HR, else 0
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
            insert_flag("High HR", f"BPM elevated: {bpm:.1f}")
            last_flag_times["High HR"] = timestamp

        if low_hr and timestamp - last_flag_times["Low HR"] > HR_COOLDOWN:
            insert_flag("Low HR", f"BPM low: {bpm:.1f}")
            last_flag_times["Low HR"] = timestamp

        if rapid_change and timestamp - last_flag_times["Rapid HR Change"] > HR_COOLDOWN:
            insert_flag("Rapid HR Change", "Sudden BPM spike/drop detected.")
            last_flag_times["Rapid HR Change"] = timestamp

        if unstable_hr and timestamp - last_flag_times["Unstable HR"] > HR_COOLDOWN:
            insert_flag("Unstable HR", "Heart rate unstable over time.")
            last_flag_times["Unstable HR"] = timestamp

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