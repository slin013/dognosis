import time
from step_counter_v3 import StepCounter

LIMP_PERCENT_THRESHOLD = 0.15   # 15% asymmetry threshold


class DualIMUStepAnalyzer:
    def __init__(self,
                 left_address=0x68,
                 right_address=0x69,
                 dog_length_in=20):

        self.left = StepCounter(address=left_address,
                                dog_length_in=dog_length_in)

        self.right = StepCounter(address=right_address,
                                 dog_length_in=dog_length_in)

        self.dog_length_in = dog_length_in
        self.limp_flag = False

    # ---------------------------------
    # Setup
    # ---------------------------------
    def calibrate(self):
        print("\nCalibrating LEFT IMU")
        self.left.calibrate()

        print("\nCalibrating RIGHT IMU")
        self.right.calibrate()

    def start(self):
        self.left.start()
        self.right.start()

    def stop(self):
        self.left.stop()
        self.right.stop()

    # ---------------------------------
    # Step Metrics
    # ---------------------------------
    def get_total_steps(self):
        return self.left.steps + self.right.steps

    def get_average_step_length(self):
        left_avg = self.left.get_average_step_length()
        right_avg = self.right.get_average_step_length()

        if left_avg == 0 and right_avg == 0:
            return 0

        return (left_avg + right_avg) / 2

    def get_step_asymmetry(self):
        left_avg = self.left.get_average_step_length()
        right_avg = self.right.get_average_step_length()

        return abs(left_avg - right_avg)

    def detect_limp(self):
        asymmetry = self.get_step_asymmetry()

        threshold = self.dog_length_in * LIMP_PERCENT_THRESHOLD

        if asymmetry > threshold:
            self.limp_flag = True
        else:
            self.limp_flag = False

        return self.limp_flag
    

if __name__ == "__main__":

    DURATION = 30

    analyzer = DualIMUStepAnalyzer(
        left_address=0x68,
        right_address=0x69,
        dog_length_in=20
    )

    analyzer.calibrate()
    analyzer.start()

    print("\nRunning dual IMU step detection...\n")

    start = time.time()

    try:
        while time.time() - start < DURATION:
            time.sleep(1)

            total_steps = analyzer.get_total_steps()
            avg_len = analyzer.get_average_step_length()
            asymmetry = analyzer.get_step_asymmetry()
            limp = analyzer.detect_limp()

            print(
                f"TotalSteps={total_steps} | "
                f"AvgLen={avg_len:.2f} in | "
                f"Asymmetry={asymmetry:.2f} | "
                f"Limp={limp}"
            )

    except KeyboardInterrupt:
        print("Interrupted.")

    analyzer.stop()

    print("\n----- SUMMARY -----")
    print(f"Total Steps: {analyzer.get_total_steps()}")
    print(f"Average Step Length: {analyzer.get_average_step_length():.2f} in")
    print(f"Limp Detected: {analyzer.detect_limp()}")