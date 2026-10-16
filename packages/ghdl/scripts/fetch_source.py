"""Fetch one immutable upstream revision. No floating main/master builds."""
from pathlib import Path
import subprocess

COMMIT = "e589c698c351369ac5bcfe7abe1f1152ac5d4727"  # GHDL v6.0.0
source = Path("work/ghdl")
if not source.exists():
    source.mkdir(parents=True)
    subprocess.run(["git", "init", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin",
                    "https://github.com/ghdl/ghdl.git"], check=True)
    subprocess.run(["git", "-C", str(source), "fetch", "--depth=1", "origin", COMMIT], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], check=True)
actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
if actual != COMMIT:
    raise SystemExit(f"Wrong upstream revision: {actual}, expected {COMMIT}")
if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"]):
    raise SystemExit("Refusing a modified upstream source tree")
