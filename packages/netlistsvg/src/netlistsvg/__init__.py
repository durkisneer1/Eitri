"""Render Yosys JSON to SVG using packaged netlistsvg and pip-installed Node."""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys

__all__ = ["render", "is_available"]


def _cli() -> Path:
    return Path(__file__).parent / "_vendor/node_modules/netlistsvg/bin/netlistsvg.js"


def is_available() -> bool:
    return _cli().is_file()


def render(netlist, output, *, skin=None, timeout=60) -> Path:
    """Render a JSON netlist file to an SVG file, returning the absolute path.

    Raises FileNotFoundError for missing inputs and CalledProcessError with
    stdout/stderr if the renderer fails. No npm/network operations at runtime.
    """
    if not is_available():
        raise RuntimeError("netlistsvg payload missing. Run scripts/prepare_netlistsvg.py or install its built wheel.")
    source = Path(netlist).expanduser().resolve()
    target = Path(output).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == target:
        raise ValueError("Output must not overwrite the input netlist")
    args = [sys.executable, "-m", "nodejs_wheel", str(_cli()), str(source), "-o", str(target)]
    if skin is not None:
        skin_path = Path(skin).expanduser().resolve()
        if not skin_path.is_file():
            raise FileNotFoundError(skin_path)
        args += ["--skin", str(skin_path)]
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout)
    if not target.is_file():
        raise RuntimeError("netlistsvg completed without producing the requested SVG")
    return target
