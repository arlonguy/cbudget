# cbudget/predict_emission.py

import json
import subprocess
import sys
from pathlib import Path

import click

def predict_emission(plan_folder: str,
                      forecast_file: Path,
                      output_file: Path = Path(__file__).resolve().parent
                                                / "configs" / "predicted-emission-rate.json") -> float:
    """
    Invoke Carbonifer to predict emissions for the given Terraform plan folder,
    using the provided carbon intensity JSON file. Writes the full JSON output
    to `output_file` and returns the emission rate (gCO2eq/h) from Total.CarbonEmissions.
    """
    # 1) Validate inputs
    if not Path(plan_folder).exists():
        click.echo(f"Plan folder not found: {plan_folder}", err=True)
        sys.exit(3)
    if not forecast_file.exists():
        click.echo(f"Carbon intensity file not found: {forecast_file}", err=True)
        sys.exit(3)

    # 2) Run Carbonifer CLI
    cmd = [
        "carbonifer",
        "plan",
        plan_folder,
        "--carbon-intensity-file",
        str(forecast_file),
        "--output",
        str(output_file)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"Carbonifer failed:\n{e.stderr}", err=True)
        sys.exit(3)

    # 3) Parse the Carbonifer output JSON
    if not output_file.exists():
        click.echo(f"Prediction file not created: {output_file}", err=True)
        sys.exit(3)

    try:
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        total = payload.get("Total", {})
        raw = total.get("CarbonEmissions")
        if raw is None:
            raise KeyError("Total.CarbonEmissions")
        # raw is a string value like "2.4129415824"
        emission_rate = float(raw)
    except Exception as e:
        click.echo(f"Could not parse CarbonEmissions from {output_file}: {e}", err=True)
        sys.exit(3)

    click.echo(f"Predicted emission rate: {emission_rate:.3f} gCO₂eq/h")
    return emission_rate
