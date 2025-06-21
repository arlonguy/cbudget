import sys
import yaml
import click
import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path

from cbudget.fetch_forecast import fetch_forecast
from cbudget.predict_emission import predict_emission
from cbudget.enforce_budget import enforce_budget

# 1) Locate the configs directory inside the package
PACKAGE_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = PACKAGE_DIR / "configs"
DEFAULT_CONFIG = CONFIGS_DIR / "infra-budget.yml"

@click.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_CONFIG,
    help="Path to YAML config file"
)
def run(config: Path):
    """Run the full carbon-budget check end-to-end."""
    # 2) Load configuration
    try:
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    except Exception as e:
        click.echo(f"Failed to load config {config}: {e}", err=True)
        sys.exit(1)

    # 3) WattTime creds
    wt = cfg.get("watttime", {})
    user = wt.get("username"); pwd = wt.get("password")
    if not (user and pwd):
        click.echo("Missing WattTime creds in config", err=True)
        sys.exit(1)

    # 4) Get WattTime token
    login_url = "https://api.watttime.org/login"
    try:
        resp = requests.get(login_url, auth=HTTPBasicAuth(user, pwd), timeout=10)
        resp.raise_for_status()
        token = resp.json().get("token")
        if not token:
            raise ValueError("no token in response")
    except Exception as e:
        click.echo(f"WattTime login failed: {e}", err=True)
        sys.exit(1)

    # 5) Fetch forecast → always writes to CONFIGS_DIR/forecast.json
    region = cfg.get("plan", {}).get("region", "CAISO_NORTH")
    hours  = cfg.get("plan", {}).get("hours", 72)
    forecast_path = fetch_forecast(
        api_token=token,
        region=region,
        hours=hours,
        filename="forecast.json"   # is the filename, fetch_forecast will write into CONFIGS_DIR
    )

    # 6) Predict emissions
    plan_folder = cfg.get("plan", {}).get("folder")
    if not plan_folder:
        click.echo("Missing plan.folder in config", err=True)
        sys.exit(1)
    emissions_kg = predict_emission(plan_folder, forecast_path)

    # 7) Enforce budget
    b = cfg.get("budget", {})
    threshold_g = float(b.get("threshold", 0))
    duration_h  = float(b.get("duration", 1))
    opa_cfg = cfg.get("opa", {})
    policy_file = CONFIGS_DIR / opa_cfg.get("policy_file", "")
    if not policy_file.exists():
        click.echo(f"OPA policy not found: {policy_file}", err=True)
        sys.exit(1)
    enforce_budget(emissions_kg, threshold_g, duration_h, str(policy_file))

    click.echo("All checks passed — budget within limits.")

if __name__ == "__main__":
    run()
