# Plot and analyze raw IMU data
# You should clearly see:
# Flat line → resting
# Periodic oscillation → walking
# Large spikes → running/jumping

import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("imu_data.csv")

plt.figure()
plt.plot(df["timestamp"], df["accel_magnitude"])
plt.xlabel("Time")
plt.ylabel("Acceleration Magnitude (g)")
plt.title("Dog Harness IMU Signal")
plt.show()
