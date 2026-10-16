"""Stage matching bindings, installed runtime, and corresponding GHDL source."""
from pathlib import Path
import difflib
import json
import shutil
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
source = root / "work/ghdl"
package = root / "src/ghdl"
native = package / "_native"
bindings = root / "src/pyGHDL"
sources = package / "_sources"
for target in (native, bindings, sources):
    if target.exists():
        shutil.rmtree(target)
shutil.copytree(root / "work/install", native, symlinks=False)
shutil.copytree(source / "pyGHDL", bindings, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
sources.mkdir()
# Force the paired library, ignoring unrelated GHDL installs/environment settings.
loader = bindings / "libghdl/__init__.py"
original = loader.read_text()
needle = '    _libghdl_path = _get_libghdl_path()'
replacement = ('    # Modified by ghdl-bundled, 2026-10-16: use the paired wheel runtime.\n'
               '    from ghdl._runtime import library_path\n'
               '    _libghdl_path = library_path()')
if original.count(needle) != 1:
    raise SystemExit("Upstream loader changed; review the binding patch")
patched = original.replace(needle, replacement)
prefix_needle = "    return libghdl.libghdl__analyze_init_status()"
if patched.count(prefix_needle) != 1:
    raise SystemExit("Upstream analyzer changed; review the prefix patch")
patched = patched.replace(prefix_needle,
    '    # Modified by ghdl-bundled, 2026-10-16: pair standard libraries too.\n'
    '    from ghdl._runtime import native_root\n'
    '    if not set_option("--PREFIX=" + str(native_root() / "lib" / "ghdl")):\n'
    '        raise LibGHDLException("Cannot configure bundled VHDL libraries")\n'
    + prefix_needle)
loader.write_text(patched)
(sources / "pyghdl-loader.patch").write_text("".join(difflib.unified_diff(
    original.splitlines(True), patched.splitlines(True),
    fromfile="a/pyGHDL/libghdl/__init__.py", tofile="b/pyGHDL/libghdl/__init__.py")))
subprocess.run(["git", "-C", str(source), "archive", "--format=tar.gz",
                "--prefix=ghdl-6.0.0/", f"--output={sources / 'ghdl-6.0.0.tar.gz'}", "HEAD"], check=True)
# Build/install scripts and wrapper source accompany each wheel too.
with tarfile.open(sources / "packaging-source.tar.gz", "w:gz") as archive:
    for name in ("scripts", ".github", "tests", "pyproject.toml", "setup.py", "README.md",
                 "LICENSE", "THIRD_PARTY_NOTICES.md"):
        archive.add(root / name, arcname=f"ghdl-package/{name}",
                    filter=lambda info: None if "__pycache__" in info.name else info)
    for path in package.glob("*.py"):
        archive.add(path, arcname=f"ghdl-package/src/ghdl/{path.name}")
revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
(native / "provenance.json").write_text(json.dumps({
    "ghdl_version": "6.0.0", "ghdl_commit": revision,
    "upstream": "https://github.com/ghdl/ghdl", "distribution": "ghdl-bundled",
    "sources": "../_sources/", "binding_patch": "../_sources/pyghdl-loader.patch",
}, indent=2) + "\n")
# No external compiler is needed for mcode or LLVM-JIT; remove unused development archives.
for path in native.rglob("*.a"):
    path.unlink()
for path in native.rglob("*.o"):
    path.unlink()
print(f"Staged {native} and {bindings}")
