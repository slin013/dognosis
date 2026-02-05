import time
import threading
import csv
from max30102 import MAX30102

class HeartRateMonitor:
    def __init__(self, fs=100):
        self.fs = fs                      # sampling rate (Hz)
        self.sensor = MAX30102()
        self.running = False

        # Store raw data here
        self.raw_data = []   # list of (timestamp, ir)

    def start_sensor(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop_sensor(self):
        self.running = False
        self.thread.join()

    def _run(self):
        start_time = time.time()

        while self.running:
            red, ir = self.sensor.read_fifo()
            timestamp = time.time() - start_time

            # Save RAW data
            self.raw_data.append((timestamp, ir))

            # Optional live print
            print(f"{timestamp:.4f}, {ir}")

            time.sleep(1 / self.fs)

    def export_to_csv(self, filename="raw_heartrate_data.csv"):
        """
        Exports raw IR data to CSV.
        Columns: timestamp (seconds), ir_adc_value
        """
        with open(filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp_sec", "ir_value"])
            writer.writerows(self.raw_data)

        print(f"Saved {len(self.raw_data)} samples to {filename}")
