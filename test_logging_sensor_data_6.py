# Version with error handling - if one sensor disconnects will not crash whole script

import time
import sqlite3
from updated_heartrate_monitor_v2 import HeartRateMonitor
from temperature_sensor.temperature_sensor import MLX90614
from dual_IMU_step_counter_2 import DualIMUStepAnalyzer
from datetime import datetime

DB_NAME = "dog_harness.db"

HIGH_TEMP_THRESHOLD = 103.5
LOW_TEMP_THRESHOLD = 99.0
ASYMMETRY_THRESHOLD = 3.0

ARRHYTHMIA_COOLDOWN = 300
LIMP_COOLDOWN = 300
TEMP_COOLDOWN = 300

last_flag_times = {
    "Arrhythmia": 0,
    "Limp": 0,
    "High Temperature": 0,
    "Low Temperature": 0
}

# -------------------------
# Initialize Sensors
# -------------------------
hrm = HeartRateMonitor(print_raw=False, print_result=False)
temp_sensor = MLX90614()
step_counter = DualIMUStepAnalyzer()

step_counter.calibrate()
step_counter.start()
hrm.start_sensor()

# -------------------------
# Database
# -------------------------
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

print("Logging data to SQLite...")

try:
    while True:

        timestamp = time.time()
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # -------------------------
        # HEART RATE SENSOR
        # -------------------------
        try:
            bpm = hrm.bpm
            arrhythmia = int(hrm.arrhythmia_flag)
        except Exception as e:
            print(f"HR sensor error: {e}")
            bpm = None
            arrhythmia = None

        # -------------------------
        # TEMPERATURE SENSOR
        # -------------------------
        try:
            temp = temp_sensor.readAmbientTemperature()
            rawTemp = temp_sensor.PrintRawTemp()
        except Exception as e:
            print(f"Temp sensor error: {e}")
            temp = None
            rawTemp = None

        # -------------------------
        # IMU STEP SENSOR
        # -------------------------
        try:
            steps = step_counter.get_total_steps()
            latest_len = step_counter.left.get_latest_step_length()
            avg_len = step_counter.get_average_step_length()
            asymmetry = step_counter.get_step_asymmetry()
            limp = int(step_counter.detect_limp())
        except Exception as e:
            print(f"IMU error: {e}")
            steps = None
            latest_len = None
            avg_len = None
            asymmetry = None
            limp = None

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
        # FLAG INSERT FUNCTION
        # -------------------------
        def insert_flag(flag_type, description):
            cursor.execute("""
                INSERT INTO flags (timestamp, datetime, flag_type, description, is_user_generated)
                VALUES (?, ?, ?, ?, 0)
            """, (timestamp, dt, flag_type, description))

        # -------------------------
        # FLAG DETECTION
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

        print(f"BPM={bpm} | Temp={temp} | Steps={steps} | Limp={limp}")

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    step_counter.stop()
    hrm.stop_sensor()
    conn.close()
