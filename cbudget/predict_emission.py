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
        total   = payload.get("Total", {})
        raw     = total.get("CarbonEmissions")
        if raw is None:
            raise KeyError("Total.CarbonEmissions")
        emission_rate = float(raw)
    except Exception as e:
        click.echo(f"❌ Could not parse CarbonEmissions from {output_path}: {e}", err=True)
        sys.exit(3)

    click.echo(f"✅ Predicted emission rate: {emission_rate:.3f} gCO₂eq/h")
    return emission_rate
