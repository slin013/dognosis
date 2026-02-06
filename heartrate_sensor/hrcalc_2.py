import numpy as np

SAMPLE_FREQ = 25
BUFFER_SIZE = 100

def calc_hr_and_spo2(ir_data, red_data, method='autocorrelation', debug=False):
    """
    Simplified version with multiple calculation methods
    """
    ir = np.array(ir_data, dtype=np.float64)
    red = np.array(red_data, dtype=np.float64)
    
    # Validate signal quality
    if not _validate_signal(ir, red, debug):
        return -999, False, -999, False
    
    # Choose calculation method
    if method == 'autocorrelation':
        hr, hr_valid = _calculate_hr_autocorrelation(ir, debug)
    elif method == 'peak_detection':
        hr, hr_valid = _calculate_hr_peak_detection(ir, debug)
    elif method == 'fft':
        hr, hr_valid = _calculate_hr_fft(ir, debug)
    else:
        hr, hr_valid = _calculate_hr_peak_detection(ir, debug)
    
    # Calculate SpO2 if HR is valid
    if hr_valid:
        spo2, spo2_valid = _calculate_spo2_simple(ir, red, debug)
    else:
        spo2, spo2_valid = -999, False
    
    return hr, hr_valid, spo2, spo2_valid

def _validate_signal(ir, red, debug=False):
    """Validate signal quality"""
    # Check for sufficient amplitude
    ir_range = np.max(ir) - np.min(ir)
    red_range = np.max(red) - np.min(red)
    
    if ir_range < 2000 or red_range < 1000:
        if debug:
            print(f"Signal amplitude too low: IR range={ir_range}, Red range={red_range}")
        return False
    
    # Check for saturation
    if np.max(ir) > 16000000 or np.max(red) > 16000000:
        if debug:
            print("Signal saturated")
        return False
    
    # Check for reasonable DC levels
    ir_mean = np.mean(ir)
    red_mean = np.mean(red)
    
    if ir_mean < 10000 or red_mean < 10000:
        if debug:
            print(f"DC level too low: IR mean={ir_mean}, Red mean={red_mean}")
        return False
    
    return True

def _calculate_hr_autocorrelation(ir, debug=False):
    """Calculate HR using autocorrelation (more robust to noise)"""
    # Remove DC component
    ir_ac = ir - np.mean(ir)
    
    # Apply bandpass filter (0.5 Hz to 4 Hz = 30 to 240 BPM)
    from scipy import signal as spsignal
    
    # Design bandpass filter
    nyquist = SAMPLE_FREQ / 2
    low = 0.5 / nyquist  # 0.5 Hz
    high = 4.0 / nyquist  # 4.0 Hz
    
    b, a = spsignal.butter(2, [low, high], btype='band')
    ir_filtered = spsignal.filtfilt(b, a, ir_ac)
    
    # Calculate autocorrelation
    autocorr = np.correlate(ir_filtered, ir_filtered, mode='full')
    autocorr = autocorr[len(autocorr)//2:]  # Take positive lags
    
    # Find peaks in autocorrelation (skip first peak at lag 0)
    peaks, _ = spsignal.find_peaks(autocorr[10:])  # Skip first 10 samples
    peaks = peaks + 10  # Adjust indices
    
    if len(peaks) > 0:
        # Find first significant peak (fundamental frequency)
        fundamental_lag = peaks[0]
        
        # Convert lag to heart rate
        hr = 60.0 * SAMPLE_FREQ / fundamental_lag
        
        # Validate HR is in physiological range
        if 30 <= hr <= 200:
            return int(hr), True
    
    return -999, False

def _calculate_hr_peak_detection(ir, debug=False):
    """Improved peak detection method"""
    # Apply smoothing
    from scipy.ndimage import uniform_filter1d
    ir_smooth = uniform_filter1d(ir, size=3)
    
    # Remove DC
    ir_ac = ir_smooth - np.mean(ir_smooth)
    
    # Find peaks (valleys in PPG)
    from scipy.signal import find_peaks
    peaks, properties = find_peaks(
        -ir_ac,  # Invert to find valleys
        height=np.std(-ir_ac) * 0.5,
        distance=int(SAMPLE_FREQ * 0.6),  # At least 0.6 seconds apart
        prominence=np.std(ir_ac) * 0.3
    )
    
    if len(peaks) >= 2:
        intervals = np.diff(peaks)
        
        # Filter intervals to physiological range (0.3s to 2.0s)
        valid_intervals = intervals[
            (intervals >= int(SAMPLE_FREQ * 0.3)) & 
            (intervals <= int(SAMPLE_FREQ * 2.0))
        ]
        
        if len(valid_intervals) >= 1:
            avg_interval = np.mean(valid_intervals)
            hr = 60.0 * SAMPLE_FREQ / avg_interval
            
            # Additional validation: check consistency
            if np.std(valid_intervals) / avg_interval < 0.3:  # Less than 30% variation
                hr = int(hr)
                return max(30, min(200, hr)), True
    
    return -999, False

def _calculate_hr_fft(ir, debug=False):
    """Calculate HR using FFT (frequency domain)"""
    # Remove DC and apply windowing
    ir_ac = ir - np.mean(ir)
    window = np.hanning(len(ir_ac))
    ir_windowed = ir_ac * window
    
    # Compute FFT
    n = len(ir_windowed)
    freqs = np.fft.rfftfreq(n, d=1/SAMPLE_FREQ)
    fft_vals = np.abs(np.fft.rfft(ir_windowed))
    
    # Focus on physiological range (0.5 Hz to 4 Hz = 30 to 240 BPM)
    mask = (freqs >= 0.5) & (freqs <= 4.0)
    freqs = freqs[mask]
    fft_vals = fft_vals[mask]
    
    if len(fft_vals) == 0:
        return -999, False
    
    # Find dominant frequency
    dominant_idx = np.argmax(fft_vals)
    dominant_freq = freqs[dominant_idx]
    
    # Convert to BPM
    hr = dominant_freq * 60
    
    # Validate
    if 30 <= hr <= 200 and fft_vals[dominant_idx] > np.mean(fft_vals) * 2:
        return int(hr), True
    
    return -999, False

def _calculate_spo2_simple(ir, red, debug=False):
    """Simplified SpO2 calculation"""
    # Calculate AC/DC ratios
    ir_ac = np.std(ir)
    ir_dc = np.mean(ir)
    red_ac = np.std(red)
    red_dc = np.mean(red)
    
    if ir_dc == 0 or red_dc == 0:
        return -999, False
    
    # Calculate ratio of ratios
    R = (red_ac / red_dc) / (ir_ac / ir_dc)
    
    # Empirical calibration (can be tuned)
    if 0.1 < R < 2.0:
        # Linear approximation (needs calibration with real data)
        spo2 = 110 - 25 * R
        
        # Clamp to reasonable range
        spo2 = max(70, min(100, spo2))
        
        # Additional validation
        if 90 <= spo2 <= 100:
            return round(spo2, 1), True
        elif 70 <= spo2 < 90:
            return round(spo2, 1), True
    
    return -999, False

# Keep original functions for compatibility
def find_peaks(x, size, min_height, min_dist, max_num):
    """Dummy implementation for compatibility"""
    from scipy.signal import find_peaks as sp_find_peaks
    peaks, _ = sp_find_peaks(x[:size], height=min_height, distance=min_dist)
    peaks = peaks[:max_num]
    return list(peaks), len(peaks)
