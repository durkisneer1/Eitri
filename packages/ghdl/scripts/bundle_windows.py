"""Copy the recursive non-system DLL closure for both CLI and ctypes entrypoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import pefile

parser = argparse.ArgumentParser()
parser.add_argument("toolchain", type=Path)
args = parser.parse_args()
root = Path("src/ghdl/_native")
search = [root / "bin", root / "lib", args.toolchain / "bin"]
lookup = {p.name.lower(): p for directory in reversed(search) for p in directory.glob("*.dll")}
system = Path(os.environ["SystemRoot"]) / "System32"
queue = list(root.rglob("*.exe")) + list(root.rglob("*.dll"))
seen = set()
manifest = []
while queue:
    binary = queue.pop()
    key = binary.name.lower()
    if key in seen:
        continue
    seen.add(key)
    with pefile.PE(str(binary)) as pe:
        imports = list(getattr(pe, "DIRECTORY_ENTRY_IMPORT", []))
        imports += list(getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", []))
        names = [entry.dll.decode("ascii").lower() for entry in imports]
    for name in names:
        if name.startswith(("api-ms-win-", "ext-ms-win-")):
            continue
        dependency = lookup.get(name)
        if dependency is None:
            if (system / name).is_file():
                continue
            raise SystemExit(f"Unresolved DLL {name} needed by {binary}")
        if dependency.is_relative_to(args.toolchain):
            target = root / "bin" / dependency.name
            if not target.exists():
                shutil.copy2(dependency, target)
                manifest.append({"name": dependency.name, "source": str(dependency),
                                 "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
            dependency = target
        queue.append(dependency)
licenses = args.toolchain / "share/licenses"
if licenses.exists():
    shutil.copytree(licenses, root / "licenses/msys2", dirs_exist_ok=True)
(root / "windows-dependencies.json").write_text(json.dumps(manifest, indent=2) + "\n")
