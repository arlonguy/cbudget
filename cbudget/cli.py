import sys
from pathlib import Path

import click
import requests
import yaml
from requests.auth import HTTPBasicAuth

from cbudget.fetch_forecast import fetch_forecast
from cbudget.predict_emission import predict_emission
from cbudget.enforce_budget import enforce_budget

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
    forecast_path = fetch_forecast(
        api_token=token,
        region=region,
        hours=hours,
        filename=str(base_dir / "forecast.json")
    )

    # 6) Predict emissions
    raw_folder = cfg.get("plan", {}).get("folder")
    if not raw_folder:
        click.echo("❌ Missing plan.folder in config", err=True)
        sys.exit(1)
    plan_folder = Path(raw_folder).expanduser().resolve()
    if not plan_folder.exists():
        click.echo(f"❌ Plan folder not found: {plan_folder}", err=True)
        sys.exit(1)

    prediction_output = base_dir / "predicted-emission-rate.json"
    emission_rate     = predict_emission(
        plan_folder=str(plan_folder),
        forecast_file=forecast_path,
        output_file=prediction_output
    )

    # 7) Enforce budget
    b_cfg        = cfg.get("budget", {})
    threshold_g  = float(b_cfg.get("threshold", 0))
    duration_h   = float(b_cfg.get("duration", 1))
    policy_name  = cfg.get("opa", {}).get("policy_file", "")
    policy_path  = base_dir / policy_name
    if not policy_path.exists():
        click.echo(f"❌ OPA policy not found: {policy_path}", err=True)
        sys.exit(1)

    enforce_budget(
        emission_rate_gph=emission_rate,
        threshold_g=threshold_g,
        duration_h=duration_h,
        policy_file=str(policy_path)
    )

    click.echo("✅ All checks passed — budget within limits.")

if __name__ == "__main__":
    run()
