#!/usr/bin/env bash
set -euo pipefail

image_ref=${1:-}
if [[ -z "${image_ref}" || $# -ne 1 ]]; then
  echo "usage: $0 IMAGE_REF" >&2
  exit 2
fi

# Initial clean Phase 4A image: 173,576,024 uncompressed bytes.
# 220,000,000 allows ~27% headroom for patched OS/runtime dependencies.
max_bytes=${NIDAR_MAX_RUNTIME_BYTES:-220000000}
if ! [[ "${max_bytes}" =~ ^[0-9]+$ ]] || (( max_bytes < 1 )); then
  echo "NIDAR_MAX_RUNTIME_BYTES must be a positive integer" >&2
  exit 2
fi

metadata=$(docker image inspect "${image_ref}")
actual_bytes=$(jq -er '.[0].Size' <<<"${metadata}")
architecture=$(jq -er '.[0].Architecture' <<<"${metadata}")
[[ "${architecture}" == arm64 ]] || { echo "wrong architecture: ${architecture}" >&2; exit 1; }
(( actual_bytes <= max_bytes )) || {
  echo "runtime exceeds size budget: ${actual_bytes} > ${max_bytes} bytes" >&2
  exit 1
}

docker run --rm --platform linux/arm64 --entrypoint /bin/sh "${image_ref}" -eu -c '
  test "$(id -u)" != 0
  grep -q "^ID=ubuntu$" /etc/os-release
  grep -q "^VERSION_ID=\"24.04\"$" /etc/os-release
  for tool in gcc g++ clang cmake ninja git gdb gz gazebo; do
    if command -v "$tool" >/dev/null 2>&1; then
      echo "prohibited tool in runtime: $tool" >&2
      exit 1
    fi
  done
  for path in /workspace /opt/mavsdk-src /opt/mavsdk-build /usr/include/mavsdk \
              /usr/src/googletest /root/.ccache /root/.cache; do
    if [ -d "$path" ] && [ -n "$(find "$path" -mindepth 1 -print -quit)" ]; then
      echo "prohibited runtime content: $path" >&2
      exit 1
    fi
  done
  if [ -d /var/cache/apt/archives ] && \
     [ -n "$(find /var/cache/apt/archives -maxdepth 1 -type f -name "*.deb" -print -quit)" ]; then
    echo "cached apt packages leaked into runtime" >&2
    exit 1
  fi
  if [ -d /var/lib/apt/lists ] && [ -n "$(find /var/lib/apt/lists -type f -print -quit)" ]; then
    echo "apt package lists leaked into runtime" >&2
    exit 1
  fi
'
printf 'runtime image policy passed: image=%s, bytes=%s, max=%s\n' \
  "${image_ref}" "${actual_bytes}" "${max_bytes}"
