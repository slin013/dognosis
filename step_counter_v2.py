import time
import math
from collections import deque
from mpu6050 import mpu6050

SAMPLE_RATE = 50        # Hz
DURATION = 30           # seconds
MIN_STEP_INTERVAL = 0.35  # seconds (helps suppress double counts)
CALIBRATION_TIME = 3     # seconds


def accel_magnitude(accel):
    return math.sqrt(
        accel['x']**2 +
        accel['y']**2 +
        accel['z']**2
    )


if __name__ == "__main__":
    mpu = mpu6050(0x68)

    print("Calibrating baseline motion...")
    calib_samples = []
    start = time.time()

    while time.time() - start < CALIBRATION_TIME:
        accel = mpu.get_accel_data(g=True)
        calib_samples.append(accel_magnitude(accel))
        time.sleep(1 / SAMPLE_RATE)

    mean = sum(calib_samples) / len(calib_samples)
    std = (sum((x - mean)**2 for x in calib_samples) / len(calib_samples))**0.5

    # Adaptive threshold multiplier
    K = 1.6
    threshold = mean + K * std

    print(f"Calibration complete.")
    print(f"Mean={mean:.3f}, Std={std:.3f}, Threshold={threshold:.3f}")
    print("Starting live step detection...\n")

    steps = 0
    last_step_time = 0
    start_time = time.time()

    while time.time() - start_time < DURATION:
        accel = mpu.get_accel_data(g=True)
        mag = accel_magnitude(accel)
        t = time.time() - start_time

        if mag > threshold and (time.time() - last_step_time) > MIN_STEP_INTERVAL:
            steps += 1
            last_step_time = time.time()
            print(f"Step {steps} at {t:.2f}s | mag={mag:.3f}")

        time.sleep(1 / SAMPLE_RATE)

    print(f"\nTotal steps in {DURATION} seconds: {steps}")

