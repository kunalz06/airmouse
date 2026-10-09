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
# One wall-clock timestamp is captured by CI in GITHUB_ENV and reused for
# both --load and --output. It is NEVER the commit timestamp.
source_timestamp=$(git show -s --format=%cI HEAD)
build_timestamp=${NIDAR_BUILD_TIMESTAMP:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}
ci_run_id=${GITHUB_RUN_ID:-local}
ci_run_attempt=${GITHUB_RUN_ATTEMPT:-0}
ci_workflow=${GITHUB_WORKFLOW:-local}
ci_sha=${GITHUB_SHA:-${git_commit}}
ci_pr_head_sha=${NIDAR_PR_HEAD_SHA:-${git_commit}}
ci_repository=${GITHUB_REPOSITORY:-local}
if ! [[ "${ci_pr_head_sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "CI PR head SHA must be an exact 40-character Git SHA" >&2
  exit 1
fi
if [[ "${ci_sha}" != "${git_commit}" ]]; then
  echo "CI checked-out Git commit does not match GITHUB_SHA" >&2
  exit 1
fi
if [[ "${ci_run_id}" != local ]]; then
  [[ "${ci_run_id}" =~ ^[1-9][0-9]*$ && "${ci_run_attempt}" =~ ^[1-9][0-9]*$ ]] || {
    echo "CI run id/attempt must be positive numeric values" >&2
    exit 1
  }
  [[ -n "${NIDAR_BUILD_TIMESTAMP:-}" ]] || {
    echo "CI must export NIDAR_BUILD_TIMESTAMP once before both builds" >&2
    exit 1
  }
fi
python3 - "${build_timestamp}" "${source_timestamp}" <<'VALIDATE_TIME'
from datetime import datetime, timezone
import sys
built = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
source = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
if built.tzinfo is None or built.utcoffset().total_seconds() != 0:
    raise SystemExit("build timestamp must carry a UTC timezone")
if source.tzinfo is None:
    raise SystemExit("source commit timestamp must carry a timezone")
if (built - datetime.now(timezone.utc)).total_seconds() > 300:
    raise SystemExit("build timestamp appears in the future")
if built.timestamp() < source.timestamp():
    raise SystemExit("build wall-clock timestamp is before source commit")
VALIDATE_TIME
runtime_base_digest=$(awk -F '"' '/^ubuntu_24_04_image_index =/ { print $2 }' config/versions.lock)
mavsdk_source_url=$(awk -F '"' '/^mavsdk_arm64_source_url =/ { print $2 }' config/versions.lock)
mavsdk_source_commit=$(awk -F '"' '/^mavsdk_arm64_source_commit =/ { print $2 }' config/versions.lock)
test -n "${runtime_base_digest}"
test -n "${mavsdk_source_url}"
test -n "${mavsdk_source_commit}"

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
  --build-arg "NIDAR_SOURCE_TIMESTAMP=${source_timestamp}"
  --build-arg "NIDAR_CI_RUN_ID=${ci_run_id}"
  --build-arg "NIDAR_CI_RUN_ATTEMPT=${ci_run_attempt}"
  --build-arg "NIDAR_CI_WORKFLOW=${ci_workflow}"
  --build-arg "NIDAR_CI_SHA=${ci_sha}"
  --build-arg "NIDAR_CI_HEAD_SHA=${ci_pr_head_sha}"
  --build-arg "NIDAR_CI_REPOSITORY=${ci_repository}"
  --build-arg "RUNTIME_BASE_DIGEST=${runtime_base_digest}"
  --build-arg "MAVSDK_SOURCE_URL=${mavsdk_source_url}"
  --build-arg "MAVSDK_SOURCE_COMMIT=${mavsdk_source_commit}"
)

if [[ "${load_image}" == true ]]; then
  docker buildx build "${build_args[@]}" --load .
else
  mkdir -p "$(dirname "${output_path}")"
  docker buildx build "${build_args[@]}" --output "type=oci,dest=${output_path}" .
  printf 'OCI artifact: %s\n' "${output_path}"
fi
