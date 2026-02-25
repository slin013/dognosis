# Instantiates 2 IMU Modules - uses stepcounter, step length modules and performs limp detection

# limp_score = |L - R| / ((L + R)/2)
# Where limp score > 0.2 --> limp likely

# What This Enables Next
    # Now you can:
    # Detect chronic limp
    # Detect fatigue (shortening stride)
    # Detect stress (HR + gait change)
    # Log left vs right stride history

# *********** Important Hardware Reminder *************
    # If both IMUs are 0x68 by default:
    # One must have AD0 pin pulled HIGH → becomes 0x69.
    # Otherwise you need an I2C multiplexer.

import time
from motion_sensor.step_counter_v2 import StepCounter

DURATION = 30
LIMP_THRESHOLD = 0.20  # 20% asymmetry


class DualIMUGaitMonitor:
    def __init__(self, left_addr=0x68, right_addr=0x69, dog_length_in=20):

        self.left = StepCounter(left_addr, dog_length_in)
        self.right = StepCounter(right_addr, dog_length_in)

    def calibrate(self):
        self.left.calibrate()
        self.right.calibrate()

    def start(self):
        self.left.start()
        self.right.start()

    def stop(self):
        self.left.stop()
        self.right.stop()

    def compute_limp_score(self):
        L = self.left.get_average_step_length()
        R = self.right.get_average_step_length()

        if L == 0 or R == 0:
            return 0

        return abs(L - R) / ((L + R) / 2)

    def get_average_step_length(self):
        L = self.left.get_average_step_length()
        R = self.right.get_average_step_length()

        if L == 0 and R == 0:
            return 0

        return (L + R) / 2


if __name__ == "__main__":

    gait = DualIMUGaitMonitor(
        left_addr=0x68,
        right_addr=0x69,
        dog_length_in=20
    )

    gait.calibrate()
    gait.start()

    print("\nMonitoring gait...\n")

    start = time.time()

    while time.time() - start < DURATION:
        time.sleep(2)

        avg_len = gait.get_average_step_length()
        limp_score = gait.compute_limp_score()

        limp_flag = limp_score > LIMP_THRESHOLD

        print(
            f"\nAvg Step Length: {avg_len:.2f} in | "
            f"Limp Score: {limp_score:.2f} | "
            f"Limp Detected: {limp_flag}"
        )

    gait.stop()

    print("\nMonitoring complete.")
