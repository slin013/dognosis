#  (SQLite version) - switching from local csv data to local sqlite db saving to
#  This will allow for cleaner storage when moving to live updates to website
import time
import sqlite3
from updated_heartrate_monitor import HeartRateMonitor
from temperature_sensor.temperature_sensor import MLX90614
from dual_IMU_step_counter_2 import DualIMUStepAnalyzer

DB_NAME = "dog_harness.db"

# --------------------------------
# Flag Thresholds (EDIT AS NEEDED)
# --------------------------------
HIGH_TEMP_THRESHOLD = 103.5  # Fahrenheit
LOW_TEMP_THRESHOLD = 99.0
ASYMMETRY_THRESHOLD = 3.0    # inches
ARRHYTHMIA_COOLDOWN = 300    # seconds between duplicate flags
LIMP_COOLDOWN = 300
TEMP_COOLDOWN = 300

# Track last flag times to prevent spam
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
# Database Connection
# -------------------------
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

print("Logging data to SQLite...")

try:
    while True:

        timestamp = time.time()

        bpm = hrm.bpm
        arrhythmia = int(hrm.arrhythmia_flag)

        temp = temp_sensor.readAmbientTemperature()

        steps = step_counter.get_total_steps()
        latest_len = step_counter.left.get_latest_step_length()
        avg_len = step_counter.get_average_step_length()
        asymmetry = step_counter.get_step_asymmetry()
        limp = int(step_counter.detect_limp())

        rawIR = hrm.PrintRawIR()
        rawRed = hrm.PrintRawRed()
        rawTemp = temp_sensor.PrintRawTemp()

        # -------------------------
        # Insert sensor data
        # -------------------------
        cursor.execute("""
            INSERT INTO sensor_data (
                timestamp, bpm, arrhythmia, temperature,
                step_count, latest_step_length, avg_step_length,
                asymmetry, limp, raw_ir, raw_red, raw_temperature
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, bpm, arrhythmia, temp,
            steps, latest_len, avg_len,
            asymmetry, limp, rawIR, rawRed, rawTemp
        ))

        # -------------------------
        # Automatic Flag Detection
        # -------------------------

        def insert_flag(flag_type, description):
            cursor.execute("""
                INSERT INTO flags (timestamp, flag_type, description, is_user_generated)
                VALUES (?, ?, ?, 0)
            """, (timestamp, flag_type, description))

        # Arrhythmia
        if arrhythmia and timestamp - last_flag_times["Arrhythmia"] > ARRHYTHMIA_COOLDOWN:
            insert_flag("Arrhythmia", "Irregular heartbeat detected.")
            last_flag_times["Arrhythmia"] = timestamp

        # Limp
        if limp and timestamp - last_flag_times["Limp"] > LIMP_COOLDOWN:
            insert_flag("Limp", "Step asymmetry exceeds threshold.")
            last_flag_times["Limp"] = timestamp

        # High Temperature
        if temp > HIGH_TEMP_THRESHOLD and timestamp - last_flag_times["High Temperature"] > TEMP_COOLDOWN:
            insert_flag("High Temperature", f"Temperature reached {temp:.2f}F.")
            last_flag_times["High Temperature"] = timestamp

        # Low Temperature
        if temp < LOW_TEMP_THRESHOLD and timestamp - last_flag_times["Low Temperature"] > TEMP_COOLDOWN:
            insert_flag("Low Temperature", f"Temperature dropped to {temp:.2f}F.")
            last_flag_times["Low Temperature"] = timestamp

        conn.commit()

        print(f"BPM={bpm:.1f} | Temp={temp:.1f} | Steps={steps} | Limp={limp}")

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    step_counter.stop()
    hrm.stop_sensor()
    conn.close()