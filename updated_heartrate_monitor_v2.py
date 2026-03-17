# heartrate_monitor.py
# Improved version
# Fixes:
# - BPM resets to 0 when finger not detected

# TO DO:
# - Test this script with reset to 0 logic
# - If works change arrythmia logic to irregular heart rate 

import time
import threading
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
from heartrate_sensor.max30102 import MAX30102


def bandpass_filter(signal, fs=100, low=1.0, high=4.0):
    b, a = butter(2, [low / (fs / 2), high / (fs / 2)], btype='band')
    return filtfilt(b, a, signal)


def detect_arrhythmia(rr_intervals):
    if len(rr_intervals) < 5:
        return False

    rr_mean = np.mean(rr_intervals)
    for rr in rr_intervals:
        if abs(rr - rr_mean) > 0.3 * rr_mean:
            return True
    return False


class HeartRateMonitor:
    starting_BPM = 0

    def __init__(self, print_raw=False, print_result=True):
        self.print_raw = print_raw
        self.print_result = print_result

        self.sensor = MAX30102()
        self.running = False

        self.ir_buffer = []
        self.rr_intervals = []
        self.last_peak_time = None

        self.fs = 100  # Hz
        self.buffer_size = self.fs * 10  # 10 seconds

        self.bpm = self.starting_BPM
        self.arrhythmia_flag = False

    def start_sensor(self):
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop_sensor(self):
        self.running = False
        self.thread.join()

    def _run(self):
        while self.running:
            red, ir = self.sensor.read_fifo()

            # Basic signal quality check
            if ir < 5000 or np.std(self.ir_buffer[-50:]) < 50:
                # No finger/contact detected → reset values
                self.ir_buffer.clear()
                self.rr_intervals.clear()
                self.last_peak_time = None

                self.bpm = 0
                self.arrhythmia_flag = False

                if self.print_result:
                    print("No contact - BPM: 0")

                time.sleep(1 / self.fs)
                continue
            self.ir_buffer.append(ir)

            if len(self.ir_buffer) > self.buffer_size:
                self.ir_buffer.pop(0)

            if len(self.ir_buffer) == self.buffer_size:
                self.process_signal()

            time.sleep(1 / self.fs)

    def process_signal(self):
        signal = np.array(self.ir_buffer)

        # Remove DC offset
        signal = signal - np.mean(signal)

        # Filter for dog heart rate range
        filtered = bandpass_filter(signal, fs=self.fs)

        # Detect peaks
        peaks, _ = find_peaks(filtered, distance=int(self.fs * 0.4))

        if len(peaks) < 2:
            self.bpm = 0
            self.arrhythmia_flag = False
            return

        peak_times = peaks / self.fs
        rr_intervals = np.diff(peak_times)

        # Save RR intervals
        self.rr_intervals.extend(rr_intervals)
        self.rr_intervals = self.rr_intervals[-30:]

        self.bpm = 60 / np.mean(rr_intervals)
        # can try changing bpm calculations to the following - might be safer if noise sneaks in
        # if len(rr_intervals) > 0:
        #     self.bpm = 60 / np.median(rr_intervals)
        # else:
        #     self.bpm = 0
        self.arrhythmia_flag = detect_arrhythmia(self.rr_intervals)
        if self.print_raw:
            print(filtered[-1])

        if self.print_result:
            print(f"BPM: {self.bpm:.1f} | Arrhythmia Flag: {self.arrhythmia_flag}")
