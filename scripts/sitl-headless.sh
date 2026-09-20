#!/usr/bin/env bash
# Start one bounded, passive PX4 X500 SITL smoke run.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${NIDAR_SIM_IMAGE:-nidar-px4-sim:v1.17.0-x500}"
timeout_seconds="${NIDAR_SITL_TIMEOUT_SECONDS:-90}"
simulation_name="nidar-sitl-headless"
smoke_name="nidar-sitl-smoke"
smoke_port=14560
qgc_source_port=14551
smoke_source_port=14561
output_dir="${project_root}/simulation/output/phase-2"
simulation_log="${output_dir}/sitl-headless.log"
smoke_log="${output_dir}/sitl-smoke.log"
overlay="${project_root}/simulation/scripts/px4-rc.mavlink"
px4_root="/opt/PX4-Autopilot/build/px4_sitl_default"
cleanup_started=false

require_free_udp_ports() {
  python3 - "${smoke_port}" "${qgc_source_port}" "${smoke_source_port}" <<'PY'
import socket
import sys

sockets = []
try:
    for value in sys.argv[1:]:
        port = int(value)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))
        sockets.append(sock)
except OSError as error:
    print(f"required UDP port is unavailable: {error}", file=sys.stderr)
    raise SystemExit(1)
finally:
    for sock in sockets:
        sock.close()
PY
}

cleanup() {
  if [[ "${cleanup_started}" == true ]]; then
    return
  fi
  cleanup_started=true
  docker rm -f "${simulation_name}" >/dev/null 2>&1 || true
  docker rm -f "${smoke_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if ! [[ "${timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NIDAR_SITL_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if ! docker image inspect "${image}" >/dev/null; then
  echo "required simulation image is unavailable: ${image}" >&2
  exit 2
fi
if [[ ! -r "${overlay}" ]]; then
  echo "required PX4 MAVLink startup overlay is unavailable: ${overlay}" >&2
  exit 2
fi
for name in "${simulation_name}" "${smoke_name}"; do
  if docker container inspect "${name}" >/dev/null 2>&1; then
    echo "refusing to replace existing container: ${name}" >&2
    exit 2
  fi
done

require_free_udp_ports
mkdir -p "${output_dir}"
: >"${simulation_log}"
: >"${smoke_log}"

docker run --rm --name "${smoke_name}" --network host --init \
  -v "${project_root}/scripts:/nidar/scripts:ro" \
  --entrypoint python3 "${image}" \
  /nidar/scripts/sitl-smoke.py --port "${smoke_port}" --timeout "${timeout_seconds}" \
  >"${smoke_log}" 2>&1 &
smoke_pid=$!

docker run --name "${simulation_name}" --network host --init \
  -v "${overlay}:${px4_root}/etc/init.d-posix/px4-rc.mavlink:ro" \
  -e HEADLESS=1 "${image}" \
  bash -lc 'cd /opt/PX4-Autopilot && make px4_sitl gz_x500' \
  >"${simulation_log}" 2>&1 &
simulation_pid=$!

set +e
wait "${smoke_pid}"
smoke_status=$?
set -e

if [[ "${smoke_status}" -ne 0 ]]; then
  echo "SITL smoke test failed; recent simulator output:" >&2
  tail -n 80 "${simulation_log}" >&2 || true
  echo "Smoke output:" >&2
  tail -n 80 "${smoke_log}" >&2 || true
  exit "${smoke_status}"
fi

echo "SITL smoke test passed; stopping ${simulation_name}."
docker stop --time 10 "${simulation_name}" >/dev/null || true
wait "${simulation_pid}" || true
docker rm "${simulation_name}" >/dev/null || true

if docker container inspect "${simulation_name}" >/dev/null 2>&1; then
  echo "simulation container remained after shutdown: ${simulation_name}" >&2
  exit 1
fi
