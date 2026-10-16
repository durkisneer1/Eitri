"""Private runtime discovery, also used by our small patch to pyGHDL."""
import os
from pathlib import Path

_DLL_HANDLES = []  # Keep Windows DLL-directory handles alive for the process.


def native_root() -> Path:
    return Path(__file__).resolve().parent / "_native"


def library_path() -> Path:
    root = native_root()
    if os.name == "nt" and not _DLL_HANDLES:
        for directory in (root / "bin", root / "lib"):
            _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    extension = ".dll" if os.name == "nt" else (".dylib" if os.sys.platform == "darwin" else ".so")
    libraries = list((root / "lib").glob(f"libghdl-*{extension}"))
    if len(libraries) != 1:
        raise RuntimeError(f"Expected one bundled libghdl, found {libraries}")
    return libraries[0]
