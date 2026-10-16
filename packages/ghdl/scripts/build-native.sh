#!/usr/bin/env bash
# Build native payload. Invoke from repository root with a matching Ada toolchain.
set -euo pipefail
ROOT=$(pwd)
SOURCE="$ROOT/work/ghdl"
PREFIX="$ROOT/work/install"
JOBS=${JOBS:-4}
BACKEND=${BACKEND:-mcode}
mkdir -p "$ROOT/work/native-build"
cd "$ROOT/work/native-build"
args=("--prefix=$PREFIX" --enable-libghdl --enable-synth --enable-gplcompat)
if [[ "$BACKEND" == llvm-jit ]]; then
  LLVM_CONFIG=${LLVM_CONFIG:-llvm-config}
  args+=("--with-llvm-config=$LLVM_CONFIG" --with-llvm-jit)
  # Static LLVM avoids requiring a Homebrew LLVM installation at runtime.
  export LLVM_LDFLAGS="$($LLVM_CONFIG --link-static --libfiles --system-libs)"
  if [[ $(uname) == Darwin ]]; then
    zstd=$(brew --prefix zstd)/lib/libzstd.a
    LLVM_LDFLAGS="${LLVM_LDFLAGS//-lzstd/$zstd} -Wl,-dead_strip,-dead_strip_dylibs"
    export CC=clang CXX=clang++
  fi
fi
GNATMAKE="gnatmake -j$JOBS" bash "$SOURCE/configure" "${args[@]}"
make -j"$JOBS"
make install
