# Should use acceleration magnitude: |a| = rad(ax^2 + ay^2 + az^2) - standard wearable gait analysis
# High Level Logic of step counting algorithm:
    # Read acceleration at 50–100 Hz
    # Compute acceleration magnitude
    # Bandpass filter to walking frequencies
    # Detect peaks
    # Each peak ≈ one step
    # Typical Dog Walking Frequencies
    # Walking: 1.5–3 Hz
    # Trotting/running: 3–6 Hz

import time
import math
import numpy as np
from mpu6050 import mpu6050
from scipy.signal import butter, filtfilt, find_peaks

# --- Parameters ---
FS = 50  # sampling frequency (Hz)
LOWCUT = 1.0
HIGHCUT = 5.0
WINDOW_SIZE = FS * 5  # 5-second window

# --- Bandpass filter ---
def bandpass_filter(data, fs=FS, low=LOWCUT, high=HIGHCUT):
    b, a = butter(2, [low/(fs/2), high/(fs/2)], btype='band')
    return filtfilt(b, a, data)

# --- Initialize IMU ---
mpu = mpu6050(0x68)

accel_buffer = []
step_count = 0

print("Step counter running... CTRL+C to stop")

try:
    while True:
        accel = mpu.get_accel_data()
        ax, ay, az = accel['x'], accel['y'], accel['z']

        accel_mag = math.sqrt(ax**2 + ay**2 + az**2)
        accel_buffer.append(accel_mag)

        if len(accel_buffer) > WINDOW_SIZE:
            accel_buffer.pop(0)

        if len(accel_buffer) == WINDOW_SIZE:
            filtered = bandpass_filter(np.array(accel_buffer))

            peaks, _ = find_peaks(
                filtered,
                distance=int(0.3 * FS),  # min time between steps
                prominence=0.1
            )

            step_count = len(peaks)

            print(f"Estimated steps (last 5s): {step_count}")

        time.sleep(1 / FS)

except KeyboardInterrupt:
    print("\nStopped.")
