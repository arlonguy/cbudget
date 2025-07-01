import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

def find_optimal_window(forecast_path: Path, duration_h: int) -> Tuple[datetime, datetime, float]:
    """
    Given a forecast JSON file (as output by fetch_forecast) and a window duration in hours,
    find the contiguous window of that length with lowest average carbon intensity (g/kWh).
    Returns (start, end, average_intensity).
    """
    data = json.loads(forecast_path.read_text(encoding='utf-8'))
    points = data.get("data", [])

    # Parse and sort
    samples = [
        (
            datetime.fromisoformat(pt["timestamp"].replace("Z", "+00:00")),
            pt["value"]
        )
        for pt in points
    ]
    samples.sort(key=lambda x: x[0])

    n = len(samples)
    window_size = duration_h
    if window_size > n:
        raise ValueError(f"Requested window {duration_h}h exceeds forecast length {n}h")

    best_avg = float('inf')
    best_start = None

    # Sliding‐window over the hourly samples
    for i in range(n - window_size + 1):
        window = samples[i : i + window_size]
        avg = sum(val for _, val in window) / window_size
        if avg < best_avg:
            best_avg = avg
            best_start = window[0][0]

    best_end = best_start + timedelta(hours=duration_h)
    return best_start, best_end, best_avg
