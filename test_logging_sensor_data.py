# INITIAL TESTING CODE - From Chat - will need to add more filtering
# Imports all sensors libraries, performs sensor data collection for 30 seconds, writes into csv

import time
import csv
import threading
import numpy as np
from updated_heartrate_monitor import HeartRateMonitor
try:
    from temperature_sensor import MLX90614
except ImportError:
    print("Install MLX90614 library: pip3 install mlx90614")
try:
    from mpu6050 import mpu6050
except ImportError:
    print("Install MPU6050 library: pip3 install mpu6050")
# try:
#     import Adafruit_ADS1x15
# except ImportError:
#     print("Install ADS1115 library: pip3 install adafruit-ads1x15")

# --- Optional: Piezo setup using ADS1115 ---
# adc = Adafruit_ADS1x15.ADS1115()
# GAIN = 1  # depends on your sensor

# --- Initialize sensors ---
hrm = HeartRateMonitor(print_raw=False, print_result=True)
# mlx = MLX90614()
mpu = mpu6050(0x68)

# Start heart rate monitoring thread
hrm.start_sensor()

# CSV Logging Setup
csv_file = "dog_harness_data.csv"
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp", "BPM", "Arrhythmia", "Temp_C",
        "Accel_X", "Accel_Y", "Accel_Z", "Piezo_Voltage"
    ])

    print("Starting data collection for 30 seconds...")
    try:
        start_time = time.time()
        while time.time() - start_time < 30:  # 30-second test
            timestamp = time.time()

            # Heart Rate
            bpm = hrm.bpm if hasattr(hrm, "bpm") else 0
            arr = bool(hrm.rr_intervals[-1]) if hrm.rr_intervals else False

            # # Temperature
            # temp = mlx.get_object_1()  # Celsius

            # Motion
            accel = mpu.get_accel_data()
            ax, ay, az = accel['x'], accel['y'], accel['z']

            # # Piezo vibration sensor (Analog via ADS1115)
            # piezo_val = adc.read_adc(0, gain=GAIN)

            # Write to CSV
            # writer.writerow([timestamp, bpm, arr, temp, ax, ay, az, piezo_val])
            writer.writerow([timestamp, bpm, arr, ax, ay, az])

            # Print live values
            # print(f"BPM: {bpm:.1f} | Arrhythmia: {arr} | Temp: {temp:.1f}C | "
            #       f"Accel: ({ax:.2f}, {ay:.2f}, {az:.2f}) | Piezo: {piezo_val}")
            print(f"BPM: {bpm:.1f} | Arrhythmia: {arr} | Accel: ({ax:.2f}, {ay:.2f}, {az:.2f})")

            time.sleep(1)  # 1 Hz logging
    except KeyboardInterrupt:
        print("Data collection interrupted by user.")

# Stop heart rate sensor
# hrm.stop_sensor()
print(f"Data saved to {csv_file}")
print("Testing complete.")
