import json
from pathlib import Path

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

def save_transformed_json(data: dict, output_path: Path, region: str) -> Path:
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

    output = {"region": region, "data": transformed}
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )
    click.echo(f"✅ Forecast saved to {output_path}")
    return output_path

def fetch_forecast(api_token: str,
                   region: str = "CAISO_NORTH",
                   hours: int = 72,
                   filename: str = "forecast.json") -> Path:
    """
    High-level wrapper:
      1) fetch raw forecast via fetch_forecast_data()
      2) transform & save via save_transformed_json()
    filename may be a relative or absolute path to where you want forecast.json.
    """
    # 1) get raw data
    raw = fetch_forecast_data(api_token, region, hours)

    # 2) resolve the output path exactly as given
    output_path = Path(filename).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 3) write it out
    return save_transformed_json(raw, output_path, 'us-west2')
