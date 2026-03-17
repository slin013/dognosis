# Switch from arrythmia detection to detecting abnormal heart rates
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
         # -------------------------
        # NEW: Heart Rate Flags
        # -------------------------
        self.high_hr_flag = False
        self.low_hr_flag = False
        self.rapid_change_flag = False
        self.unstable_hr_flag = False

        # NEW: BPM history
        self.bpm_history = []

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
            if ir < 5000:
                # No finger/contact detected → reset values
                self.ir_buffer.clear()
                self.rr_intervals.clear()
                self.last_peak_time = None

                self.bpm = 0
                self.arrhythmia_flag = False
                self.bpm_history.clear()

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

        # UPDATED: use median for stability
        if len(rr_intervals) > 0:
            self.bpm = 60 / np.median(rr_intervals)
        else:
            self.bpm = 0

        # NEW: update BPM history
        self.bpm_history.append(self.bpm)
        self.bpm_history = self.bpm_history[-10:]

       

        # High / Low BPM
        self.high_hr_flag = self.bpm > 180
        self.low_hr_flag = self.bpm < 50 and self.bpm > 0

        # Rapid change detection
        if len(self.bpm_history) >= 2:
            self.rapid_change_flag = abs(self.bpm_history[-1] - self.bpm_history[-2]) > 30
        else:
            self.rapid_change_flag = False

        # Unstable heart rate
        if len(self.bpm_history) >= 5:
            self.unstable_hr_flag = max(self.bpm_history) - min(self.bpm_history) > 30
        else:
            self.unstable_hr_flag = False


        # Disable flags if no valid BPM
        if self.bpm == 0:
            high_hr_flag = False
            low_hr_flag = False
            rapid_change_flag = False
            unstable_hr_flag = False

        # Keep arrhythmia_flag unused but set False
        self.arrhythmia_flag = False

        if self.print_raw:
            print(filtered[-1])

        if self.print_result:
            print(
                f"BPM: {self.bpm:.1f} | "
                f"High:{high_hr_flag} Low:{low_hr_flag} "
                f"RapidChange:{rapid_change_flag} "
                f"Unstable:{unstable_hr_flag}"
            )