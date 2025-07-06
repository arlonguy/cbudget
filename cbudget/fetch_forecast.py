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
        click.echo("ℹ Falling back to static placeholder data", err=True)
        return {}

def save_transformed_json(data: dict,
                          output_path: Path,
                          region: str,
                          duration_h: int) -> Path:
    """
    Transform raw WattTime data for Carbonifer, but *slice* it down
    to only the first `duration_h` hours worth of data (5-min intervals).
    """
    raw_points = data.get("data", [])
    if len(raw_points) < 2:
        raise ValueError("Not enough forecast points to infer interval")

    # infer interval in minutes between samples
    t0 = datetime.fromisoformat(raw_points[0]["point_time"].replace("+00:00", "Z"))
    t1 = datetime.fromisoformat(raw_points[1]["point_time"].replace("+00:00", "Z"))
    interval_min = (t1 - t0).total_seconds() / 60

    # how many samples cover duration_h hours?
    samples_needed = int(duration_h * 60 / interval_min)

    # slice to only that many points
    to_slice = raw_points[:samples_needed]

    # lbs/MWh → g/kWh conversion
    factor = 0.453592

    transformed = []
    for point in to_slice:
        ts = point["point_time"].replace("+00:00", "Z")
        val_gpkwh = round(point["value"] * factor, 2)
        transformed.append({"timestamp": ts, "value": val_gpkwh})

    output = {"region": region, "data": transformed}
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )
    click.echo(f"🌡️ Forecast (first {duration_h} h) saved to {output_path}")
    return output_path

def fetch_forecast(api_token: str,
                   region: str = "CAISO_NORTH",
                   hours: int = 72,
                   filename: str = "forecast.json",
                   duration_h: int = 1) -> Path:
    """
    1) Fetch raw forecast via fetch_forecast_data()
    2) Transform & save via save_transformed_json(), slicing to the
       first `duration_h` hours worth of 5-min points.
    """
    # 1) fetch raw data
    raw = fetch_forecast_data(api_token, region, hours)

    # 2) prepare output path
    output_path = Path(filename).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 3) slice & save
    return save_transformed_json(raw, output_path, 'us-west2', duration_h)
