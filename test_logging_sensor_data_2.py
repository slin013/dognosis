import time
import csv
from updated_heartrate_monitor import HeartRateMonitor
from temperature_sensor.temperature_sensor import MLX90614
from step_counter_callable import StepCounter

# --- Initialize sensors ---
hrm = HeartRateMonitor(print_raw=False, print_result=False)
temp_sensor = MLX90614()
step_counter = StepCounter()

# Start sensors
step_counter.calibrate()
step_counter.start()
hrm.start_sensor()

csv_file = "dog_harness_data.csv"

with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    # writer.writerow([
    #     "timestamp",
    #     "BPM",
    #     "Arrhythmia",
    #     "Temperature_C",
    #     "Step_Count",
    #     "Latest_Step_Length_in",
    #     "Avg_Step_Length_in"
    # ])
    writer.writerow([
        "timestamp",
        "BPM",
        "Arrhythmia",
        "Step_Count"
    ])

    print("Logging data for 30 seconds...")
    start = time.time()

    try:
        while time.time() - start < 30:
            timestamp = time.time()

            bpm = getattr(hrm, "bpm", 0)
            arrhythmia = (
                hrm.rr_intervals and
                abs(hrm.rr_intervals[-1] - sum(hrm.rr_intervals)/len(hrm.rr_intervals)) > 0
            )

            # temp = temp_sensor.get_object_1()
            # ---- Step Data ----
            steps = step_counter.steps
            latest_len = step_counter.get_latest_step_length()
            avg_len = step_counter.get_average_step_length()

            # writer.writerow([
            #     timestamp,
            #     bpm,
            #     arrhythmia,
            #     temp,
            #     steps,
            #     latest_len,
            #     avg_len
            # ])
            writer.writerow([
                timestamp,
                bpm,
                arrhythmia,
                steps
            ])

            # print(
            #     f"BPM={bpm:.1f} | "
            #     f"Arr={arrhythmia} | "
            #     f"Temp={temp:.1f}C | "
            #     f"Steps={steps} | "
            #     f"LastLen={latest_len:.2f} in | "
            #     f"AvgLen={avg_len:.2f} in"
            # )
            print(
                f"BPM={bpm:.1f} | "
                f"Arr={arrhythmia} | "
                f"Steps={steps}"
            )

            time.sleep(1)

    except KeyboardInterrupt:
        print("Interrupted.")

# Stop threads
step_counter.stop()
hrm.stop_sensor()

print(f"Data saved to {csv_file}")
