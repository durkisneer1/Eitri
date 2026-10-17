"""Create an editable development environment; never installs global tools."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

parser = argparse.ArgumentParser()
parser.add_argument("--ghdl-wheel", type=Path, help="Matching built ghdl-bundled wheel")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
wheels = [args.ghdl_wheel.resolve()] if args.ghdl_wheel else list((root / "wheelhouse").glob("ghdl_bundled-*.whl"))
if len(wheels) != 1 or not wheels[0].is_file():
    raise SystemExit("Provide one compatible GHDL wheel in wheelhouse/ or use --ghdl-wheel PATH. Build it with the GHDL workflow first.")
venv_path = root / ".venv"
python = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.exists():
    venv.EnvBuilder(with_pip=True).create(venv_path)

def run(*parts):
    subprocess.run([str(python), *map(str, parts)], cwd=root, check=True,
                   env={**os.environ, "YOWASP_CACHE_DIR": str(root / "work/yowasp-cache"),
                        "EITRI_GHDL_WHEEL": str(wheels[0])})

# Fail on an incompatible wheel before doing the JavaScript preparation.
run("-m", "pip", "install", wheels[0], "nodejs-wheel-binaries==24.19.0")
run(root / "scripts/prepare_netlistsvg.py")
run("-m", "pip", "install", "-e", ".[dev]")
run("-m", "pip", "check")
run(root / "scripts/check_environment.py")
print(f"Ready: {python}")
