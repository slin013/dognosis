# Adds step length detection
import time
import math
from mpu6050 import mpu6050

SAMPLE_RATE = 50
DURATION = 30
MIN_STEP_INTERVAL = 0.35
CALIBRATION_TIME = 3

DOG_LENGTH_IN = 20
STEP_SCALE = 0.55


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

    K = 1.6
    threshold = mean + K * std

    print(f"Calibration complete.")
    print(f"Mean={mean:.3f}, Std={std:.3f}, Threshold={threshold:.3f}")
    print("Starting live step detection...\n")

    steps = 0
    last_step_time = 0
    start_time = time.time()

    step_times = []
    step_lengths = []

    prev_mag = 0


    while time.time() - start_time < DURATION:
        accel = mpu.get_accel_data(g=True)
        mag = accel_magnitude(accel)

        dynamic_mag = abs(mag - mean)
        t = time.time() - start_time

        thresh = max(K * std, 0.15)

        is_peak = (
            dynamic_mag > thresh and
            prev_mag <= thresh
        )

        if is_peak and (time.time() - last_step_time) > MIN_STEP_INTERVAL:
            now = time.time()
            steps += 1

            if step_times:
                dt = now - step_times[-1]
                freq = 1.0 / dt
                freq_norm = min(max(freq / 3.0, 0.6), 1.2)

                step_length = (DOG_LENGTH_IN * STEP_SCALE) / freq_norm
                step_lengths.append(step_length)

                print(
                    f"Step {steps} | "
                    f"dt={dt:.2f}s | "
                    f"len={step_length:.1f} in"
                )
            else:
                print(f"Step {steps}")

            step_times.append(now)
            last_step_time = now

        prev_mag = dynamic_mag
        time.sleep(1 / SAMPLE_RATE)

        print(f"\nTotal steps in {DURATION} seconds: {steps}")

    if step_lengths:
        avg_len = sum(step_lengths) / len(step_lengths)
        print(f"\nAverage step length: {avg_len:.2f} in")
