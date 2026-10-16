"""Callable Yosys jobs plus optional access to the native design database."""
from __future__ import annotations
import os
import subprocess
import sys
from typing import Sequence

__all__ = ["run", "run_script", "libyosys"]


def run(args: Sequence[str | os.PathLike[str]], *, cwd=None, check=True,
        capture_output=True, timeout=None, env=None) -> subprocess.CompletedProcess[str]:
    """Run the pinned YoWASP backend in an isolated Python process.

    Captures stdout/stderr by default. Supports cwd and timeout without changing
    the GUI process's current directory. Nonzero exits raise CalledProcessError.
    """
    if isinstance(args, (str, bytes)):
        raise TypeError("Pass a sequence of arguments; use run_script for Yosys scripts")
    child_env = {**os.environ, **(env or {})}
    return subprocess.run([sys.executable, "-m", "yosys._worker", *map(os.fspath, args)],
                          cwd=cwd, check=check, capture_output=capture_output,
                          text=True, timeout=timeout, env=child_env)


def run_script(script: str, **kwargs) -> subprocess.CompletedProcess[str]:
    """Execute a Yosys command script, e.g. 'read_verilog gate.v; synth'."""
    return run(["-p", script], **kwargs)


def libyosys():
    """Return pyosys.libyosys on macOS/Linux for direct native API access.

    Native objects have upstream lifetime/threading constraints. Do not share
    them between simultaneous GUI callbacks. Use run/run_script for isolated jobs.
    """
    try:
        from pyosys import libyosys as api
    except ModuleNotFoundError as error:
        if error.name not in {"pyosys", "pyosys.libyosys"}:
            raise
        raise RuntimeError("Native pyosys is unavailable here; use yosys.run_script().") from error
    return api
