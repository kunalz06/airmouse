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
docker_timeout_seconds="${NIDAR_SITL_DOCKER_TIMEOUT_SECONDS:-10}"
sim_name=""
client_name=""
run_dir=""
run_token=""
sim_cidfile=""
client_cidfile=""
owned_container_id=""
sitl_lock_file="/tmp/nidar-sitl-vehicle.lock"
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
pending_signal_status=0

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

read_container_id() {
  local cidfile="$1"
  local container_id

  [[ -r "${cidfile}" ]] || return 1
  container_id="$(<"${cidfile}")"
  [[ "${container_id}" =~ ^[a-f0-9]{64}$ ]] || return 1
  printf '%s\n' "${container_id}"
}

is_confirmed_absent_container_error() {
  local reference="$1"
  local error="$2"
  case "${error}" in
    "Error: No such object: ${reference}" | \
    "Error: No such container: ${reference}" | \
    "Error response from daemon: No such object: ${reference}" | \
    "Error response from daemon: No such container: ${reference}") return 0 ;;
  esac
  return 1
}

inspect_owned_container() {
  local reference="$1"
  local role="$2"
  owned_container_id=""
  local remaining
  if ! remaining="$(cleanup_remaining_seconds)"; then
    record_cleanup_failure "cleanup deadline expired before verifying ${role} container"
    return 1
  fi

  local inspect_output inspect_error inspect_error_file status
  if ! inspect_error_file="$(mktemp "${run_dir}/inspect.XXXXXX")"; then
    record_cleanup_failure "failed to allocate ownership verification state"
    return 2
  fi
  if inspect_output="$(timeout --foreground --signal=TERM --kill-after=1s "${remaining}s" \
    docker container inspect --format '{{.Id}}\t{{index .Config.Labels "io.nidar.sitl.token"}}' \
      "${reference}" 2>"${inspect_error_file}")"; then
    :
  else
    status=$?
    inspect_error="$(<"${inspect_error_file}")"
    rm -f "${inspect_error_file}"
    if ((status == 1)) && is_confirmed_absent_container_error "${reference}" "${inspect_error}"; then
      return 1
    fi
    record_cleanup_failure "could not verify ownership of ${role} container"
    return 2
  fi
  rm -f "${inspect_error_file}"
  if [[ ! "${inspect_output}" =~ ^([a-f0-9]{64})\\t${run_token}$ ]]; then
    record_cleanup_failure "could not verify ownership of ${role} container"
    return 2
  fi
  owned_container_id="${BASH_REMATCH[1]}"
}

remove_owned_container() {
  local cidfile="$1"
  local name="$2"
  local role="$3"
  local container_id inspect_status
  if container_id="$(read_container_id "${cidfile}")"; then
    if inspect_owned_container "${container_id}" "${role}"; then
      container_id="${owned_container_id}"
    else
      inspect_status=$?
      ((inspect_status == 1)) && return 0
      return 1
    fi
  elif inspect_owned_container "${name}" "${role}"; then
    container_id="${owned_container_id}"
  else
    inspect_status=$?
    ((inspect_status == 1)) && return 0
    return 1
  fi

  local remaining
  if ! remaining="$(cleanup_remaining_seconds)"; then
    record_cleanup_failure "cleanup deadline expired before removing ${role} container"
    return 1
  fi
  if timeout --foreground --signal=TERM --kill-after=1s "${remaining}s" \
    docker rm -f "${container_id}" >/dev/null 2>&1; then
    if inspect_owned_container "${container_id}" "${role}"; then
      record_cleanup_failure "${role} container remained after cleanup"
      return 1
    else
      inspect_status=$?
      ((inspect_status == 1)) && return 0
      return 1
    fi
  fi
  record_cleanup_failure "failed to remove ${role} container during cleanup"
  return 1
}

check_required_image() {
  local image="$1"
  local description="$2"
  if ! timeout --foreground --signal=TERM --kill-after=1s "${docker_timeout_seconds}s" \
    docker image inspect "${image}" >/dev/null 2>&1; then
    echo "required ${description} is unavailable: ${image}" >&2
    return 1
  fi
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
    if ! remove_owned_container "${client_cidfile}" "${client_name}" client; then
      : # The helper already recorded the bounded cleanup failure.
    fi
  fi
  if ! reap_logger; then
    : # The helper already recorded the bounded cleanup failure.
  fi
  if [[ "${sim_started}" == true ]]; then
    if ! remove_owned_container "${sim_cidfile}" "${sim_name}" simulator; then
      : # The helper already recorded the bounded cleanup failure.
    fi
  fi
  if [[ -n "${run_dir}" ]]; then
    rm -rf "${run_dir}"
    run_dir=""
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

defer_signal() {
  pending_signal_status="$1"
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
if ! [[ "${docker_timeout_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NIDAR_SITL_DOCKER_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if ! command -v flock >/dev/null 2>&1; then
  echo "flock is required to serialize fixed-port SITL runs" >&2
  exit 2
fi
exec {sitl_lock_fd}>"${sitl_lock_file}"
if ! flock -n "${sitl_lock_fd}"; then
  echo "another Phase 3A vehicle SITL run owns UDP ${listen_port}" >&2
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

if ! check_required_image "${sim_image}" simulation image; then
  exit 2
fi
if ! check_required_image "${dev_image}" development image; then
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
if ! run_dir="$(mktemp -d "${TMPDIR:-/tmp}/nidar-sitl-vehicle.XXXXXXXX")"; then
  echo "failed to create private SITL container state directory" >&2
  exit 2
fi
if ! run_token="$(od -An -N16 -tx1 /dev/urandom | tr -d '[:space:]')" ||
   ! [[ "${run_token}" =~ ^[a-f0-9]{32}$ ]]; then
  echo "failed to create unique SITL container ownership token" >&2
  exit 2
fi
sim_name="nidar-sitl-vehicle-px4-${run_token}"
client_name="nidar-sitl-vehicle-client-${run_token}"
sim_cidfile="${run_dir}/sim.cid"
client_cidfile="${run_dir}/client.cid"

trap 'defer_signal 130' INT
trap 'defer_signal 143' TERM
python3 "${project_root}/scripts/bounded-log.py" \
  --output "${sim_log}" --max-bytes "${log_max_bytes}" -- \
  docker run --name "${sim_name}" --cidfile "${sim_cidfile}" \
    --label "io.nidar.sitl.token=${run_token}" --network host --init \
    -v "${overlay}:${px4_root}/etc/init.d-posix/px4-rc.mavlink:ro" \
    -e HEADLESS=1 "${sim_image}" \
    bash -lc 'cd /opt/PX4-Autopilot && make px4_sitl gz_x500' &
sim_pid=$!
sim_started=true
trap 'exit 130' INT
trap 'exit 143' TERM
if ((pending_signal_status != 0)); then
  exit "${pending_signal_status}"
fi

set +e
client_started=true
# The collector owns the independent client wallclock cap so it can flush the
# atomic bounded diagnostic log after terminating an unresponsive Docker run.
python3 "${project_root}/scripts/bounded-log.py" \
  --output "${client_log}" --max-bytes "${log_max_bytes}" \
  --timeout-seconds "${client_timeout_seconds}" --kill-after-seconds 10 -- \
  docker run --rm --name "${client_name}" --cidfile "${client_cidfile}" \
    --label "io.nidar.sitl.token=${run_token}" --network host --init \
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
