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
    policy_path = Path(policy_file)
    if not policy_path.exists():
        click.echo(f"❌ OPA policy not found: {policy_path}", err=True)
        sys.exit(4)

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

    # Always dump OPA output for visibility
    # click.echo(f"OPA stderr:\n{proc.stderr}", err=True)
    # click.echo(f"OPA stdout:\n{proc.stdout}", err=True)

    # 0 = allow==true, 2 = allow==false, others = eval error
    if proc.returncode not in (0, 2):
        click.echo(f"❌ OPA eval error (exit {proc.returncode})", err=True)
        sys.exit(5)

    # If exit code 2, budget was exceeded
    if proc.returncode == 2:
        click.echo(
            f"❌ Rate enforcement failed:\n"
            f"   predicted: {emission_rate_gph:.2f} g/h\n"
            f"   allowed:   {allowed_rate_gph:.2f} g/h",
            err=True
        )
        sys.exit(5)

    # Otherwise exit code 0 → success
    click.echo(
        f"✅ Predicted rate {emission_rate_gph:.2f} g/h ≤ "
        f"allowed rate {allowed_rate_gph:.2f} g/h"
    )
    sys.exit(0)
