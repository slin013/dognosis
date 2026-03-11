# heartrate_monitor.py
# Improved version
# Fixes:
# - BPM resets to 0 when finger not detected
# - More robust arrhythmia detection
# - Noise peak filtering
# - Prevent unrealistic BPM spikes

import time
import threading
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
from heartrate_sensor.max30102 import MAX30102


def bandpass_filter(signal, fs=100, low=1.2, high=5.0):
    b, a = butter(2, [low / (fs / 2), high / (fs / 2)], btype='band')
    return filtfilt(b, a, signal)


def detect_arrhythmia(rr_intervals):

    if len(rr_intervals) < 8:
        return False

    rr = np.array(rr_intervals)

    # Remove unrealistic intervals
    rr = rr[(rr > 0.3) & (rr < 2.0)]

    if len(rr) < 5:
        return False

    rr_std = np.std(rr)
    rr_mean = np.mean(rr)

    variability = rr_std / rr_mean

    return variability > 0.25


class HeartRateMonitor:

    starting_BPM = 0

    def __init__(self, print_raw=False, print_result=True):

        self.print_raw = print_raw
        self.print_result = print_result

        self.sensor = MAX30102()
        self.running = False

        self.ir_buffer = []
        self.rr_intervals = []

        self.fs = 100
        self.buffer_size = self.fs * 10

        self.bpm = self.starting_BPM
        self.arrhythmia_flag = False

        # Finger detection
        self.no_contact_counter = 0
        self.no_contact_limit = self.fs * 2


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

            # Detect finger presence
            if ir < 5000:

                self.no_contact_counter += 1

                if self.no_contact_counter > self.no_contact_limit:
                    self.bpm = 0
                    self.arrhythmia_flag = False
                    self.ir_buffer.clear()
                    self.rr_intervals.clear()

                time.sleep(1 / self.fs)
                continue

            else:
                self.no_contact_counter = 0

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

        # Bandpass filter
        filtered = bandpass_filter(signal, fs=self.fs)

        # Peak detection with noise filtering
        peaks, _ = find_peaks(
            filtered,
            distance=int(self.fs * 0.4),
            prominence=np.std(filtered) * 0.5
        )

        if len(peaks) < 2:
            return

        peak_times = peaks / self.fs
        rr_intervals = np.diff(peak_times)

        # Save intervals
        self.rr_intervals.extend(rr_intervals)
        self.rr_intervals = self.rr_intervals[-30:]

        bpm = 60 / np.mean(rr_intervals)

        # Ignore unrealistic BPM spikes
        if 30 < bpm < 220:
            self.bpm = bpm

        self.arrhythmia_flag = detect_arrhythmia(self.rr_intervals)

        if self.print_raw:
            print(filtered[-1])

        if self.print_result:
            print(f"BPM: {self.bpm:.1f} | Arrhythmia Flag: {self.arrhythmia_flag}")
