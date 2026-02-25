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