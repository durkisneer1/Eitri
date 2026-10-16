"""GTKWave launcher adapter. The native GTKWave GUI is not bundled yet."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess

__all__ = ["executable", "is_available", "launch", "version"]


def executable(path=None) -> Path:
    """Resolve an explicit path, GTKWave environment setting, payload, or PATH."""
    configured = path if path is not None else os.environ.get("GTKWAVE_EXECUTABLE")
    if configured is not None:
        resolved = Path(configured).expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"GTKWave executable does not exist: {resolved}")
        return resolved
    bundled = Path(__file__).parent / "_native/bin" / ("gtkwave.exe" if os.name == "nt" else "gtkwave")
    if bundled.is_file():
        return bundled
    located = shutil.which("gtkwave")
    if located:
        return Path(located)
    raise FileNotFoundError("GTKWave is not bundled yet. Install GTKWave or set GTKWAVE_EXECUTABLE to its executable.")


def is_available() -> bool:
    try:
        executable()
        return True
    except FileNotFoundError:
        return False


def launch(waveform, *, savefile=None, executable_path=None, cwd=None) -> subprocess.Popen:
    """Open a waveform in GTKWave's separate window and return immediately."""
    base = Path(cwd).resolve() if cwd else Path.cwd()
    wave = Path(waveform)
    wave = (base / wave).resolve() if not wave.is_absolute() else wave
    if not wave.is_file():
        raise FileNotFoundError(wave)
    args = [str(executable(executable_path)), str(wave)]
    if savefile is not None:
        save = (base / Path(savefile)).resolve()
        if not save.is_file():
            raise FileNotFoundError(save)
        args.append(str(save))
    return subprocess.Popen(args, cwd=cwd)


def version(*, executable_path=None, timeout=10) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(executable(executable_path)), "--version"],
                          capture_output=True, text=True, check=True, timeout=timeout)
