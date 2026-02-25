# Should use acceleration magnitude: |a| = rad(ax^2 + ay^2 + az^2) - standard wearable gait analysis
# High Level Logic of step counting algorithm:
    # Read acceleration at 50–100 Hz
    # Compute acceleration magnitude
    # Bandpass filter to walking frequencies
    # Detect peaks
    # Each peak ≈ one step
    # Typical Dog Walking Frequencies
    # Walking: 1.5–3 Hz
    # Trotting/running: 3–6 Hz

import time
import math
import numpy as np
from mpu6050 import mpu6050
from scipy.signal import butter, filtfilt, find_peaks


SAMPLE_RATE = 50        # Hz
DURATION = 30           # seconds
MIN_STEP_INTERVAL = 0.3 # seconds (dogs rarely step faster than this)


def collect_imu_data(mpu, duration=DURATION, fs=SAMPLE_RATE):
    samples = []
    interval = 1.0 / fs
    start_time = time.time()

    while time.time() - start_time < duration:
        accel = mpu.get_accel_data(g=True)

        # Acceleration magnitude (in g)
        mag = math.sqrt(
            accel['x']**2 +
            accel['y']**2 +
            accel['z']**2
        )

        samples.append((time.time(), mag))
        time.sleep(interval)

    return samples


def count_steps(samples):
    magnitudes = [s[1] for s in samples]

    # Adaptive threshold
    mean = sum(magnitudes) / len(magnitudes)
    std = (sum((x - mean)**2 for x in magnitudes) / len(magnitudes))**0.5
    threshold = mean + 0.5 * std

    steps = 0
    last_step_time = 0

    for t, mag in samples:
        if mag > threshold and (t - last_step_time) > MIN_STEP_INTERVAL:
            steps += 1
            last_step_time = t

    return steps


if __name__ == "__main__":
    mpu = mpu6050(0x68)

    print("Collecting IMU data for 30 seconds...")
    data = collect_imu_data(mpu)

    steps = count_steps(data)
    print(f"Total steps in 30 seconds: {steps}")
