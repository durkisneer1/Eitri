# Third-party software and release obligations

This is an unofficial distribution, not an upstream GHDL release.

* GHDL and pyGHDL 6.0.0, commit e589c698c351369ac5bcfe7abe1f1152ac5d4727:
  GPL-2.0-or-later. Copyright Tristan Gingold and contributors. The complete
  upstream source is inside each wheel at ghdl/_sources/ghdl-6.0.0.tar.gz.
  That source includes individual component notices and VHDL library sources.
* The pyGHDL loader is modified to load the matching bundled library. The
  dated change notice and exact patch accompany the source. Packaging scripts,
  workflow and tests are in ghdl/_sources/packaging-source.tar.gz.
* Standard/IEEE sources have individual notices, including Apache-2.0 sources.
  The build enables GHDL's GPL-compatible library selection. Preserve these notices.
* Python dependencies pyTooling and pyVHDLModel are installed by pip from their
  own distributions, with their own license metadata.
* Native dependencies differ by platform: GNAT/GCC runtimes (GPL with applicable
  runtime exceptions), LLVM on macOS (Apache-2.0 with LLVM exceptions), and any
  libraries copied by wheel repair. Their notices and source requirements apply
  independently. A runtime exception is not a blanket exemption for redistributing
  a standalone runtime library.

## Before public distribution

The workflow builds candidate artifacts; it deliberately does not upload to PyPI
or create a public GitHub Release. Review repaired-wheel dependencies and their
exact versions, include all required notices, and supply corresponding sources for
bundled copyleft runtime libraries (including any distributor patches and build
scripts). GHDL's source bundle alone does not satisfy those separate obligations.
Preserve the workflow's toolchain inventories and dependency reports with releases.
Do not describe the whole wheel as MIT or impose noncommercial-only restrictions.

The package code and build scripts are GPL-3.0-or-later. For the combined
LLVM-JIT distribution we elect GPLv3 under GHDL's GPL-2.0-or-later grant,
which permits combination with LLVM's Apache-2.0 terms. Upstream notices remain intact.
