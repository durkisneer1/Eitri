#!/usr/bin/env bash
set -euo pipefail
mkdir -p work
archive=work/gnat.tar.gz
curl -fL --retry 3 -o "$archive" https://github.com/alire-project/GNAT-FSF-builds/releases/download/gnat-14.2.0-1/gnat-aarch64-darwin-14.2.0-1.tar.gz
printf '%s  %s\n' cc5517d65c2074807c8ae97b671e852ed70e307a457e7acde0a848a9394e31c5 "$archive" | shasum -a 256 -c -
tar -xzf "$archive" -C work
if [[ -n ${GITHUB_PATH:-} ]]; then
  echo "$(pwd)/work/gnat-aarch64-darwin-14.2.0-1/bin" >> "$GITHUB_PATH"
fi
