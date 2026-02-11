import time
import csv
from updated_heartrate_monitor import HeartRateMonitor
from temperature_sensor.temperature_sensor import MLX90614
from step_counter_v3 import StepCounter

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
    writer.writerow([
        "timestamp",
        "BPM",
        "Arrhythmia",
        "Temperature_C",
        "Step_Count",
        "Latest_Step_Length_in",
        "Avg_Step_Length_in"
    ])

    print("Logging data for 30 seconds...")
    end_time = time.time() + 30  # Hard stop time

    try:
        while time.time() < end_time:
            timestamp = time.time()

            bpm = getattr(hrm, "bpm", 0)
            if hrm.rr_intervals:
                avg_rr = sum(hrm.rr_intervals) / len(hrm.rr_intervals)
                arrhythmia = abs(hrm.rr_intervals[-1] - avg_rr) > 0
            else:
                arrhythmia = False

            temp = temp_sensor.get_object_1()
            # ---- Step Data ----
            steps = step_counter.steps
            latest_len = step_counter.get_latest_step_length() or 0
            avg_len = step_counter.get_average_step_length() or 0
            writer.writerow([
                timestamp,
                bpm,
                arrhythmia,
                temp,
                steps,
                latest_len,
                avg_len
            ])
            f.flush() 
            
            print(
                f"BPM={bpm:.1f} | "
                f"Arr={arrhythmia} | "
                f"Temp={temp:.1f}C | "
                f"Steps={steps} | "
                f"LastLen={latest_len:.2f} in | "
                f"AvgLen={avg_len:.2f} in"
            )
            

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nInterrupted early — saving data...")

# Stop threads
step_counter.stop()
hrm.stop_sensor()

print(f"Data saved to {csv_file}")
