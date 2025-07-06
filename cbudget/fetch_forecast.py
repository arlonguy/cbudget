import json
from pathlib import Path
from datetime import datetime, timedelta

import click
import requests

def fetch_forecast_data(api_token: str, region: str, hours: int) -> dict:
    """
    Fetch CO₂ intensity forecast data from the WattTime API.
    Returns the raw JSON response.
    """
    FORECAST_URL = "https://api.watttime.org/v3/forecast"
    headers = {"Authorization": f"Bearer {api_token}"}
    params = {
        "region": [region],
        "signal_type": "co2_moer",
        "horizon_hours": [hours]
    }
    try:
        resp = requests.get(FORECAST_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        click.echo(f"❌ Error fetching WattTime forecast: {e}", err=True)
        click.echo("ℹFalling back to static placeholder data", err=True)
        return {}

def save_transformed_json(data: dict, output_path: Path, region: str, duration_h: int | None = None) -> Path:
    """
    Transform raw WattTime data for Carbonifer:
      - Converts from lbs/MWh to g/kWh.
      - Wraps points as {"timestamp": ..., "value": ...}.
    Writes result to output_path and returns it.
    """
    points = data.get("data", [])
    conversion_factor = 0.453592  # lbs/MWh → g/kWh

    transformed = []
    for point in points:
        ts = point["point_time"].replace("+00:00", "Z")
        val_g_per_kwh = round(point["value"] * conversion_factor, 2)
        transformed.append({"timestamp": ts, "value": val_g_per_kwh})

    # If user requested only the FIRST duration_h hours:
    if duration_h is not None and duration_h > 0 and len(transformed) >= 2:
        # compute interval between first two points
        t0 = datetime.fromisoformat(transformed[0]["timestamp"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(transformed[1]["timestamp"].replace("Z", "+00:00"))
        delta_min = (t1 - t0).total_seconds() / 60.0
        pts_per_hour = int(round(60.0 / delta_min))
        keep = duration_h * pts_per_hour
        transformed = transformed[:keep]

    output = {"region": region, "data": transformed}
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )
    click.echo(f"🌡️ Forecast saved to {output_path}")
    return output_path

def fetch_forecast(api_token: str,
                   region: str = "CAISO_NORTH",
                   hours: int = 72,
                   filename: str = "forecast.json",
                   duration_h: int | None = None) -> Path:
    """
    1) fetch raw forecast via fetch_forecast_data()
    2) transform & save via save_transformed_json()
       keeping only the first `duration_h` hours if requested.
    """
    raw = fetch_forecast_data(api_token, region, hours)
    output_path = Path(filename).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 3) write it out
    return save_transformed_json(raw, output_path, 'us-west2', duration_h)


def fetch_forecast(api_token: str,
                   region: str = "CAISO_NORTH",
                   hours: int = 72,
                   filename: str = "forecast.json") -> Path:
    """
    1) Fetch raw data
    2) Transform & save full-horizon (>duration) forecast to `filename`
    """
    raw = fetch_forecast_data(api_token, region, hours)
    output_path = Path(filename).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return save_transformed_json(raw, output_path, 'us-west2')


def slice_forecast(full_path: Path, duration_h: int, out_path: Path) -> Path:
    """
    Read the full-horizon forecast at `full_path`, then write only the next
    `duration_h` hours of data (based on timestamps) to `out_path`.
    """
    payload = json.loads(full_path.read_text(encoding="utf-8"))
    pts = payload.get("data", [])
    if not pts:
        raise ValueError("No data points in forecast file")

    # parse first timestamp
    t0 = datetime.fromisoformat(pts[0]["timestamp"].replace("Z", "+00:00"))
    cutoff = t0 + timedelta(hours=duration_h)

    sliced = [
        p for p in pts
        if datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")) < cutoff
    ]

    new = {"region": 'us-west2', "data": sliced}
    out_path.write_text(json.dumps(new, ensure_ascii=False, indent=4),
                        encoding="utf-8")
    click.echo(f"Sliced forecast to next {duration_h} h → {out_path}")
    return out_path
