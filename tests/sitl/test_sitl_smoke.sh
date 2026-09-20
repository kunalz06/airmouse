#!/usr/bin/env bash
# Verify that the passive listener fails clearly when no MAVLink source exists.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
image="${NIDAR_SIM_IMAGE:-nidar-px4-sim:v1.17.0-x500}"

set +e
output="$(docker run --rm --network host \
  -v "${project_root}/scripts:/nidar/scripts:ro" \
  --entrypoint python3 "${image}" \
  /nidar/scripts/sitl-smoke.py --port 14560 --timeout 0.2 2>&1)"
status=$?
set -e

if [[ ${status} -ne 1 ]] || [[ "${output}" != *"timed out waiting for PX4 HEARTBEAT and LOCAL_POSITION_NED"* ]]; then
  printf 'expected a bounded passive-listener timeout; status=%s output=%s\n' \
    "${status}" "${output}" >&2
  exit 1
fi
