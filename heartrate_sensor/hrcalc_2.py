import numpy as np

SAMPLE_FREQ = 25
MA_SIZE = 4
BUFFER_SIZE = 100

def calc_hr_and_spo2(ir_data, red_data):
    """
    Drop-in replacement with same interface but improved algorithms
    """
    # Convert inputs
    ir = np.array(ir_data, dtype=np.float64)
    red = np.array(red_data, dtype=np.float64)
    
    # Quick validation
    if len(ir) < BUFFER_SIZE or len(red) < BUFFER_SIZE:
        return -999, False, -999, False
    
    # Use only the last BUFFER_SIZE samples if more are provided
    if len(ir) > BUFFER_SIZE:
        ir = ir[-BUFFER_SIZE:]
        red = red[-BUFFER_SIZE:]
    
    # Calculate HR using improved method
    hr, hr_valid = _improved_hr_calculation(ir)
    
    # Calculate SpO2
    spo2, spo2_valid = _improved_spo2_calculation(ir, red, hr_valid)
    
    return int(hr) if hr_valid else -999, hr_valid, \
           float(spo2) if spo2_valid else -999, spo2_valid

def _improved_hr_calculation(ir):
    """Improved HR calculation with better signal processing"""
    # Step 1: Remove DC component
    ir_mean = np.mean(ir)
    x = ir - ir_mean
    
    # Step 2: Apply bandpass filter (0.5-4 Hz)
    try:
        from scipy import signal
        fs = SAMPLE_FREQ
        nyquist = fs / 2
        low = 0.5 / nyquist
        high = 4.0 / nyquist
        b, a = signal.butter(2, [low, high], btype='band')
        x = signal.filtfilt(b, a, x)
    except ImportError:
        # Fallback: simple moving average
        for i in range(len(x) - MA_SIZE):
            x[i] = np.mean(x[i:i+MA_SIZE])
    
    # Step 3: Find peaks/valleys
    # Invert for valley detection
    x_inv = -x
    
    # Dynamic threshold
    signal_range = np.max(x_inv) - np.min(x_inv)
    if signal_range < 1000:
        return -999, False
    
    threshold = np.mean(x_inv) + 0.2 * signal_range
    
    # Find peaks
    peaks = []
    for i in range(1, len(x_inv) - 1):
        if x_inv[i] > threshold and x_inv[i] > x_inv[i-1] and x_inv[i] > x_inv[i+1]:
            # Avoid duplicates
            if not peaks or (i - peaks[-1]) > 6:  # At least 6 samples apart (~0.24s)
                peaks.append(i)
    
    # Step 4: Calculate HR from intervals
    if len(peaks) >= 2:
        intervals = []
        for i in range(1, len(peaks)):
            interval = peaks[i] - peaks[i-1]
            # Validate interval (0.3-2.0 seconds)
            if 7 <= interval <= 50:  # At 25Hz: 7 samples=0.28s, 50 samples=2.0s
                intervals.append(interval)
        
        if intervals:
            avg_interval = np.mean(intervals)
            hr = (SAMPLE_FREQ * 60) / avg_interval
            
            # Additional validation
            if np.std(intervals) / avg_interval < 0.4:  # Consistent intervals
                hr = max(30, min(200, hr))
                
                # Check signal strength
                if np.mean(ir) > 30000:
                    return hr, True
    
    return -999, False

def _improved_spo2_calculation(ir, red, hr_valid):
    """Improved SpO2 calculation"""
    if not hr_valid:
        return -999, False
    
    # Simple AC/DC method
    ir_ac = np.std(ir)
    ir_dc = np.mean(ir)
    red_ac = np.std(red)
    red_dc = np.mean(red)
    
    if ir_dc == 0 or red_dc == 0:
        return -999, False
    
    # Ratio of ratios
    R = (red_ac / red_dc) / (ir_ac / ir_dc)
    
    # Empirical formula (based on typical calibration)
    if 0.1 < R < 3.0:
        # Quadratic approximation
        spo2 = 104 - 17 * R
        
        # Clamp to reasonable range
        spo2 = max(70, min(100, spo2))
        
        # Simple validation
        if 80 <= spo2 <= 100:
            return spo2, True
    
    return -999, False

# Keep all original functions for compatibility
def find_peaks(x, size, min_height, min_dist, max_num):
    """Original implementation for compatibility"""
    ir_valley_locs, n_peaks = find_peaks_above_min_height(x, size, min_height, max_num)
    ir_valley_locs, n_peaks = remove_close_peaks(n_peaks, ir_valley_locs, x, min_dist)
    n_peaks = min([n_peaks, max_num])
    return ir_valley_locs, n_peaks

def find_peaks_above_min_height(x, size, min_height, max_num):
    """Original implementation"""
    i = 0
    n_peaks = 0
    ir_valley_locs = []
    while i < size - 1:
        if x[i] > min_height and x[i] > x[i-1]:
            n_width = 1
            while i + n_width < size - 1 and x[i] == x[i+n_width]:
                n_width += 1
            if x[i] > x[i+n_width] and n_peaks < max_num:
                ir_valley_locs.append(i)
                n_peaks += 1
                i += n_width + 1
            else:
                i += n_width
        else:
            i += 1
    return ir_valley_locs, n_peaks

def remove_close_peaks(n_peaks, ir_valley_locs, x, min_dist):
    """Original implementation"""
    sorted_indices = sorted(ir_valley_locs, key=lambda i: x[i])
    sorted_indices.reverse()
    
    i = -1
    while i < n_peaks:
        old_n_peaks = n_peaks
        n_peaks = i + 1
        j = i + 1
        while j < old_n_peaks:
            n_dist = (sorted_indices[j] - sorted_indices[i]) if i != -1 else (sorted_indices[j] + 1)
            if n_dist > min_dist or n_dist < -1 * min_dist:
                sorted_indices[n_peaks] = sorted_indices[j]
                n_peaks += 1
            j += 1
        i += 1
    
    sorted_indices[:n_peaks] = sorted(sorted_indices[:n_peaks])
    return sorted_indices, n_peaks
