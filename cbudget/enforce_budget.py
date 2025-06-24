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
    emission_rate_gph : predicted emission rate (gCO2eq/h)
    threshold_g       : allowed total emissions (grams)
    duration_h        : hours
    policy_file       : path to Rego policy
    """
    policy_path = Path(policy_file)
    if not policy_path.exists():
        click.echo(f"❌ OPA policy not found: {policy_path}", err=True)
        sys.exit(4)

    # Compute allowed rate
    allowed_rate_gph = threshold_g / duration_h

    payload_str = json.dumps({
        "emission_rate_gph": emission_rate_gph,
        "threshold_rate_gph": allowed_rate_gph
    })

    cmd = [
        "opa", "eval",
        "-f", "json",
        "--data", str(policy_path),
        "--stdin-input",
        "data.carbon.allow == true"
    ]
    proc = subprocess.run(
        cmd,
        input=payload_str,
        capture_output=True,
        text=True
    )

    # Treat exit code 1 as error, 2 as “no result” (i.e. allow==false)
    if proc.returncode not in (0, 2):
        click.echo(f"❌ OPA eval failed (exit {proc.returncode}):\n{proc.stderr}", err=True)
        sys.exit(5)

    # Parse JSON if any output; if empty or allowed==false, it’s a budget breach
    allowed = False
    if proc.stdout.strip():
        try:
            result = json.loads(proc.stdout)
            allowed = result["result"][0]["expressions"][0]["value"]
        except Exception as e:
            click.echo(f"❌ Failed to parse OPA output: {e}\nstdout: {proc.stdout}", err=True)
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
