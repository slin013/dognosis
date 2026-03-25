"""
Estimated core temperature model (v1).

This model converts the harness surface temperature reading (F) into a
core-temperature estimate (F) using lightweight contextual adjustments.
"""

from typing import Optional, Tuple


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def estimate_core_temp_f(
    surface_temp_f: Optional[float],
    bpm: Optional[float] = None,
    steps_per_min: Optional[float] = None,
) -> Tuple[Optional[float], float]:
    """
    Return (core_temp_est_f, confidence_0_to_1).

    v1 heuristic:
    - Base offset between skin and core
    - Small HR/activity-driven adjustment
    - Confidence lowered when context is missing
    """
    if surface_temp_f is None:
        return None, 0.0

    try:
        sf = float(surface_temp_f)
    except (TypeError, ValueError):
        return None, 0.0

    # Base skin->core offset (placeholder, to be calibrated with empirical data).
    core_est = sf + 25.0
    confidence = 0.55

    if bpm is not None:
        try:
            b = float(bpm)
            # Mildly increase estimate during elevated HR.
            core_est += _clamp((b - 100.0) * 0.015, -0.8, 1.2)
            confidence += 0.20
        except (TypeError, ValueError):
            pass

    if steps_per_min is not None:
        try:
            spm = float(steps_per_min)
            # Slight activity term to prevent underestimation in active windows.
            core_est += _clamp((spm - 15.0) * 0.01, -0.5, 0.8)
            confidence += 0.15
        except (TypeError, ValueError):
            pass

    # Keep plausible canine core range bounds for safety.
    core_est = _clamp(core_est, 95.0, 109.0)
    confidence = _clamp(confidence, 0.0, 0.95)
    return round(core_est, 2), round(confidence, 2)
