import json
import shutil
import subprocess
import sys
from pathlib import Path

import click

def predict_emission(plan_folder: str,
                     forecast_file: Path,
                     output_file: Path = Path(__file__).resolve().parent
                                             / "configs"
                                             / "predicted-emission-rate.json") -> float:
    """
    Invoke Carbonifer to predict emissions for the given Terraform plan folder,
    using the provided carbon intensity JSON file. Writes the full JSON output
    to `output_file` and returns the emission rate (gCO2eq/h) from Total.CarbonEmissions.
    """
    # Resolve all paths
    plan_path     = Path(plan_folder).expanduser().resolve()
    forecast_path = Path(forecast_file).expanduser().resolve()
    output_path   = Path(output_file).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) Validate inputs
    if not plan_path.exists():
        click.echo(f"❌ Plan folder not found: {plan_path}", err=True)
        sys.exit(3)
    if not forecast_path.exists():
        click.echo(f"❌ Carbon intensity file not found: {forecast_path}", err=True)
        sys.exit(3)

    # find the carbonifer binary on PATH
    carbonifer_bin = shutil.which("carbonifer")
    if not carbonifer_bin:
         click.echo("❌ Could not find the ‘carbonifer’ binary on PATH", err=True)
         sys.exit(3)

    # 2) Build your cmd with that full path
    cmd = [
        carbonifer_bin, "plan", str(plan_path),
        "--carbon-intensity-file", str(forecast_path),
        "-f", "json",
        "--output", str(output_path)
    ]
    click.echo(f"🔧 Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Carbonifer failed:\n{e.stderr}", err=True)
        sys.exit(3)

    # 3) Parse the Carbonifer output JSON
    if not output_path.exists():
        click.echo(f"❌ Prediction file not created: {output_path}", err=True)
        sys.exit(3)

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        total = payload.get("Total", {})
        raw = total.get("CarbonEmissions")
        if raw is None:
            raise KeyError("Total.CarbonEmissions")
        emission_rate = float(raw)
        power_raw = total.get("Power")
        if power_raw is not None:
            try:
                power_value = float(power_raw)
                click.echo(
                    f"🔋 Estimated energy usage of provisioned IaC resources with an average utilization rate of 0.5 (50%): {power_value:.10f} Wh/h")
            except Exception as e:
                click.echo(f"⚠️  Failed to parse Power from prediction file: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Could not parse CarbonEmissions from {output_path}: {e}", err=True)
        sys.exit(3)

    click.echo(f"🏭 Predicted emission rate of provisioned IaC resources: {emission_rate:.3f} gCO₂eq/h (average over next 72h)")
    return emission_rate


def calculate_total_emissions(emission_rate_gph: float, duration_h: float) -> float:
    """
    Given a rate in gCO2eq/h and a duration in hours, return total emissions in grams.
    """
    total_g = emission_rate_gph * duration_h
    click.echo(f"🏭 Total predicted emissions of provisioned IaC resources: {total_g:.0f} g over {duration_h:.0f} h")
    return total_g