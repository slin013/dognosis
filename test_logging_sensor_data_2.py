import time
import csv
from heartrate_sensor.updated_heartrate_monitor import HeartRateMonitor
from temperature_sensor import MLX90614
from step_counter_v2 import StepCounter

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
    #     "Step_Count"
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
            steps = step_counter.steps

            # writer.writerow([
            #     timestamp,
            #     bpm,
            #     arrhythmia,
            #     temp,
            #     steps
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
            #     f"Steps={steps}"
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
