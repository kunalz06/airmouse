#!/usr/bin/env bash
set -euo pipefail

image_ref="nidar-runtime:phase-4a-local"
output_path="build/release/nidar-runtime-arm64.oci.tar"
load_image=false

usage() {
  cat <<'EOF'
Usage: scripts/build-runtime-arm64.sh [--load] [--image-ref IMAGE] [--output OCI_TAR]

Builds the pinned NIDAR runtime for linux/arm64. By default it exports an OCI
archive; --load imports the ARM64 image into the local Docker store only when
container-based verification requires it.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --load) load_image=true; shift ;;
  --image-ref) image_ref=${2:?--image-ref requires a value}; shift 2 ;;
  --output) output_path=${2:?--output requires a value}; shift 2 ;;
  --help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
  esac
done

git_commit=$(git rev-parse HEAD)
build_timestamp=$(git show -s --format=%cI HEAD)
runtime_base_digest=$(awk -F '"' '/^ubuntu_24_04_image_index =/ { print $2 }' config/versions.lock)
test -n "${runtime_base_digest}"

if ! docker buildx inspect nidar-builder >/dev/null 2>&1; then
  echo "required buildx builder 'nidar-builder' is unavailable" >&2
  exit 1
fi

build_args=(
  --builder nidar-builder
  --platform linux/arm64
  --file docker/runtime/Dockerfile
  --tag "${image_ref}"
  --build-arg "NIDAR_GIT_COMMIT=${git_commit}"
  --build-arg "NIDAR_BUILD_TIMESTAMP=${build_timestamp}"
  --build-arg "RUNTIME_BASE_DIGEST=${runtime_base_digest}"
)

if [[ "${load_image}" == true ]]; then
  docker buildx build "${build_args[@]}" --load .
else
  mkdir -p "$(dirname "${output_path}")"
  docker buildx build "${build_args[@]}" --output "type=oci,dest=${output_path}" .
  printf 'OCI artifact: %s\n' "${output_path}"
fi
