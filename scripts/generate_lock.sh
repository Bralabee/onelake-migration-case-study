#!/usr/bin/env bash
set -euo pipefail

# Generate multi-platform conda lock files from environment.yml
# Requires conda-lock in the environment (included in environment.yml)
# Usage: ./scripts/generate_lock.sh

if [ ! -f environment.yml ]; then
  echo "environment.yml not found in current directory" >&2
  exit 1
fi

PLATFORMS=(linux-64 osx-arm64 osx-64 win-64)
OUT_DIR=locks
mkdir -p "$OUT_DIR"

echo "Generating lock files for: ${PLATFORMS[*]}"
conda-lock lock -f environment.yml ${PLATFORMS[@]/#/--platform } --filename-template "{platform}.lock.yml" --lockfile "$OUT_DIR/conda-lock.yml" || {
  echo "conda-lock multi-platform generation failed" >&2
  exit 1
}

echo "Done. Lock files in $OUT_DIR/ :"
ls -1 "$OUT_DIR"

echo "Create env from a specific lock file, e.g.:"
echo "  conda-lock install --name onelake-migration locks/linux-64.lock.yml"
