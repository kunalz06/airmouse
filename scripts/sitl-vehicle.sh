#!/usr/bin/env bash
# Bounded Phase 3A PX4 X500 discovery and telemetry verification.
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "scripts/sitl-vehicle.sh must be executed, not sourced" >&2
  return 2
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sim_image="${NIDAR_SIM_IMAGE:-nidar-px4-sim:v1.17.0-x500}"
dev_image="${NIDAR_DEV_IMAGE:-nidar-dev}"
client_binary="${NIDAR_CLIENT_BINARY:-build/dev/nidar-flight}"
timeout_seconds="${NIDAR_SITL_TIMEOUT_SECONDS:-90}"
client_timeout_seconds="${NIDAR_SITL_CLIENT_TIMEOUT_SECONDS:-120}"
cleanup_timeout_seconds="${NIDAR_SITL_CLEANUP_TIMEOUT_SECONDS:-30}"
sim_name="nidar-sitl-vehicle-px4"
client_name="nidar-sitl-vehicle-client"
listen_port=14540
output_dir="${project_root}/simulation/output/phase-3a"
sim_log="${output_dir}/px4-sitl.log"
client_log="${output_dir}/nidar-flight.log"
log_max_bytes=524288
overlay="${project_root}/simulation/scripts/px4-rc.mavlink"
px4_root="/opt/PX4-Autopilot/build/px4_sitl_default"
cleanup_started=false
cleanup_result=0
cleanup_deadline=0
sim_pid=""
sim_started=false
client_started=false

cleanup_remaining_seconds() {
  local remaining=$((cleanup_deadline - SECONDS))
  if ((remaining <= 0)); then
    return 1
  fi
  printf '%s\n' "${remaining}"
}

record_cleanup_failure() {
  echo "$*" >&2
  cleanup_result=1
}

inspect_cleanup_container() {
  local name="$1"
  local remaining
  if ! remaining="$(cleanup_remaining_seconds)"; then
    record_cleanup_failure "cleanup deadline expired before inspecting ${name}"
    return 2
  fi

  local status
  if timeout --foreground --signal=TERM --kill-after=1s "${remaining}s" \
    docker container inspect "${name}" >/dev/null 2>&1; then
    return 0
  else
    status=$?
  fi
  if ((status == 1)); then
    return 1
  fi
  record_cleanup_failure "failed to inspect ${name} during cleanup (status ${status})"
  return 2
}

remove_cleanup_container() {
  local name="$1"
  local inspected
  if inspect_cleanup_container "${name}"; then
    inspected=0
  else
    inspected=$?
  fi
  if ((inspected == 1)); then
    return 0
  fi
  if ((inspected != 0)); then
    return 1
  fi

  local remaining
  if ! remaining="$(cleanup_remaining_seconds)"; then
    record_cleanup_failure "cleanup deadline expired before removing ${name}"
    return 1
  fi
  local status
  if timeout --foreground --signal=TERM --kill-after=1s "${remaining}s" \
    docker rm -f "${name}" >/dev/null 2>&1; then
    status=0
  else
    status=$?
    record_cleanup_failure "failed to remove ${name} during cleanup (status ${status})"
  fi

  if inspect_cleanup_container "${name}"; then
    record_cleanup_failure "container remained after cleanup: ${name}"
    return 1
  else
    inspected=$?
  fi
  if ((inspected != 1)); then
    return 1
  fi
  return "${status}"
}

terminate_logger() {
  if [[ -n "${sim_pid}" ]] && kill -0 "${sim_pid}" >/dev/null 2>&1; then
    kill -TERM "${sim_pid}" >/dev/null 2>&1 || true
  fi
}

reap_logger() {
  local remaining
  if [[ -z "${sim_pid}" ]]; then
    return 0
  fi

  while kill -0 "${sim_pid}" >/dev/null 2>&1; do
    if ! remaining="$(cleanup_remaining_seconds)"; then
      record_cleanup_failure "cleanup deadline expired while reaping PX4 logger"
      kill -KILL "${sim_pid}" >/dev/null 2>&1 || true
      return 1
    fi
    sleep 0.1
  done
  # The liveness check above guarantees this wait only reaps an exited child.
  wait "${sim_pid}" >/dev/null 2>&1 || true
  sim_pid=""
}

cleanup() {
  if [[ "${cleanup_started}" == true ]]; then
    return "${cleanup_result}"
  fi
  cleanup_started=true
  if ! [[ "${cleanup_timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
    record_cleanup_failure "cleanup timeout is invalid: ${cleanup_timeout_seconds}"
    return "${cleanup_result}"
  fi
  cleanup_deadline=$((SECONDS + cleanup_timeout_seconds))

  terminate_logger
  if [[ "${client_started}" == true ]]; then
    if ! remove_cleanup_container "${client_name}"; then
      : # The helper already recorded the bounded cleanup failure.
    fi
  fi
  if [[ "${sim_started}" == true ]]; then
    if ! remove_cleanup_container "${sim_name}"; then
      : # The helper already recorded the bounded cleanup failure.
    fi
  fi
  if ! reap_logger; then
    : # The helper already recorded the bounded cleanup failure.
  fi

  if ((cleanup_result != 0)); then
    echo "Phase 3A SITL cleanup failed before its ${cleanup_timeout_seconds}s deadline" >&2
  fi
  return "${cleanup_result}"
}

on_exit() {
  local original_status=$?
  trap - EXIT
  if ! cleanup && ((original_status == 0)); then
    exit 1
  fi
  exit "${original_status}"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ! [[ "${timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NIDAR_SITL_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if ! [[ "${client_timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NIDAR_SITL_CLIENT_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if ! [[ "${cleanup_timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NIDAR_SITL_CLEANUP_TIMEOUT_SECONDS must be a positive integer" >&2
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

python3 "${project_root}/scripts/bounded-log.py" \
  --output "${sim_log}" --max-bytes "${log_max_bytes}" -- \
  docker run --name "${sim_name}" --network host --init \
    -v "${overlay}:${px4_root}/etc/init.d-posix/px4-rc.mavlink:ro" \
    -e HEADLESS=1 "${sim_image}" \
    bash -lc 'cd /opt/PX4-Autopilot && make px4_sitl gz_x500' &
sim_pid=$!
sim_started=true

set +e
client_started=true
timeout --foreground --signal=TERM --kill-after=10s "${client_timeout_seconds}s" \
  python3 "${project_root}/scripts/bounded-log.py" \
    --output "${client_log}" --max-bytes "${log_max_bytes}" -- \
    docker run --rm --name "${client_name}" --network host --init \
      -v "${project_root}:/workspace:ro" -w /workspace \
      "${dev_image}" "${client_binary}" \
        --sim \
        --endpoint udpin://127.0.0.1:14540 \
        --discovery-timeout-ms "$((timeout_seconds * 1000))" \
        --telemetry-max-age-ms 2000 \
        --telemetry-wait-ms 15000
client_status=$?
set -e

if [[ ${client_status} -ne 0 ]]; then
  # Flush the bounded PX4 logger before printing its final diagnostics. The
  # EXIT trap is then a no-op because cleanup has already run.
  if ! cleanup; then
    echo "Phase 3A SITL cleanup failed after client failure" >&2
  fi
  if [[ ${client_status} -eq 124 ]]; then
    echo "Phase 3A vehicle SITL client exceeded ${client_timeout_seconds}s hard timeout" >&2
  fi
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

if ! cleanup; then
  exit 1
fi

echo "Phase 3A vehicle SITL passed."
