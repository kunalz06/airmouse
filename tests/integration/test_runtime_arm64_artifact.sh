#!/usr/bin/env bash
set -euo pipefail

image_ref=${1:-}
if [[ -z "${image_ref}" ]]; then
  echo "usage: $0 IMAGE_REF" >&2
  exit 2
fi

metadata=$(docker image inspect "${image_ref}")
architecture=$(jq -r '.[0].Architecture' <<<"${metadata}")
os_name=$(jq -r '.[0].Os' <<<"${metadata}")
git_commit=$(jq -r '.[0].Config.Labels["org.opencontainers.image.revision"] // empty' <<<"${metadata}")
mavsdk_version=$(jq -r '.[0].Config.Labels["io.nidar.mavsdk.version"] // empty' <<<"${metadata}")
target_arch=$(jq -r '.[0].Config.Labels["io.nidar.target.architecture"] // empty' <<<"${metadata}")

[[ "${architecture}" == "arm64" ]]
[[ "${os_name}" == "linux" ]]
[[ -n "${git_commit}" && "${git_commit}" != "unknown" ]]
[[ "${mavsdk_version}" == "3.17.2" ]]
[[ "${target_arch}" == "linux/arm64" ]]

rootfs_tar=$(mktemp)
binary=$(mktemp)
listing=$(mktemp)
trap 'rm -f "${rootfs_tar}" "${binary}" "${listing}"' EXIT

container_id=$(docker create --platform linux/arm64 "${image_ref}")
trap 'docker rm -f "${container_id}" >/dev/null 2>&1 || true; rm -f "${rootfs_tar}" "${binary}" "${listing}"' EXIT
docker export "${container_id}" >"${rootfs_tar}"
docker rm "${container_id}" >/dev/null
tar --list --file="${rootfs_tar}" >"${listing}"

if ! grep -qx 'usr/local/bin/nidar-flight' "${listing}"; then
  echo "nidar-flight is absent from the runtime image" >&2
  exit 1
fi
tar --extract --to-stdout --file="${rootfs_tar}" usr/local/bin/nidar-flight >"${binary}"
tar --list --verbose --file="${rootfs_tar}" | awk '
  $NF == "usr/local/bin/nidar-flight" && $1 ~ /^-..x/ { found = 1 }
  END { exit found ? 0 : 1 }
'
readelf --file-header "${binary}" | grep -Eq 'AArch64|aarch64'

tar --extract --to-stdout --file="${rootfs_tar}" usr/local/lib/libmavsdk.so.3.17.2 |
  strings >"${binary}.mavsdk-strings"
trap 'docker rm -f "${container_id}" >/dev/null 2>&1 || true; rm -f "${rootfs_tar}" "${binary}" "${binary}.mavsdk-strings" "${listing}"' EXIT
if grep -Eqi 'ActionImpl|OffboardImpl|MissionImpl|MissionRawImpl|ParamImpl|MavlinkPassthroughImpl' "${binary}.mavsdk-strings"; then
  echo "active MAVSDK plugin symbols found in runtime library" >&2
  exit 1
fi
grep -Eq 'TelemetryImpl' "${binary}.mavsdk-strings"

for prohibited in \
  'usr/bin/gcc' 'usr/bin/g++' 'usr/bin/clang' 'usr/bin/cmake' 'usr/bin/ninja' \
  'usr/bin/git' 'usr/bin/gdb' 'usr/bin/gz' 'usr/bin/gazebo'; do
  if grep -qx "${prohibited}" "${listing}"; then
    echo "prohibited runtime tool found: ${prohibited}" >&2
    exit 1
  fi
done

if grep -Eq '(^|/)(PX4-Autopilot|workspace|build|include/mavsdk|googletest)(/|$)' "${listing}"; then
  echo "development, simulation, or source content found in runtime image" >&2
  exit 1
fi

if ! grep -Eq '(^|/)libmavsdk\.so' "${listing}"; then
  echo "libmavsdk.so is absent from the runtime image" >&2
  exit 1
fi

dependency_report=$(docker run --rm --platform linux/arm64 --entrypoint /bin/sh "${image_ref}" \
  -c 'ldd /usr/local/bin/nidar-flight /usr/local/lib/libmavsdk.so')
if grep -q 'not found' <<<"${dependency_report}"; then
  printf '%s\n' "${dependency_report}" >&2
  echo "runtime dynamic library resolution failed" >&2
  exit 1
fi

echo "runtime ARM64 artifact policy passed: ${image_ref}"
