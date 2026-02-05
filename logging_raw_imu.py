# Initial Logging of Raw IMU Data to CSV file - should then be analyzed

import time
import csv
import math
from mpu6050 import mpu6050

# Initialize MPU6050
mpu = mpu6050(0x68)

# Output CSV
filename = "imu_data.csv"

print("Starting IMU data collection...")
print("Press CTRL+C to stop.")

with open(filename, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp",
        "ax", "ay", "az",
        "gx", "gy", "gz",
        "accel_magnitude"
    ])

    try:
        while True:
            t = time.time()

            accel = mpu.get_accel_data()
            gyro = mpu.get_gyro_data()

            ax, ay, az = accel['x'], accel['y'], accel['z']
            gx, gy, gz = gyro['x'], gyro['y'], gyro['z']

            # Acceleration magnitude
            accel_mag = math.sqrt(ax**2 + ay**2 + az**2)

            writer.writerow([
                t, ax, ay, az, gx, gy, gz, accel_mag
            ])

            print(f"|a| = {accel_mag:.2f} g")

            time.sleep(0.02)  # 50 Hz

    except KeyboardInterrupt:
        print("\nIMU logging stopped.")

print(f"Data saved to {filename}")
