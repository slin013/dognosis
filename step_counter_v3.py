# Adds step length detection
import time
import math
from mpu6050 import mpu6050

# -----------------------------
# Dog + sensor parameters
# -----------------------------
SAMPLE_RATE = 60        # dogs need higher temporal resolution
DURATION = 30
CALIBRATION_TIME = 3

# Gait timing (Springer Spaniel walking/trotting)
MIN_STEP_INTERVAL = 0.22   # front leg cadence
MAX_STEP_INTERVAL = 0.7

DOG_WEIGHT_LB = 50
DOG_SHOULDER_IN = 25

# Step-length scaling (empirical)
STEP_SCALE = 0.42   # dogs have shorter effective step than humans

# -----------------------------
# Axis-weighted armpit motion
# -----------------------------
def armpit_motion(accel):
    """
    Emphasize foreleg swing (X) and vertical paw strike (Z)
    """
    return math.sqrt(
        (1.2 * accel['x'])**2 +
        (0.6 * accel['y'])**2 +
        (1.5 * accel['z'])**2
    )


if __name__ == "__main__":
    mpu = mpu6050(0x68)

    print("Calibrating dog baseline motion...")
    calib = []
    start = time.time()

    while time.time() - start < CALIBRATION_TIME:
        a = mpu.get_accel_data(g=True)
        calib.append(armpit_motion(a))
        time.sleep(1 / SAMPLE_RATE)

    mean = sum(calib) / len(calib)
    std = (sum((x - mean)**2 for x in calib) / len(calib))**0.5

    # Dog harness noise is higher → slightly higher K
    K = 2.0
    threshold = max(mean + K * std, 0.18)

    print(f"Calibration complete")
    print(f"Mean={mean:.3f}, Std={std:.3f}, Threshold={threshold:.3f}\n")

    steps = 0
    last_step_time = 0
    start_time = time.time()

    prev_dyn = 0
    prev_derivative = 0

    print("Detecting dog steps...\n")

    while time.time() - start_time < DURATION:
        a = mpu.get_accel_data(g=True)
        mag = armpit_motion(a)

        dyn = mag - mean
        derivative = dyn - prev_dyn
        t = time.time()

        # Impulse-based peak detection
        is_step = (
            dyn > threshold and
            prev_derivative > 0 and
            derivative < 0 and
            MIN_STEP_INTERVAL < (t - last_step_time) < MAX_STEP_INTERVAL
        )

        if is_step:
            steps += 1
            last_step_time = t
            print(f"Step {steps} @ {t - start_time:.2f}s | impulse={dyn:.3f}")

        prev_dyn = dyn
        prev_derivative = derivative
        time.sleep(1 / SAMPLE_RATE)

    print(f"\nTotal detected front-leg steps: {steps}")

    # Convert to distance (front-leg steps ≈ half stride)
    stride_length = DOG_SHOULDER_IN * STEP_SCALE
    distance_in = (steps / 2) * stride_length

    print(f"Estimated distance: {distance_in / 12:.2f} ft")