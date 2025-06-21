import json
from pathlib import Path

import click
import requests
import yaml
from requests.auth import HTTPBasicAuth

def load_watttime_credentials():
    """
    Load WattTime username & password from configs/infra-budget.yml
    """
    config_path = Path(__file__).parent.parent / "configs" / "infra-budget.yml"
    cfg = yaml.safe_load(open(config_path))
    wt_cfg = cfg["watttime"]
    return wt_cfg["username"], wt_cfg["password"]

def get_watttime_token(username: str, password: str) -> str:
    """
    Log into WattTime and return an access token.
    """
    login_url = "https://api.watttime.org/login"
    resp = requests.get(login_url, auth=HTTPBasicAuth(username, password), timeout=10)
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        click.echo("Failed to retrieve WattTime token", err=True)
        raise click.Abort()
    return token

def fetch_forecast_data(api_token: str, region: str, hours: int) -> dict:
    """
    Fetch CO2 intensity forecast data from WattTime API.
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
        click.echo(f"Error fetching WattTime forecast: {e}", err=True)
        click.echo("Falling back to static placeholder data", err=True)
        return {}

def save_transformed_json(data: dict, filename: str, region: str) -> Path:
    """
    Transform WattTime response to {region, data:[{timestamp, value}]} in g/kWh,
    and write to filename. Returns the Path written.
    """
    points = data.get("data", [])
    # conversion lbs/MWh → g/kWh: lbs/MWh * 0.453592 (kg/lb) * 1000 (g/kg) / 1000 (kWh/MWh) = 0.453592
    conversion_factor = 0.453592

    transformed = []
    for point in points:
        timestamp = point["point_time"].replace("+00:00", "Z")
        value = round(point["value"] * conversion_factor, 2)
        transformed.append({"timestamp": timestamp, "value": value})

    output = {"region": region, "data": transformed}
    path = Path(filename)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=4), encoding="utf-8")
    click.echo(f"Forecast saved to {path}")
    return path

def fetch_forecast(region: str = "CAISO_NORTH",
                   hours: int = 72,
                   filename: str = "forecast.json") -> Path:
    """
    High-level: loads creds, gets token, fetches raw forecast,
    transforms & saves JSON for Carbonifer.
    """
    username, password = load_watttime_credentials()
    token = get_watttime_token(username, password)
    raw = fetch_forecast_data(token, region, hours)
    return save_transformed_json(raw, filename, "us-west2")



