# Adds step length detection - new version to try - based on step_counter_v2
import time
import math
import threading
from mpu6050 import mpu6050

SAMPLE_RATE = 50
MIN_STEP_INTERVAL = 0.35
CALIBRATION_TIME = 3

# --- Dog scaling parameters ---
# These are tunable and NOT hardcoded to one dog
DEFAULT_STRIDE_FACTOR = 0.45  # stride ≈ 45% of body length


def accel_magnitude(accel):
    return math.sqrt(
        accel['x']**2 +
        accel['y']**2 +
        accel['z']**2
    )


class StepCounter:
    def __init__(self, address=0x68, dog_length_in=20):
        self.mpu = mpu6050(address)

        self.dog_length_in = dog_length_in
        self.stride_factor = DEFAULT_STRIDE_FACTOR

        self.steps = 0
        self.step_times = []
        self.step_lengths = []

        self.last_step_time = 0
        self.running = False

        self.threshold = 0

    # ------------------------
    # Calibration
    # ------------------------
    def calibrate(self):
        print(f"Calibrating IMU at address {hex(self.mpu.address)}...")
        samples = []
        start = time.time()

        while time.time() - start < CALIBRATION_TIME:
            accel = self.mpu.get_accel_data(g=True)
            samples.append(accel_magnitude(accel))
            time.sleep(1 / SAMPLE_RATE)

        mean = sum(samples) / len(samples)
        std = (
            sum((x - mean) ** 2 for x in samples) / len(samples)
        ) ** 0.5

        K = 1.6
        self.threshold = mean + K * std

        print(
            f"Calibration done | "
            f"Threshold={self.threshold:.3f}"
        )

    # ------------------------
    # Start / Stop
    # ------------------------
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    # ------------------------
    # Core detection loop
    # ------------------------
    def _run(self):
        while self.running:
            accel = self.mpu.get_accel_data(g=True)
            mag = accel_magnitude(accel)

            now = time.time()

            if (
                mag > self.threshold and
                (now - self.last_step_time) > MIN_STEP_INTERVAL
            ):
                self._register_step(now)

            time.sleep(1 / SAMPLE_RATE)

    # ------------------------
    # Step registration logic
    # ------------------------
    def _register_step(self, timestamp):
        self.steps += 1

        if self.step_times:
            dt = timestamp - self.step_times[-1]

            # Step frequency (Hz)
            freq = 1.0 / dt if dt > 0 else 0

            # Normalize realistic dog gait range
            # typical walking: 1–3 Hz
            freq_norm = min(max(freq / 3.0, 0.6), 1.3)

            # Step length estimation
            # Based on body length scaling
            step_length = (
                self.dog_length_in *
                self.stride_factor /
                freq_norm
            )

            self.step_lengths.append(step_length)

            print(
                f"[{hex(self.mpu.address)}] "
                f"Step {self.steps} | "
                f"Len={step_length:.2f} in"
            )

        else:
            print(f"[{hex(self.mpu.address)}] Step {self.steps}")

        self.step_times.append(timestamp)
        self.last_step_time = timestamp

    # ------------------------
    # Public getters
    # ------------------------
    def get_latest_step_length(self):
        if self.step_lengths:
            return self.step_lengths[-1]
        return 0

    def get_average_step_length(self):
        if self.step_lengths:
            return sum(self.step_lengths) / len(self.step_lengths)
        return 0


# MAIN (only runs if script executed directly)
# =========================================================
if __name__ == "__main__":

    DURATION = 30

    step_counter = StepCounter(dog_length_in=20)

    step_counter.calibrate()
    step_counter.start()

    print("\nRunning step detection for 30 seconds...\n")

    start_time = time.time()

    try:
        while time.time() - start_time < DURATION:
            time.sleep(1)

            latest_len = step_counter.get_latest_step_length()
            avg_len = step_counter.get_average_step_length()

            print(
                f"[LIVE] Steps={step_counter.steps} | "
                f"LastLen={latest_len:.2f} in | "
                f"AvgLen={avg_len:.2f} in"
            )

    except KeyboardInterrupt:
        print("Interrupted by user.")

    step_counter.stop()

    print("\n----- SUMMARY -----")
    print(f"Total Steps: {step_counter.steps}")
    print(f"Average Step Length: {step_counter.get_average_step_length():.2f} in")
    print("Done.")