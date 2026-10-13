#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${project_root}"

mapfile -d '' files < <(
  find apps include src     -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' \)     ! -path 'src/vehicle/*' -print0
)

if (( ${#files[@]} > 0 )); then
  if grep -nH -E '#include[[:space:]]*<mavsdk/' "${files[@]}"; then
    echo "MAVSDK include escaped src/vehicle" >&2
    exit 1
  fi
  if grep -nH -E 'mavsdk::' "${files[@]}"; then
    echo "MAVSDK symbol escaped src/vehicle" >&2
    exit 1
  fi
fi

if grep -R -nE   'mavsdk/(action|offboard|mission|mission_raw|param)|mavsdk::(Action|Offboard|Mission|MissionRaw|Param)'   src/vehicle; then
  echo "active-command MAVSDK plugin is forbidden in Phase 3A" >&2
  exit 1
fi

adapter="src/vehicle/mavsdk_vehicle.cpp"
if grep -nE -- '->[[:space:]]*remove_connection[[:space:]]*\(' "${adapter}"; then
  echo "connection teardown must be owned by the dedicated Mavsdk destructor" >&2
  exit 1
fi
grep -Fq "Each bundle exclusively owns its SDK instance" "${adapter}"
grep -Fq "sdk.reset();" "${adapter}"
