import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

def find_optimal_window(forecast_path: Path, duration_h: int) -> Tuple[datetime, datetime, float]:
    """
    Given a forecast JSON (5 min resolution) and a window length in hours,
    slide an exact-duration window (duration_h * samples_per_hour) to find
    the lowest average carbon intensity (g/kWh).
    Returns (start, end, average_intensity).
    """
    data = json.loads(forecast_path.read_text(encoding='utf-8'))
    points = data.get("data", [])

    # Parse & sort by timestamp
    samples = [
        (
            datetime.fromisoformat(pt["timestamp"].replace("Z", "+00:00")),
            pt["value"]
        )
        for pt in points
    ]
    samples.sort(key=lambda x: x[0])

    if len(samples) < 2:
        raise ValueError("Need at least two samples to infer interval")

    # Figure out how many samples per hour
    delta = samples[1][0] - samples[0][0]
    secs_per_sample = delta.total_seconds()
    samples_per_hour = int(timedelta(hours=1).total_seconds() // secs_per_sample)
    window_size = duration_h * samples_per_hour

    n = len(samples)
    if window_size > n:
        raise ValueError(f"Requested window {duration_h}h ({window_size} samples) "
                         f"exceeds forecast length {n} samples")

    best_avg = float('inf')
    best_start = None

    # Slide over sample‐index, not hours
    for i in range(n - window_size + 1):
        window = samples[i : i + window_size]
        avg = sum(val for _, val in window) / window_size
        if avg < best_avg:
            best_avg = avg
            best_start = window[0][0]

    best_end = best_start + timedelta(hours=duration_h)
    return best_start, best_end, best_avg
