# Releasing Eitri

Publish only **eitri-hdl**. It includes `eitri`, `ghdl`, `pyGHDL`, `yosys`,
`netlistsvg`, and `gtkwave`. Public upstream packages supply Qt, YoWASP Yosys,
pyosys (outside Windows), Node, pyTooling, and pyVHDLModel. GTKWave's external
native viewer is optional and remains separately installed.

## Build

The normal release path is GitHub Actions Trusted Publishing, described below.
Local builds and manual uploads remain available for troubleshooting.

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
and tests on each platform. The clean-install matrix covers Python 3.11, 3.12,
3.13, and 3.14 on Windows x64, Linux x64, and macOS ARM64. Wait for all twelve
jobs to pass; artifact uploads occur in the Python 3.14 jobs and do not by
themselves prove the other versions passed. Download those wheel artifacts into `release/` for
a multiplatform release. The locally built macOS wheel supports only macOS 26+
ARM64. Only include intended, tested artifacts of the current version.

Preserve the native workflow's dependency reports and toolchain inventories.
The source/notice requirements in `packages/ghdl/THIRD_PARTY_NOTICES.md` still
apply to the combined package, including corresponding runtime sources. A local
build and passing tests alone do not establish completion of that release review.

## Trusted Publishing setup (once)

Create the `testpypi` and `pypi` environments in the repository's
[Settings → Environments](https://github.com/durkisneer1/Eitri/settings/environments).
To pause before production upload, add yourself as a required reviewer for
`pypi`, allowing self-review if you trigger your own releases. Without that
environment protection, production upload proceeds automatically after TestPyPI.
Restrict the production environment to version tags (`v*`). Allow `main` and
version tags for `testpypi` if using the manual test-only option.

Register GitHub trusted publishers with these exact values:

| Setting | TestPyPI | PyPI |
| --- | --- | --- |
| Project | `eitri-hdl` | `eitri-hdl` |
| Owner | `durkisneer1` | `durkisneer1` |
| Repository | `Eitri` | `Eitri` |
| Workflow filename | `ghdl-wheels.yml` | `ghdl-wheels.yml` |
| Environment | `testpypi` | `pypi` |

For the existing TestPyPI project, use
[project Publishing settings](https://test.pypi.org/manage/project/eitri-hdl/settings/publishing/).
If the production project does not exist, add a pending publisher under
[PyPI account Publishing](https://pypi.org/manage/account/publishing/).
If it already exists under your account, use its project Publishing settings.
No API tokens or GitHub secrets are required. See the official
[existing-project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) and
[new-project](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) guides.

## Automated release

Commit and push the workflow changes before tagging. Set the desired version
in `pyproject.toml`, commit it, and push a matching tag, for example:

```sh
git tag v0.1.0
git push origin v0.1.0
```

The tag must match the project version exactly. This triggers native builds and
all twelve clean-install jobs, validates the three final Eitri wheels, uploads
them to TestPyPI, and then uploads the identical artifacts to PyPI. If a required
reviewer is configured for `pypi`, test the TestPyPI release before approving
the production job. No local wheel downloads or Twine uploads are needed.

For a TestPyPI-only rehearsal, use Actions → GHDL native wheels → Run workflow
and enable `publish_testpypi`. Manual runs never upload to production. Use a
distinct prerelease version (for example `0.1.1rc1`) for rehearsals: rebuilding
the same filenames for a later tag will fail because uploads are not overwritable.
The workflow intentionally does not silently skip existing files. If an upload
partially fails, inspect the index before deciding how to recover; do not blindly
rerun a completed upload job.

Ordinary branch pushes and pull requests only build and test. Publishing jobs
have OIDC permission but do not check out or build source code. Both indexes
receive the same validated artifact bundle from the current workflow run.

## Upload to TestPyPI (manual fallback)

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

## Upload to production PyPI (manual fallback, after testing)

```sh
.venv-release/bin/python -m twine upload release/*.whl
```

Use your separate production PyPI token. Upload the same verified artifacts.
Users install with `python -m pip install eitri-hdl` and launch with `eitri` or
`python -m eitri`. Bump the project version for subsequent changed releases.
