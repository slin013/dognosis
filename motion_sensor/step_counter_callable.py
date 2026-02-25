# uses logic from step_counter_v2 - but makes it a callable script rather than standalone

import time
import math
import threading
from mpu6050 import mpu6050

SAMPLE_RATE = 50
MIN_STEP_INTERVAL = 0.35
CALIBRATION_TIME = 3


def accel_magnitude(accel):
    return math.sqrt(
        accel['x']**2 +
        accel['y']**2 +
        accel['z']**2
    )


class StepCounter:
    def __init__(self, address=0x68):
        self.mpu = mpu6050(address)

        self.steps = 0
        self.last_step_time = 0
        self.running = False

        self.mean = 0
        self.std = 0
        self.threshold = 0

    def calibrate(self):
        print("Calibrating step detector...")
        samples = []
        start = time.time()

        while time.time() - start < CALIBRATION_TIME:
            accel = self.mpu.get_accel_data(g=True)
            samples.append(accel_magnitude(accel))
            time.sleep(1 / SAMPLE_RATE)

        self.mean = sum(samples) / len(samples)
        self.std = (
            sum((x - self.mean) ** 2 for x in samples) / len(samples)
        ) ** 0.5

        K = 1.6
        self.threshold = self.mean + K * self.std

        print(
            f"Step calibration done | "
            f"Mean={self.mean:.3f}, Std={self.std:.3f}, "
            f"Threshold={self.threshold:.3f}"
        )

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def _run(self):
        while self.running:
            accel = self.mpu.get_accel_data(g=True)
            mag = accel_magnitude(accel)

            now = time.time()
            if (
                mag > self.threshold and
                (now - self.last_step_time) > MIN_STEP_INTERVAL
            ):
                self.steps += 1
                self.last_step_time = now
                print(f"Step detected | total={self.steps}")

            time.sleep(1 / SAMPLE_RATE)
