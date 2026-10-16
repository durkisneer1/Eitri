#!/usr/bin/env bash
set -euo pipefail
llvm_version=${1:?Pass llvm-config --version}
zstd_version=$(brew list --versions zstd | awk '{print $2}' | cut -d_ -f1)
mkdir -p work/macos-notices
curl -fL --retry 3 -o work/macos-notices/LLVM-LICENSE.txt "https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-$llvm_version/llvm/LICENSE.TXT"
curl -fL --retry 3 -o work/macos-notices/GCC-COPYING3.txt https://raw.githubusercontent.com/gcc-mirror/gcc/releases/gcc-14.2.0/COPYING3
curl -fL --retry 3 -o work/macos-notices/GCC-RUNTIME-EXCEPTION.txt https://raw.githubusercontent.com/gcc-mirror/gcc/releases/gcc-14.2.0/COPYING.RUNTIME
curl -fL --retry 3 -o work/macos-notices/ZSTD-LICENSE.txt "https://raw.githubusercontent.com/facebook/zstd/v$zstd_version/LICENSE"
printf 'GNAT: 14.2.0-1\nLLVM: %s\nzstd: %s\n' "$llvm_version" "$zstd_version" > work/macos-notices/versions.txt
