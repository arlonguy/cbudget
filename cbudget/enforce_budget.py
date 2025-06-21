# cbudget/enforce_budget.py

import json
import subprocess
import sys
from pathlib import Path

import click

def enforce_budget(emission_rate_gph: float,
                   threshold_g: float,
                   duration_h: float,
                   policy_file: str):
    """
    emission_rate_gph : predicted emission rate (gCO2eq/h) from Carbonifer
    threshold_g       : allowed total emissions (budget) in grams
    duration_h        : job duration in hours
    policy_file       : path to your Rego policy (e.g. carbon-policy.rego)
    """
    # 1) Validate policy file exists
    policy_path = Path(policy_file)
    if not policy_path.exists():
        click.echo(f"OPA policy not found: {policy_path}", err=True)
        sys.exit(4)

    # 2) Compute allowed rate (g/h)
    try:
        allowed_rate_gph = threshold_g / duration_h
    except Exception as e:
        click.echo(f"Invalid threshold or duration: {e}", err=True)
        sys.exit(4)

    # 3) Build OPA input payload
    input_payload = {
        "emission_rate_gph": emission_rate_gph,
        "threshold_rate_gph": allowed_rate_gph
    }

    # 4) Invoke OPA to enforce the rate-based policy
    cmd = [
        "opa", "eval",
        "--data", str(policy_path),
        "--input", json.dumps(input_payload),
        "data.carbon.allow == true"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # 5) Handle enforcement result
    if proc.returncode != 0 or "true" not in proc.stdout:
        click.echo(
            f"Rate enforcement failed:\n"
            f"   predicted: {emission_rate_gph:.2f} g/h\n"
            f"   allowed:   {allowed_rate_gph:.2f} g/h",
            err=True
        )
        click.echo(proc.stdout, err=True)
        sys.exit(5)

    click.echo(
        f"Predicted rate {emission_rate_gph:.2f} g/h ≤ "
        f"allowed rate {allowed_rate_gph:.2f} g/h"
    )
    sys.exit(0)
