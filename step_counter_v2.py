import time
import math
from mpu6050 import mpu6050

SAMPLE_RATE = 50        # Hz
DURATION = 30           # seconds
MIN_STEP_INTERVAL = 0.3 # seconds


def collect_imu_data(mpu, duration=DURATION, fs=SAMPLE_RATE):
    samples = []
    interval = 1.0 / fs
    start_time = time.time()

    while time.time() - start_time < duration:
        accel = mpu.get_accel_data(g=True)

        mag = math.sqrt(
            accel['x']**2 +
            accel['y']**2 +
            accel['z']**2
        )

        samples.append((time.time(), mag))
        time.sleep(interval)

    return samples


def count_steps(samples, verbose=True):
    magnitudes = [s[1] for s in samples]

    mean = sum(magnitudes) / len(magnitudes)
    std = (sum((x - mean)**2 for x in magnitudes) / len(magnitudes))**0.5
    threshold = mean + 0.5 * std

    steps = 0
    last_step_time = 0

    for t, mag in samples:
        if mag > threshold and (t - last_step_time) > MIN_STEP_INTERVAL:
            steps += 1
            last_step_time = t

            if verbose:
                print(f"Step {steps} detected at t={t:.2f}s (mag={mag:.3f})")

    return steps


if __name__ == "__main__":
    mpu = mpu6050(0x68)

    print("Collecting IMU data for 30 seconds...")
    data = collect_imu_data(mpu)

    print("Analyzing steps...")
    total_steps = count_steps(data, verbose=True)

    print(f"\nTotal steps in 30 seconds: {total_steps}")
