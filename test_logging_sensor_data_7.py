# Version with thread locking to prevent i2c errors

import time
import sqlite3
from updated_heartrate_monitor_v2 import HeartRateMonitor
from temperature_sensor.temperature_sensor import MLX90614
from dual_IMU_step_counter_2 import DualIMUStepAnalyzer
from datetime import datetime
import threading

# -------------------------
# Config / Thresholds
# -------------------------
from dognosis_db import DB_PATH as DB_NAME

HIGH_TEMP_THRESHOLD = 103.5
LOW_TEMP_THRESHOLD = 99.0
ASYMMETRY_THRESHOLD = 3.0

ARRHYTHMIA_COOLDOWN = 300
LIMP_COOLDOWN = 300
TEMP_COOLDOWN = 300

# -------------------------
# Shared Data
# -------------------------
sensor_data = {
    "bpm": None,
    "arrhythmia": None,
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
    "Arrhythmia": 0,
    "Limp": 0,
    "High Temperature": 0,
    "Low Temperature": 0
}

# -------------------------
# Sensor Manager Thread
# -------------------------
class SensorManager(threading.Thread):
    def __init__(self, hrm, temp_sensor, step_counter, update_interval=0.05):
        super().__init__()
        self.hrm = hrm
        self.temp_sensor = temp_sensor
        self.step_counter = step_counter
        self.running = True
        self.update_interval = update_interval  # seconds

    def run(self):
        while self.running:
            # --- HEART RATE ---
            try:
                bpm = self.hrm.bpm
                arrhythmia = int(self.hrm.arrhythmia_flag)
            except Exception as e:
                print(f"HRM error: {e}")
                bpm = None
                arrhythmia = None

            # --- TEMPERATURE ---
            try:
                temp = self.temp_sensor.readAmbientTemperature()
                rawTemp = self.temp_sensor.PrintRawTemp()
            except Exception as e:
                print(f"Temperature sensor error: {e}")
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
                steps = None
                latest_len = None
                avg_len = None
                asymmetry = None
                limp = None

            # --- Update shared data ---
            with data_lock:
                sensor_data.update({
                    "bpm": bpm,
                    "arrhythmia": arrhythmia,
                    "temperature": temp,
                    "steps": steps,
                    "latest_step_length": latest_len,
                    "avg_step_length": avg_len,
                    "asymmetry": asymmetry,
                    "limp": limp,
                    "raw_temperature": rawTemp
                })

            time.sleep(self.update_interval)

# -------------------------
# Initialize Sensors
# -------------------------
hrm = HeartRateMonitor(print_raw=False, print_result=False)
temp_sensor = MLX90614()
step_counter = DualIMUStepAnalyzer()

step_counter.calibrate()
step_counter.start()
hrm.start_sensor()

# Start sensor manager thread
sensor_manager = SensorManager(hrm, temp_sensor, step_counter)
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
            arrhythmia = sensor_data["arrhythmia"]
            temp = sensor_data["temperature"]
            steps = sensor_data["steps"]
            latest_len = sensor_data["latest_step_length"]
            avg_len = sensor_data["avg_step_length"]
            asymmetry = sensor_data["asymmetry"]
            limp = sensor_data["limp"]
            rawTemp = sensor_data["raw_temperature"]

        # Use placeholders for rawIR and rawRed
        rawIR = None
        rawRed = None

        # -------------------------
        # Insert sensor data
        # -------------------------
        cursor.execute("""
            INSERT INTO sensor_data (
                timestamp, datetime, bpm, arrhythmia, temperature,
                step_count, latest_step_length, avg_step_length,
                asymmetry, limp, raw_ir, raw_red, raw_temperature
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, dt, bpm, arrhythmia, temp,
            steps, latest_len, avg_len,
            asymmetry, limp,
            rawIR, rawRed, rawTemp
        ))

        # -------------------------
        # Flag insertion helper
        # -------------------------
        def insert_flag(flag_type, description):
            cursor.execute("""
                INSERT INTO flags (timestamp, datetime, flag_type, description, is_user_generated)
                VALUES (?, ?, ?, ?, 0)
            """, (timestamp, dt, flag_type, description))

        # -------------------------
        # Automatic Flag Detection
        # -------------------------
        if arrhythmia and timestamp - last_flag_times["Arrhythmia"] > ARRHYTHMIA_COOLDOWN:
            insert_flag("Arrhythmia", "Irregular heartbeat detected.")
            last_flag_times["Arrhythmia"] = timestamp

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

        print(f"BPM={bpm} | Temp={temp} | Arrhythmia={arrhythmia} | Steps={steps} | Limp={limp}")

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    # Stop sensor manager thread
    sensor_manager.running = False
    sensor_manager.join()

    # Stop sensors
    step_counter.stop()
    hrm.stop_sensor()

    # Close database
    conn.close()