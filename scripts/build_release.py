"""Build a single platform wheel in a clean staging directory."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--ghdl-wheel", type=Path)
group.add_argument("--ghdl-wheel-dir", type=Path)
parser.add_argument("--outdir", type=Path, default=Path("release"))
args = parser.parse_args()
wheels = [args.ghdl_wheel] if args.ghdl_wheel else list(args.ghdl_wheel_dir.glob("ghdl_bundled-*.whl"))
if len(wheels) != 1 or not wheels[0].is_file():
    parser.error("Provide exactly one GHDL wheel for this platform")
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="eitri-release-") as directory:
    stage = Path(directory)
    for filename in ("pyproject.toml", "setup.py", "README.md", "LICENSE"):
        shutil.copy2(root / filename, stage / filename)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info")
    shutil.copytree(root / "src", stage / "src", ignore=ignore)
    for name in ("yosys", "netlistsvg", "gtkwave"):
        shutil.copytree(root / "packages" / name / "src", stage / "packages" / name / "src", ignore=ignore)
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(args.outdir.resolve()), str(stage)],
        env={**os.environ, "EITRI_GHDL_WHEEL": str(wheels[0].resolve())}, check=True,
    )
