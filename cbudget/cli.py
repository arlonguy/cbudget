import sys
from pathlib import Path

import click
import requests
import yaml
from requests.auth import HTTPBasicAuth

from cbudget.fetch_forecast import fetch_forecast
from cbudget.predict_emission import predict_emission, calculate_total_emissions
from cbudget.enforce_budget import enforce_budget
from cbudget.temporal_window import find_optimal_window

# Path to the bundled default config within the package
PACKAGE_DIR    = Path(__file__).resolve().parent
BUNDLED_CONFIG = PACKAGE_DIR / "configs" / "infra-budget.yml"

@click.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML config file (overrides bundled one)"
)
def run(config: Path):
    """Run the full carbon-budget check end-to-end."""
    # Determine which config to use
    config   = Path(config) if config else BUNDLED_CONFIG
    base_dir = config.parent
    click.echo(f"🔧 Using config: {config}")

    # Load configuration
    try:
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    except Exception as e:
        click.echo(f"❌ Failed to load config {config}: {e}", err=True)
        sys.exit(1)

    # WattTime credentials
    wt   = cfg.get("watttime", {})
    user = wt.get("username")
    pwd  = wt.get("password")
    if not (user and pwd):
        click.echo("❌ Missing WattTime credentials in config", err=True)
        sys.exit(1)

    # Obtain WattTime token
    try:
        resp = requests.get(
            "https://api.watttime.org/login",
            auth=HTTPBasicAuth(user, pwd),
            timeout=10
        )
        resp.raise_for_status()
        token = resp.json().get("token")
        if not token:
            raise ValueError("No token in response")
    except Exception as e:
        click.echo(f"❌ Failed to log in to WattTime: {e}", err=True)
        sys.exit(1)

    # Parameters for forecast
    region     = cfg.get("plan", {}).get("region", "CAISO_NORTH")
    hours      = int(cfg.get("plan", {}).get("hours", 72))
    duration_h = int(cfg.get("budget", {}).get("duration", 1))

    # a) full 72h forecast → forecast_full.json
    full_fcst = fetch_forecast(
        api_token  = token,
        region     = region,
        hours      = hours,
        filename   = str(base_dir / "forecast_full.json"),
        duration_h = hours,      # keep all 72h
    )

    # b) budget-window forecast → forecast.json
    window_fcst = fetch_forecast(
        api_token  = token,
        region     = region,
        hours      = hours,
        filename   = str(base_dir / "forecast.json"),
        duration_h = duration_h,  # keep only first duration_h
    )

    # Predict emissions using the budget-window forecast
    raw_folder    = cfg.get("plan", {}).get("folder")
    if not raw_folder:
        click.echo("❌ Missing plan.folder in config", err=True)
        sys.exit(1)
    plan_folder = (base_dir / raw_folder).expanduser().resolve()
    if not plan_folder.exists():
        click.echo(f"❌ Plan folder not found: {plan_folder}", err=True)
        sys.exit(1)

    prediction_output = base_dir / "predicted-emission-rate.json"
    energy_whph, emission_rate = predict_emission(
        plan_folder    = str(plan_folder),
        forecast_file  = window_fcst,
        duration_h     = duration_h,
        output_file    = prediction_output
    )

    # Total predicted emissions over the duration
    calculate_total_emissions(emission_rate, duration_h)

    # Enforce budget
    threshold_g = float(cfg.get("budget", {}).get("threshold", 0))
    policy_file = cfg.get("opa", {}).get("policy_file", "")
    policy_path = base_dir / policy_file
    if not policy_path.exists():
        click.echo(f"❌ OPA policy not found: {policy_path}", err=True)
        sys.exit(1)

    enforce_budget(
        emission_rate_gph = emission_rate,
        threshold_g       = threshold_g,
        duration_h        = duration_h,
        policy_file       = str(policy_path)
    )
    click.echo("✅ All checks passed — budget within limits.")

    # Find optimal window in the *full* 72h forecast
    start, end, avg_intensity = find_optimal_window(full_fcst, duration_h)
    click.echo(
        f"⏳ Optimal {duration_h}h window: {start.isoformat()} → {end.isoformat()} "
        f"(avg grid carbon intensity {avg_intensity:.2f} gCO₂eq/kWh)"
    )

    # Emission rate during that optimal window
    window_rate = avg_intensity * (energy_whph / 1000.0)
    click.echo(
        f"🏭 Predicted emission rate in optimal window: {window_rate:.3f} gCO₂eq/h"
    )

if __name__ == "__main__":
    run()
