# Development setup

Use Python 3.12+ with compatible wheels for your platform. Build a matching
`ghdl-bundled` wheel using the GHDL workflow, then run from the repository root:

```sh
python scripts/bootstrap.py --ghdl-wheel /absolute/path/to/ghdl_bundled.whl
```

Bootstrap creates `.venv`, installs the app and adapters in editable mode,
prepares the pinned netlistsvg payload, and checks the tool environment.
Alternatively, put one compatible GHDL wheel in `wheelhouse/` and run
`python scripts/bootstrap.py`.

Activate the environment and start Eitri:

```sh
source .venv/bin/activate
python -m eitri
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

GTKWave is optional: Eitri has an embedded waveform viewer. To use the external
viewer, install GTKWave separately or set `GTKWAVE_EXECUTABLE`. Its native runtime
is not bundled yet.

## Checks and builds

```sh
python scripts/check_environment.py
QT_QPA_PLATFORM=offscreen python -m pytest -q
python scripts/prepare_netlistsvg.py
python scripts/build_release.py --ghdl-wheel wheelhouse/ghdl_bundled-6.0.0.post1-py3-none-macosx_26_0_arm64.whl
```

In PowerShell, set `$env:QT_QPA_PLATFORM = "offscreen"` before running pytest.
The renderer payload must be prepared before building its wheel.

The public distribution is `eitri-hdl`; it includes the local tool adapters and
GHDL payload. The separate package definitions remain internal development/build
inputs and do not need publishing. See [RELEASING.md](RELEASING.md) for release
commands. CI builds and tests artifacts but never uploads to PyPI.

The app code lives under `src/eitri/`, tool adapters under `packages/`, and
automation under `scripts/` and `.github/workflows/`.
New workspace code is GPL-3.0-or-later. Third-party components retain their own
licenses; preserve their notices, including
`packages/ghdl/THIRD_PARTY_NOTICES.md`, when distributing binaries.
