#!/usr/bin/env bash
# Explicit, reviewable generation of the first or intentionally updated APT lock.
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
if ! docker buildx inspect nidar-builder >/dev/null 2>&1; then
  echo "required buildx builder 'nidar-builder' is unavailable" >&2
  exit 1
fi
if [[ -e config/apt-closure.lock.json ]]; then
  echo "refusing to overwrite existing APT closure lock; remove it only in a reviewed intentional regeneration" >&2
  exit 1
fi

inventory_dir=$(mktemp -d "${TMPDIR:-/tmp}/nidar-apt-closure.XXXXXX")
trap 'rm -rf "${inventory_dir}"' EXIT

docker buildx build \
  --builder nidar-builder \
  --platform linux/arm64 \
  --file docker/runtime/Dockerfile \
  --target apt-closure-export \
  --build-arg NIDAR_APT_LOCK_MODE=bootstrap \
  --build-arg NIDAR_APT_BASELINE_GENERATION=1 \
  --output "type=local,dest=${inventory_dir}" \
  .
python3 scripts/verify-runtime-apt-closure.py --inventory-dir "${inventory_dir}" --write-lock
python3 scripts/verify-runtime-apt-closure.py --check-repository
echo "APT closure candidate generated. Inspect all config/apt-closure/*.tsv and config/apt-closure.lock.json, then rebuild normally before committing."
