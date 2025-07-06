import sys
from pathlib import Path

import click
import requests
import yaml
from requests.auth import HTTPBasicAuth

from cbudget.fetch_forecast import fetch_forecast, slice_forecast
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
    help="Path to your YAML config file (overrides bundled one)"
)
def run(config: Path):
    """Run the full carbon-budget check end-to-end."""
    # 1) Determine which config to use
    config = config or BUNDLED_CONFIG
    base_dir = config.parent
    click.echo(f"🔧 Using config: {config}")

    # 2) Load configuration
    try:
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    except Exception as e:
        click.echo(f"❌ Failed to load config {config}: {e}", err=True)
        sys.exit(1)

    # 3) WattTime credentials
    wt = cfg.get("watttime", {})
    user = wt.get("username")
    pwd  = wt.get("password")
    if not (user and pwd):
        click.echo("❌ Missing WattTime credentials in config", err=True)
        sys.exit(1)

    # 4) Obtain WattTime token
    login_url = "https://api.watttime.org/login"
    try:
        resp = requests.get(
            login_url,
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

    # 5) Fetch forecast data (saves to base_dir/forecast.json)
    region        = cfg.get("plan", {}).get("region", "CAISO_NORTH")
    hours         = cfg.get("plan", {}).get("hours", 72)
    duration_h    = int(cfg.get("budget", {}).get("duration", 1))
    full_fcst = fetch_forecast(token, region, hours,
                               filename=str(base_dir / "forecast.json"))

    # write a second file containing only the next duration_h hours
    window_fcst = base_dir / "forecast_window.json"
    slice_forecast(full_fcst, duration_h, window_fcst)

    # 6) Predict emissions using only the sliced window
    raw_folder = cfg["plan"]["folder"]
    plan_folder = (base_dir / raw_folder).expanduser().resolve()
    if not plan_folder.exists():
        click.echo(f"❌ Plan folder not found: {plan_folder}", err=True)
        sys.exit(1)

    pred_out = base_dir / "predicted-emission-rate.json"
    energy_whph, rate_gph = predict_emission(
        plan_folder=str(plan_folder),
        forecast_file=window_fcst,
        output_file=pred_out
    )

    # Calculate total mass over your duration
    total_g = calculate_total_emissions(rate_gph, duration_h)

    # 7) Enforce budget
    b_cfg        = cfg.get("budget", {})
    threshold = float(cfg["budget"]["threshold"])
    policy = base_dir / cfg["opa"]["policy_file"]
    enforce_budget(rate_gph, threshold, duration_h, str(policy))

    click.echo("✅ All checks passed — budget within limits.")

    # 8) Find the lowest‐intensity window and compute its gCO₂eq/h
    start, end, avg_int = find_optimal_window(full_fcst, duration_h)
    click.echo(f"⏳ Optimal {duration_h} h window: {start.isoformat()} → {end.isoformat()} (avg grid carbon intensity {avg_int:.2f} gCO₂eq/kWh)")

    # and show its emission rate using your known Wh/h
    window_rate = avg_int * (energy_whph / 1000.0)
    click.echo(f"🏭 Predicted emission rate for ⏳ optimal window duration: {window_rate:.3f} gCO₂eq/h")


if __name__ == "__main__":
    run()
