"""Build-only npm step. Wheels contain the JS payload; users need no npm setup."""
from pathlib import Path
import shutil
from nodejs_wheel import npm

root = Path(__file__).resolve().parents[1]
package = root / "packages/netlistsvg"
if not (package / "package-lock.json").is_file():
    raise SystemExit("Missing package-lock.json; generate and review it before building")
result = npm(["ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund", "--cache", str(root / "work/npm-cache")],
             cwd=package, return_completed_process=True)
result.check_returncode()
target = package / "src/netlistsvg/_vendor/node_modules"
if target.exists():
    shutil.rmtree(target)
shutil.copytree(package / "node_modules", target, symlinks=False,
                ignore=shutil.ignore_patterns(".bin", "__pycache__", "*.pyc"))
print(f"Prepared {target}")
