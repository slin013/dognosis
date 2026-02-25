# Update to include live graphing

import time
import csv
import os
from updated_heartrate_monitor import HeartRateMonitor
import matplotlib.pyplot as plt
from collections import deque

# --- Initialize sensors ---
hrm = HeartRateMonitor(print_raw=False, print_result=False)
rawIR = 0
rawRed = 0
rawTemp = 0

# Start sensors
hrm.start_sensor()

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
csv_file = f"HRONLYdog_harness_data__{timestamp}.csv"

file_exists = os.path.isfile(csv_file)

with open(csv_file, "a", newline="") as f:
    writer = csv.writer(f)
    # Only write header if file does not already exist
    if not file_exists:
        writer.writerow([
            "timestamp",
            "BPM",
            "Arrhythmia",
            #"Temperature_C",
            #"Step_Count",
            #"Latest_Step_Length_in",
            #"Avg_Step_Length_in",
            #"Asymmetry",
            #"Limp",
            "raw-ir",
            "raw-red",
            #"raw-temperature",
        ])

    print("Logging data for 600 seconds...")
    end_time = time.time() + 600  # Hard stop time
    # ---- Setup Live Plot ----
    plt.ion()

    fig, axs = plt.subplots(1, 1, figsize=(8, 10), sharex=True)

    time_data = []
    bpm_data = []
    #temp_data = []
    #step_data = []
    #step_len_data = []
    #asymmetry_data = []

    axs[0].set_title("Heart Rate (BPM)")
    #axs[1].set_title("Temperature")
    #axs[2].set_title("Step Count")
    #axs[3].set_title("Step Length (inches)")

    for ax in axs:
        ax.grid(True)

    plt.tight_layout()

    try:
        while time.time() < end_time:
            timestamp = time.time()

            bpm = hrm.bpm
            arrhythmia = hrm.arrhythmia_flag

            # raw hr data
            rawIR = hrm.PrintRawIR()
            rawRed = hrm.PrintRawRed()
            rawTemp = temp_sensor.PrintRawTemp()


            temp = temp_sensor.readAmbientTemperature()
            # ---- Step Data ----
            writer.writerow([
                timestamp,
                bpm,
                arrhythmia,
                rawIR,
                rawRed,
            ])

            # ---- Store Data ----
            elapsed = time.time() - (end_time - 600)

            time_data.append(elapsed)
            bpm_data.append(bpm)

            # ---- Update Plots ----
            axs[0].cla()
            #axs[1].cla()
            #axs[2].cla()
            #axs[3].cla()

            axs[0].plot(time_data, bpm_data)
            axs[0].set_title("Heart Rate (BPM)")

            """
            axs[1].plot(time_data, temp_data)
            axs[1].set_title("Temperature (F)")

            #axs[2].plot(time_data, step_data)
            axs[2].set_title("Step Count")

            axs[3].plot(time_data, step_len_data)
            axs[3].set_title("Avg Step Length (in)")
            """

            plt.pause(0.01)

            f.flush()

            print(
                f"BPM={bpm:.1f} | "
                f"Arr={arrhythmia} | "
                #f"Temp={temp:.1f}F | "
                #f"Steps={steps} | "
                #f"LastLen={latest_len:.2f} in | "
                #f"AvgLen={avg_len:.2f} in | "
                #f"Asymmetry={asymmetry:.2f} | "
                #f"Limp={limp} "

            )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nInterrupted early — saving data...")

# Stop threads
hrm.stop_sensor()

print(f"Data saved to {csv_file}")
