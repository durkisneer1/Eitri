# ghdl-bundled

Unofficial GHDL 6.0.0 binary distribution: one pip installation supplies the
`ghdl` CLI, a Python job API, `libghdl`, matching `pyGHDL` bindings, `ghdl-ls`,
`ghdl-dom`, and standard/IEEE VHDL libraries. No runtime download occurs.

**Not yet published.** `ghdl` is already an unrelated project on PyPI. This
project uses distribution name `ghdl-bundled`, command `ghdl`, and module `ghdl`.
The proposed name has not been reserved. Once published, installation is:

```sh
pip install ghdl-bundled
ghdl --version
```

For now, download a wheel produced by the workflow and install that local file:

```sh
python -m pip install ./ghdl_bundled-6.0.0.post1-py3-none-PLATFORM.whl
```

Use a dedicated virtual environment; this distribution owns the `pyGHDL`
namespace and `ghdl` command. Do not co-install another pyGHDL distribution.

```python
import ghdl

ghdl.run(["-a", "--std=08", "design.vhd", "tb.vhd"])
ghdl.run(["-r", "--std=08", "tb", "--vcd=wave.vcd"], timeout=60)

# Existing upstream low-level API, loaded directly into Python:
from pyGHDL import libghdl
from pyGHDL.libghdl import errorout_console
libghdl.initialize()
errorout_console.Install_Handler()
assert libghdl.set_option("--std=08")
assert libghdl.analyze_init_status() == 0
node = libghdl.analyze_file("design.vhd")
```

`ghdl.run` launches the bundled executable without a shell and returns a
`subprocess.CompletedProcess`. `check`, `cwd`, `timeout`, `capture_output`,
`text`, and an environment overlay are supported. Native exit failures raise
`CalledProcessError` unless `check=False`. CLI stdout/stderr are streamed.

The upstream `libghdl` API exposes compiler internals, not a stable high-level
simulation session API. Do not use it concurrently from multiple threads.
Use separate worker processes for independent analyses. The binding's upstream
filename encoding limitations are retained. No nanobind or GHDL CLI rewrite.

## Build targets

| Target | Backend | Minimum system | Runtime compiler needed? |
|---|---|---|---|
| Windows x64 | mcode | Windows 10/11, x64 Python | No |
| macOS ARM64 | LLVM-JIT | macOS 15, ARM64 Python | No |
| Linux x64 | mcode | glibc 2.35+, x64 Python | No |

Linux is built on Ubuntu 22.04 and repaired/validated against
`manylinux_2_35_x86_64`; this is intentionally not a manylinux2014 wheel.
Older glibc and Alpine/musl are unsupported. macOS Intel and Windows ARM64
are not built. Windows ARM64 needs a native Ada/toolchain/backend combination
not covered by this project's build recipes; it is not just another wheel tag.

Python 3.10+ is required. Wheels use `py3-none-PLATFORM` because bindings use
ctypes rather than the CPython extension ABI. CI tests Python 3.10 and 3.14.

## GitHub Actions

Push this directory as the root of a GitHub repository. `.github/workflows/wheels.yml`
runs on pushes, pull requests, or manual dispatch. It builds from an immutable
GHDL commit, stages matching bindings, repairs native dependencies, and uploads
one candidate wheel per target. Separate clean jobs install the wheels and run
simulation, synthesis, CLI, and direct-library tests with toolchain paths removed.
No PyPI credentials are needed, and no package is automatically published.

The source checkout does not contain generated `pyGHDL` or native files.
`pip install .` without building/staging first intentionally fails instead of
creating a broken pure-Python package. Ship wheels, not an unbuildable sdist.

Local build sequence after installing a suitable GNAT/C toolchain:

```sh
python scripts/fetch_source.py
BACKEND=mcode bash scripts/build-native.sh
python scripts/stage.py
python -m build --wheel
# Perform platform-specific repair as shown in the workflow, then install/test.
```

On macOS use `BACKEND=llvm-jit`, the checksummed compiler from
`scripts/install_macos_gnat.sh`, and `LLVM_CONFIG=$(brew --prefix llvm@22)/bin/llvm-config`.
All build intermediates stay under `work/`. Build from a clean checkout.

## Distribution and licensing

See THIRD_PARTY_NOTICES.md. Each wheel includes corresponding GHDL source, the
binding patch and packaging source. Native runtime dependencies still require a
release-specific license/source audit before public redistribution. Build artifacts
are candidates, not a claim of completed release compliance or tested support
until their clean-install CI jobs pass.

References: https://github.com/ghdl/ghdl/tree/v6.0.0,
https://ghdl.github.io/ghdl/pyGHDL/pyGHDL.html.
