"""Make GNAT runtimes discoverable for delocate, retaining their license texts."""
from pathlib import Path
import shutil
import sys

compiler = Path(sys.argv[1]).resolve()
root = Path("src/ghdl/_native")
(root / "licenses").mkdir(parents=True, exist_ok=True)
for pattern in ("lib/libgcc_s*.dylib", "lib/gcc/*/*/adalib/libgnat-*.dylib"):
    matches = list(compiler.glob(pattern))
    if not matches:
        raise SystemExit(f"Missing compiler runtime: {pattern}")
    for path in matches:
        for directory in (root / "bin", root / "lib"):
            shutil.copy2(path, directory / path.name)
for name in ("COPYING*", "*LICENSE*", "*EXCEPTION*"):
    for path in compiler.rglob(name):
        if path.is_file():
            target = root / "licenses/gnat" / path.relative_to(compiler)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
notices = Path("work/macos-notices")
if not notices.is_dir():
    raise SystemExit("Run scripts/macos_notices.sh before packaging")
shutil.copytree(notices, root / "licenses", dirs_exist_ok=True)
