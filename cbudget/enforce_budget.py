import json
import subprocess
import sys
import shutil
from pathlib import Path

import click

def enforce_budget(emission_rate_gph: float,
                   threshold_g: float,
                   duration_h: float,
                   policy_file: str):
    """
    emission_rate_gph : predicted emission rate (gCO2eq/h)
    threshold_g       : allowed total emissions (grams)
    duration_h        : job duration (hours)
    policy_file       : path to Rego policy
    """
    policy_path = Path(policy_file)
    if not policy_path.exists():
        click.echo(f"❌ OPA policy not found: {policy_path}", err=True)
        sys.exit(4)

    allowed_rate_gph = threshold_g / duration_h
    payload = {
        "emission_rate_gph": emission_rate_gph,
        "threshold_rate_gph": allowed_rate_gph
    }

    # find the opa binary on PATH
    opa_bin = shutil.which("opa")
    if not opa_bin:
        opa_bin = "/usr/local/bin/opa"  # fallback
        if not Path(opa_bin).exists():
            click.echo(f"❌ Could not find the ‘opa’ binary", err=True)
            sys.exit(4)

    # build cmd with that full path
    cmd = [
        opa_bin,
        "eval",
        "-f", "json",
        "--data", policy_file,
        "--stdin-input",
        "data.carbon.allow == true"
    ]

    # Run OPA, feeding JSON on stdin
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True
    )

    # Any non-zero here really is a syntax/runtime error
    if proc.returncode != 0:
        click.echo(f"❌ OPA eval error (exit {proc.returncode}):\n{proc.stderr}", err=True)
        sys.exit(5)

    # Parse the JSON result
    try:
        out = json.loads(proc.stdout)
        value = out["result"][0]["expressions"][0]["value"]
    except Exception as e:
        click.echo(
            f"❌ Failed to parse OPA JSON output: {e}\n"
            f"STDERR: {proc.stderr}\nSTDOUT: {proc.stdout}",
            err=True
        )
        sys.exit(5)

    # Now branch on the actual boolean
    if not value:
        click.echo(
            f"❌ Rate enforcement failed:\n"
            f"   predicted emission rate over next 24h: {emission_rate_gph:.2f} g/h\n"
            f"   allowed emission budget rate: {allowed_rate_gph:.2f} g/h",
            err=True
        )
        sys.exit(5)

    click.echo(
        f"💰 Predicted emission rate {emission_rate_gph:.2f} g/h ≤ "
        f"allowed emission budget rate {allowed_rate_gph:.2f} g/h"
    )
    return
