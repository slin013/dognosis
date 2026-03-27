"""
Predicted HR from dog profile (same model as dashboard JS / templates).
Used by the logger for dynamic High/Low/Emotional Distress thresholds.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

HR_MEAN = 114.0
HR_MEAN_WEIGHT_KG = 19.3
HR_WEIGHT_SLOPE = -0.21
HR_AGE_PER_DAY = 0.002

# Match static/charts.js Status badge vs predicted baseline
HR_FLAG_LOW_BELOW_PRED = 15
HR_FLAG_HIGH_ABOVE_PRED = 35

# Baseline-first thresholds when measured resting HR is available.
# If baseline exists, these multipliers should dominate model output.
RESTING_HR_LOW_MULT = 0.7
RESTING_HR_HIGH_MULT = 1.5
RESTING_HR_EMOTIONAL_DISTRESS_MULT = 1.4

BREED_COEFFS = {
    "border_collie": -7.777,
    "ckcs": 13.822,
    "golden_retriever": -6.152,
    "labrador_retriever": -5.356,
    "springer_spaniel": -6.735,
    "staffordshire_bull_terrier": 5.556,
    "west_highland_white_terrier": -6.0,
    "yorkshire_terrier": 14.178,
}


def age_days_from_dob(dob_str: Optional[str]) -> Optional[int]:
    if not dob_str or not str(dob_str).strip():
        return None
    try:
        parts = str(dob_str).strip().split("-")
        if len(parts) != 3:
            return None
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        dob = date(y, m, d)
        today = date.today()
        if dob > today:
            return None
        return (today - dob).days
    except (ValueError, TypeError):
        return None


def compute_predicted_hr(row: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    row keys: weight (kg), date_of_birth (YYYY-MM-DD), breed_code (canonical or 'other'/empty).
    """
    if not row:
        return None
    w = row.get("weight")
    if w is None:
        return None
    try:
        wf = float(w)
    except (TypeError, ValueError):
        return None
    if wf <= 0:
        return None

    hr = HR_MEAN + HR_WEIGHT_SLOPE * (wf - HR_MEAN_WEIGHT_KG)

    ad = age_days_from_dob(row.get("date_of_birth"))
    if ad is not None and ad >= 0:
        hr += HR_AGE_PER_DAY * ad

    code = (row.get("breed_code") or "").strip()
    if code and code != "other" and code in BREED_COEFFS:
        hr += BREED_COEFFS[code]

    hr = max(45.0, min(220.0, hr))
    return round(hr, 1)


def emotional_distress_avg_threshold(predicted: Optional[float]) -> float:
    """Min average BPM in window to count as 'elevated' for Emotional Distress."""
    if predicted is not None:
        return predicted + HR_FLAG_LOW_BELOW_PRED
    return 130.0


def resting_hr_from_row(row: Optional[Dict[str, Any]]) -> Optional[float]:
    """Return valid resting HR from profile row, if available."""
    if not row:
        return None
    value = row.get("resting_hr")
    if value is None:
        return None
    try:
        rf = float(value)
    except (TypeError, ValueError):
        return None
    if rf <= 0:
        return None
    return rf


def compute_hr_thresholds(
    row: Optional[Dict[str, Any]],
    predicted: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Returns personalized low/high/distress thresholds.
    Priority: resting baseline > profile prediction > None.
    """
    resting = resting_hr_from_row(row)
    if resting is not None:
        return {
            "low": round(resting * RESTING_HR_LOW_MULT, 1),
            "high": round(resting * RESTING_HR_HIGH_MULT, 1),
            "emotional_distress_min_avg": round(resting * RESTING_HR_EMOTIONAL_DISTRESS_MULT, 1),
            "baseline_type": "resting",
            "baseline_value": round(resting, 1),
        }

    if predicted is not None:
        return {
            "low": round(predicted - HR_FLAG_LOW_BELOW_PRED, 1),
            "high": round(predicted + HR_FLAG_HIGH_ABOVE_PRED, 1),
            "emotional_distress_min_avg": round(emotional_distress_avg_threshold(predicted), 1),
            "baseline_type": "predicted",
            "baseline_value": round(predicted, 1),
        }

    return {
        "low": None,
        "high": None,
        "emotional_distress_min_avg": round(emotional_distress_avg_threshold(None), 1),
        "baseline_type": None,
        "baseline_value": None,
    }


def row_tuple_to_hr_dict(row: tuple, col_names: list) -> Dict[str, Any]:
    d = dict(zip(col_names, row))
    return {
        "weight": d.get("weight"),
        "resting_hr": d.get("resting_hr"),
        "date_of_birth": d.get("date_of_birth"),
        "breed_code": d.get("breed_code"),
    }
