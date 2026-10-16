# Eitri workspace

A starting point for your own Dear PyGui HDL application. **No application UI,
buttons, windows, editor, project model, or application callbacks are implemented.**
The app package is intentionally empty. The tool adapters are implemented and callable.

## Start developing on this Mac

The local `.venv` is prepared. Select it as your editor's Python interpreter:

```sh
cd /Users/durk/Documents/VHDL/Eitri
source .venv/bin/activate
python scripts/check_environment.py
```

Your application code can import:

```python
import ghdl
import yosys
import netlistsvg
import gtkwave
import dearpygui.dearpygui as dpg
```

Write your app under `src/eitri/`. Editable installs mean changes to this
package and the adapters take effect without reinstalling. The native GHDL
package is installed from a wheel, not editable.

## Layout

```text
src/eitri/       Your empty app package
packages/ghdl/         Existing GHDL build/package source, copied into this workspace
packages/yosys/        import yosys: portable jobs and native pyosys access
packages/netlistsvg/   import netlistsvg: JSON-to-SVG renderer
packages/gtkwave/      import gtkwave: external native viewer launcher
scripts/              Development setup, payload preparation, environment check
tests/               Adapter and tool integration checks
.github/workflows/    Adapter CI and GHDL native wheel builds
wheelhouse/           Local native GHDL wheel (not committed)
```

The earlier `../ghdl-package` directory is retained unchanged; use
`packages/ghdl` as this workspace's maintained copy going forward. The existing
`../and_gate` project is untouched. No nested Git repository was copied.

## Backend status

| Import | Ready behavior | Runtime dependency |
|---|---|---|
| `ghdl` | Analysis, simulation, synthesis, low-level `libghdl` | Bundled GHDL wheel |
| `yosys` | `run`, `run_script` with output, errors, timeouts | Pinned YoWASP WASM, installed by pip |
| `yosys.libyosys()` | Native design-database API on macOS/Linux | Pinned pyosys, installed by pip there |
| `netlistsvg` | `render(input_json, output_svg)` | JS dependencies inside its wheel; Node installed by pip |
| `gtkwave` | `launch(waveform)` returns a running process | Existing GTKWave install; not yet bundled |
| `dearpygui.dearpygui` | Ready for your own UI code | Pinned Dear PyGui wheel |

GTKWave on this Mac is discovered on PATH. On other machines, install GTKWave or
set `GTKWAVE_EXECUTABLE` to its native executable. This adapter does not embed a
waveform panel inside Dear PyGui. A distributable GTKWave runtime remains future
packaging work; importing the adapter alone does not install the viewer.

YoWASP jobs do not load native GHDL plugins. For VHDL synthesis, use GHDL's
supported synthesis-to-Verilog flow first, then pass that Verilog to Yosys.
Neither these adapters nor the empty app implement full FPGA place-and-route.

## Recreate the environment

Use Python 3.10+ with wheels available for the target platform. Put a compatible
GHDL wheel in `wheelhouse/`, then run from the workspace root:

```sh
python scripts/bootstrap.py
# Or explicitly choose an existing native build:
python scripts/bootstrap.py --ghdl-wheel /absolute/path/to/ghdl_bundled.whl
```

Bootstrap creates `.venv`, installs GHDL and Node from wheels, stages pinned npm
runtime dependencies, installs the app/adapters in editable mode, and checks the
environment. npm is used only during this developer/build preparation. The
renderer performs no downloads when called. The local GHDL wheel requires
macOS 26 ARM64; CI targets macOS 15 ARM64, Windows x64, and glibc 2.35+ Linux x64.

Package/distribution names differ from imports:
`eitri`, `ghdl-bundled`, `eitri-yosys`,
`eitri-netlistsvg`, `eitri-gtkwave`.
These workspace distribution names are placeholders and have not been published
or reserved. Do not run `pip install yosys` expecting this local adapter.

After all workspace distributions are published, the root project's dependencies
allow one `pip install eitri` to install the Python/tool packages. A completely
self-contained GUI distribution still requires finishing the GTKWave native bundle.

## Building and testing

```sh
python -m pytest -q
python -m build --wheel packages/yosys
python -m build --wheel packages/gtkwave
python -m build --wheel packages/netlistsvg
python -m build --wheel .
```

Run `python scripts/prepare_netlistsvg.py` before building the renderer wheel.
The npm lockfile pins transitive versions and integrity hashes. Build fails when
its payload is missing rather than publishing a broken renderer.

`tooling.yml` builds and tests adapters on Windows, macOS ARM64, and Linux.
`ghdl-wheels.yml` preserves the native GHDL build/repair/clean-install matrix.
No workflow publishes packages or starts an app.

See `docs/API.md` for callable interfaces and callback integration guidance.
All new workspace code is GPL-3.0-or-later. Third-party components keep their own
licenses. Preserve notices in the vendored JavaScript tree and refer to
`packages/ghdl/THIRD_PARTY_NOTICES.md` before public binary distribution.
