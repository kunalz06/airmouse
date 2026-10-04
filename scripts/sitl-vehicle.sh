#!/usr/bin/env bash
# Bounded Phase 3A PX4 X500 discovery and telemetry verification.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sim_image="${NIDAR_SIM_IMAGE:-nidar-px4-sim:v1.17.0-x500}"
dev_image="${NIDAR_DEV_IMAGE:-nidar-dev}"
client_binary="${NIDAR_CLIENT_BINARY:-build/dev/nidar-flight}"
timeout_seconds="${NIDAR_SITL_TIMEOUT_SECONDS:-90}"
sim_name="nidar-sitl-vehicle-px4"
client_name="nidar-sitl-vehicle-client"
listen_port=14540
output_dir="${project_root}/simulation/output/phase-3a"
sim_log="${output_dir}/px4-sitl.log"
client_log="${output_dir}/nidar-flight.log"
overlay="${project_root}/simulation/scripts/px4-rc.mavlink"
px4_root="/opt/PX4-Autopilot/build/px4_sitl_default"
cleanup_started=false

cleanup() {
  if [[ "${cleanup_started}" == true ]]; then
    return
  fi
  cleanup_started=true
  docker rm -f "${client_name}" >/dev/null 2>&1 || true
  docker rm -f "${sim_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if ! [[ "${timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NIDAR_SITL_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi

python3 - "${listen_port}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.bind(("127.0.0.1", port))
except OSError as error:
    print(f"required UDP port is unavailable: {error}", file=sys.stderr)
    raise SystemExit(1)
finally:
    sock.close()
PY

for name in "${sim_name}" "${client_name}"; do
  if docker container inspect "${name}" >/dev/null 2>&1; then
    echo "refusing to replace existing container: ${name}" >&2
    exit 2
  fi
done

if ! docker image inspect "${sim_image}" >/dev/null 2>&1; then
  echo "required simulation image is unavailable: ${sim_image}" >&2
  exit 2
fi
if ! docker image inspect "${dev_image}" >/dev/null 2>&1; then
  echo "required development image is unavailable: ${dev_image}" >&2
  exit 2
fi
if [[ ! -x "${project_root}/${client_binary}" ]]; then
  echo "${client_binary} is unavailable; run the required build first" >&2
  exit 2
fi
if [[ ! -r "${overlay}" ]]; then
  echo "required PX4 startup overlay is unavailable: ${overlay}" >&2
  exit 2
fi

mkdir -p "${output_dir}"
: >"${sim_log}"
: >"${client_log}"

docker run --name "${sim_name}" --network host --init   -v "${overlay}:${px4_root}/etc/init.d-posix/px4-rc.mavlink:ro"   -e HEADLESS=1 "${sim_image}"   bash -lc 'cd /opt/PX4-Autopilot && make px4_sitl gz_x500'   >"${sim_log}" 2>&1 &
sim_pid=$!

set +e
docker run --rm --name "${client_name}" --network host --init   -v "${project_root}:/workspace:ro" -w /workspace   "${dev_image}"   "${client_binary}"     --sim     --endpoint udpin://127.0.0.1:14540     --discovery-timeout-ms "$((timeout_seconds * 1000))"     --telemetry-max-age-ms 2000     --telemetry-wait-ms 15000   >"${client_log}" 2>&1
client_status=$?
set -e

if [[ ${client_status} -ne 0 ]]; then
  echo "Phase 3A vehicle SITL failed; client output:" >&2
  tail -n 100 "${client_log}" >&2 || true
  echo "recent PX4 output:" >&2
  tail -n 100 "${sim_log}" >&2 || true
  exit "${client_status}"
fi

grep -Fx "connection=connected" "${client_log}" >/dev/null
grep -Fx "component=companion-computer" "${client_log}" >/dev/null
grep -Fx "forwarding=off" "${client_log}" >/dev/null
grep -Fx "telemetry=ready" "${client_log}" >/dev/null

echo "Phase 3A client diagnostics:"
cat "${client_log}"

docker stop --time 10 "${sim_name}" >/dev/null || true
wait "${sim_pid}" || true
docker rm "${sim_name}" >/dev/null 2>&1 || true

if docker container inspect "${client_name}" >/dev/null 2>&1 ||
   docker container inspect "${sim_name}" >/dev/null 2>&1; then
  echo "Phase 3A container remained after shutdown" >&2
  exit 1
fi

echo "Phase 3A vehicle SITL passed."
