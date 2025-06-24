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
    policy_path = Path(policy_file)
    if not policy_path.exists():
        click.echo(f"❌ OPA policy not found: {policy_path}", err=True)
        sys.exit(4)

    # Compute allowed rate (g/h)
    try:
        allowed_rate_gph = threshold_g / duration_h
    except Exception as e:
        click.echo(f"❌ Invalid threshold or duration: {e}", err=True)
        sys.exit(4)

    input_payload = {
        "emission_rate_gph": emission_rate_gph,
        "threshold_rate_gph": allowed_rate_gph
    }
    payload_str = json.dumps(input_payload)

    # Invoke OPA, passing JSON via stdin with `--input -`
    cmd = [
        "opa", "eval",
        "-f", "json",
        "--data", str(policy_path),
        "--input", "-",          # read input from stdin
        "data.carbon.allow == true"
    ]
    proc = subprocess.run(
        cmd,
        input=payload_str,       # feed the JSON here
        capture_output=True,
        text=True
    )

    if proc.returncode != 0:
        click.echo(f"❌ OPA eval failed (exit {proc.returncode}):\n{proc.stderr}", err=True)
        sys.exit(5)

    # Parse the JSON result
    try:
        result = json.loads(proc.stdout)
        allowed = result["result"][0]["expressions"][0]["value"]
    except Exception as e:
        click.echo(
            f"❌ Could not parse OPA JSON output: {e}\n"
            f"STDERR: {proc.stderr}\nSTDOUT: {proc.stdout}", err=True
        )
        sys.exit(5)

    if not allowed:
        click.echo(
            f"❌ Rate enforcement failed:\n"
            f"   predicted: {emission_rate_gph:.2f} g/h\n"
            f"   allowed:   {allowed_rate_gph:.2f} g/h",
            err=True
        )
        sys.exit(5)

    click.echo(
        f"✅ Predicted rate {emission_rate_gph:.2f} g/h ≤ "
        f"allowed rate {allowed_rate_gph:.2f} g/h"
    )
    sys.exit(0)
