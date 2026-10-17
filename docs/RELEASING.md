# Releasing Eitri

Publish only **eitri-hdl**. It includes `eitri`, `ghdl`, `pyGHDL`, `yosys`,
`netlistsvg`, and `gtkwave`. Public upstream packages supply Qt, YoWASP Yosys,
pyosys (outside Windows), Node, pyTooling, and pyVHDLModel. GTKWave's external
native viewer is optional and remains separately installed.

## Build

Use the release environment with `build` and `twine` installed. Prepare the
JavaScript payload using an environment with the pinned nodejs-wheel-binaries:

```sh
.venv/bin/python scripts/prepare_netlistsvg.py
.venv-release/bin/python scripts/build_release.py --ghdl-wheel /absolute/path/to/ghdl_bundled-6.0.0.post1-py3-none-PLATFORM.whl --outdir release
.venv-release/bin/python -m twine check release/*.whl
```

The builder uses a clean temporary source tree, preserves the native wheel's
platform tag, permissions, repaired libraries, sources and notices, and removes
its separate distribution metadata. Do not relabel a macOS 26 wheel as macOS 15.
Do not upload a source distribution: this release requires prebuilt native code.

The GHDL workflow uploads final `eitri-hdl-*` artifacts after clean installation
and tests on each platform. Download those wheel artifacts into `release/` for
a multiplatform release. The locally built macOS wheel supports only macOS 26+
ARM64. Only include intended, tested artifacts of the current version.

Preserve the native workflow's dependency reports and toolchain inventories.
The source/notice requirements in `packages/ghdl/THIRD_PARTY_NOTICES.md` still
apply to the combined package, including corresponding runtime sources. A local
build and passing tests alone do not establish completion of that release review.

## Upload to TestPyPI (manual)

```sh
.venv-release/bin/python -m twine upload --repository testpypi release/*.whl
```

Use username `__token__` and a TestPyPI API token. Never commit tokens.
Then, in a fresh Python 3.11+ environment on a supported platform:

```sh
python -m pip download --index-url https://test.pypi.org/simple/ --no-deps --only-binary=:all: --dest test-download eitri-hdl==0.1.0
python -m pip install test-download/*.whl
python -m pip check
eitri
```

The download selects Eitri exclusively from TestPyPI; installation resolves its
public dependencies from the normal PyPI index. Verify editing, simulation and
circuit rendering. The activated environment puts the `eitri` launcher on PATH.

## Upload to production PyPI (manual, after testing)

```sh
.venv-release/bin/python -m twine upload release/*.whl
```

Use your separate production PyPI token. Upload the same verified artifacts.
Users install with `python -m pip install eitri-hdl` and launch with `eitri` or
`python -m eitri`. Bump the project version for subsequent changed releases.
