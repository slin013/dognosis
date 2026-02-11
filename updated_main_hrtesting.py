# main.py from chat to be used with updated heartrate monitor for testing with additional filtering

# How to Run (Important) - Steps for running on Pi 4 from Chat
# 1. Enable I²C
# sudo raspi-config


# Enable I2C, then reboot.

# 2. Install Dependencies
# sudo apt update
# sudo apt install python3-scipy python3-numpy

# 3. Run
# python3 main.py

from updated_heartrate_monitor import HeartRateMonitor
import time

print("Sensor starting...")

duration = 30  # seconds

hrm = HeartRateMonitor(
    print_raw=False,
    print_result=True
)

hrm.start_sensor()

try:
    time.sleep(duration)
except KeyboardInterrupt:
    print("Keyboard interrupt detected.")

hrm.stop_sensor()

print("Sensor stopped.")
