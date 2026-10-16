"""Bundled GHDL CLI API. Use ``libghdl()`` for upstream in-process bindings."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from ._runtime import native_root

__all__ = ["executable", "run", "libghdl"]
__version__ = "6.0.0.post1"


def executable() -> Path:
    """Absolute path to the bundled native executable, never a PATH lookup."""
    path = native_root() / "bin" / ("ghdl.exe" if os.name == "nt" else "ghdl")
    if not path.is_file():
        raise RuntimeError("GHDL native payload is missing. Install a built platform wheel.")
    return path


def run(args: Sequence[str | os.PathLike[str]], *, cwd=None, check=True,
        capture_output=False, text=True, timeout=None,
        env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run a GHDL job with subprocess.run semantics; never invokes a shell.

    ``env`` overlays the inherited environment. The bundled VHDL library
    prefix and runtime search paths are always selected by this package.
    """
    if isinstance(args, (str, bytes)):
        raise TypeError("Pass an argument sequence, not a shell command string")
    child_env = dict(os.environ)
    child_env.update(env or {})
    root = native_root()
    child_env["GHDL_PREFIX"] = str(root / "lib" / "ghdl")
    child_env["PATH"] = os.pathsep.join([
        str(root / "bin"), str(root / "lib"), child_env.get("PATH", "")
    ])
    return subprocess.run([str(executable()), *map(os.fspath, args)], cwd=cwd,
                          check=check, capture_output=capture_output, text=text,
                          timeout=timeout, env=child_env)


def libghdl():
    """Load the bundled upstream low-level API (GPL); not a thread-safe session API."""
    from pyGHDL import libghdl as api
    return api
