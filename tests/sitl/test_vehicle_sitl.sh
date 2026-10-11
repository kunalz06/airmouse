#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mode="${1:---normal}"

if [[ "${mode}" == "--normal" ]]; then
  exec "${project_root}/scripts/sitl-vehicle.sh"
fi

if [[ "${mode}" != "--occupied-port" &&
      "${mode}" != "--fake-docker-cleanup" &&
      "${mode}" != "--signal-during-launch" ]]; then
  echo "usage: $0 [--normal|--occupied-port|--fake-docker-cleanup|--signal-during-launch]" >&2
  exit 2
fi

if [[ "${mode}" == "--fake-docker-cleanup" || "${mode}" == "--signal-during-launch" ]]; then
  fixture_dir="$(mktemp -d)"
  fake_bin="${fixture_dir}/bin"
  fake_state="${fixture_dir}/state"
  fake_calls="${fixture_dir}/calls"
  mkdir -p "${fake_bin}" "${fake_state}"
  : >"${fake_calls}"
  cleanup_fixture() {
    # The EXIT/INT/TERM trap invokes this indirectly.
    # shellcheck disable=SC2317
    rm -rf "${fixture_dir}"
  }
  trap cleanup_fixture EXIT INT TERM

  cat >"${fake_bin}/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

state="${FAKE_DOCKER_STATE:?}"
calls="${FAKE_DOCKER_CALLS:?}"
mode="${FAKE_DOCKER_MODE:?}"

case "${1:-}" in
  container)
    [[ "${2:-}" == "inspect" ]]
    name="${3:-}"
    printf 'inspect %s\n' "${name}" >>"${calls}"
    if [[ "${mode}" == "preflight-daemon-failure" ]]; then
      echo "Cannot connect to the Docker daemon" >&2
      exit 1
    fi
    if [[ "${name}" == "nidar-sitl-vehicle-client" ]]; then
      echo "Error: No such container: ${name}" >&2
      exit 1
    fi
    if [[ ! -e "${state}/sim-preflight-complete" ]]; then
      : >"${state}/sim-preflight-complete"
      echo "Error: No such object: ${name}" >&2
      exit 1
    fi
    if [[ "${mode}" == "cleanup-daemon-failure" ]]; then
      echo "Cannot connect to the Docker daemon" >&2
      exit 1
    fi
    if [[ -e "${state}/sim-removed" ]]; then
      echo "Error response from daemon: No such container: ${name}" >&2
      exit 1
    fi
    exit 0
    ;;
  image)
    [[ "${2:-}" == "inspect" ]]
    exit 0
    ;;
  run)
    printf 'run %s\n' "$*" >>"${calls}"
    if [[ " $* " == *" --name nidar-sitl-vehicle-client "* ]]; then
      printf '%s\n' connection=connected component=companion-computer forwarding=off telemetry=ready
      exit 0
    fi
    sleep 30
    ;;
  rm)
    [[ "${2:-}" == "-f" ]]
    name="${3:-}"
    printf 'rm %s\n' "${name}" >>"${calls}"
    [[ "${name}" == "nidar-sitl-vehicle-px4" ]] && : >"${state}/sim-removed"
    exit 0
    ;;
esac

echo "unexpected fake docker invocation: $*" >&2
exit 99
SH
  chmod +x "${fake_bin}/docker"

  real_python3="$(command -v python3)"
  cat >"${fake_bin}/python3" <<SH
#!/usr/bin/env bash
set -euo pipefail

if [[ "\${1:-}" == "-" && "\${2:-}" == "14540" ]]; then
  cat >/dev/null
  exit 0
fi
if [[ "\${FAKE_SIGNAL_DURING_LAUNCH:-false}" == true &&
      "\${1:-}" == "${project_root}/scripts/bounded-log.py" ]] &&
   [[ ! -e "${fake_state}/signal-sent" ]]; then
  : >"${fake_state}/signal-sent"
  kill -TERM "\${PPID}"
fi
exec "${real_python3}" "\$@"
SH
  chmod +x "${fake_bin}/python3"

  run_fake_sitl() {
    local scenario="$1"
    local output_file="$2"
    set +e
    PATH="${fake_bin}:${PATH}" \
      FAKE_DOCKER_STATE="${fake_state}" \
      FAKE_DOCKER_CALLS="${fake_calls}" \
      FAKE_DOCKER_MODE="${scenario}" \
      NIDAR_CLIENT_BINARY="scripts/sitl-vehicle.sh" \
      NIDAR_SITL_TIMEOUT_SECONDS=2 \
      NIDAR_SITL_CLEANUP_TIMEOUT_SECONDS=3 \
      "${project_root}/scripts/sitl-vehicle.sh" >"${output_file}" 2>&1
    local status=$?
    set -e
    return "${status}"
  }

  if [[ "${mode}" == "--fake-docker-cleanup" ]]; then
    output_file="${fixture_dir}/absent.log"
    if ! run_fake_sitl confirmed-absent "${output_file}"; then
      cat "${output_file}" >&2
      echo "expected confirmed-absent fake Docker run to succeed" >&2
      exit 1
    fi
    if ! grep -Fx 'rm nidar-sitl-vehicle-px4' "${fake_calls}" >/dev/null ||
       ! grep -Fx 'Phase 3A vehicle SITL passed.' "${output_file}" >/dev/null; then
      cat "${output_file}" >&2
      echo "confirmed absent container was not cleaned up successfully" >&2
      exit 1
    fi

    rm -f "${fake_state}"/*
    : >"${fake_calls}"
    output_file="${fixture_dir}/daemon-failure.log"
    if run_fake_sitl cleanup-daemon-failure "${output_file}"; then
      cat "${output_file}" >&2
      echo "ambiguous cleanup inspect exit 1 incorrectly succeeded" >&2
      exit 1
    fi
    if grep -Fx 'rm nidar-sitl-vehicle-px4' "${fake_calls}" >/dev/null ||
       ! grep -F 'could not confirm nidar-sitl-vehicle-px4 is absent during cleanup' "${output_file}" >/dev/null ||
       grep -Fx 'Phase 3A vehicle SITL passed.' "${output_file}" >/dev/null; then
      cat "${output_file}" >&2
      echo "ambiguous cleanup inspect exit 1 was not fail-closed" >&2
      exit 1
    fi

    rm -f "${fake_state}"/*
    : >"${fake_calls}"
    output_file="${fixture_dir}/preflight-daemon-failure.log"
    if run_fake_sitl preflight-daemon-failure "${output_file}"; then
      cat "${output_file}" >&2
      echo "Docker-unavailable preflight incorrectly succeeded" >&2
      exit 1
    fi
    if ! grep -F 'failed to inspect existing container nidar-sitl-vehicle-px4; refusing to continue' "${output_file}" >/dev/null ||
       grep -F 'run ' "${fake_calls}" >/dev/null; then
      cat "${output_file}" >&2
      echo "Docker-unavailable preflight was not fail-closed" >&2
      exit 1
    fi
    exit 0
  fi

  output_file="${fixture_dir}/signal.log"
  set +e
  PATH="${fake_bin}:${PATH}" \
    FAKE_DOCKER_STATE="${fake_state}" \
    FAKE_DOCKER_CALLS="${fake_calls}" \
    FAKE_DOCKER_MODE=confirmed-absent \
    FAKE_SIGNAL_DURING_LAUNCH=true \
    NIDAR_CLIENT_BINARY="scripts/sitl-vehicle.sh" \
    NIDAR_SITL_TIMEOUT_SECONDS=2 \
    NIDAR_SITL_CLEANUP_TIMEOUT_SECONDS=3 \
    "${project_root}/scripts/sitl-vehicle.sh" >"${output_file}" 2>&1
  status=$?
  set -e
  if [[ ${status} -ne 143 ]] ||
     ! grep -Fx 'rm nidar-sitl-vehicle-px4' "${fake_calls}" >/dev/null; then
    cat "${output_file}" >&2
    echo "signal during simulator launch did not trigger registered cleanup" >&2
    exit 1
  fi
  exit 0
fi

ready_file="$(mktemp)"
holder_pid=""
cleanup() {
  if [[ -n "${holder_pid}" ]]; then
    kill "${holder_pid}" >/dev/null 2>&1 || true
    wait "${holder_pid}" 2>/dev/null || true
  fi
  rm -f "${ready_file}"
}
trap cleanup EXIT INT TERM

python3 - "${ready_file}" <<'PY' &
import pathlib
import socket
import sys
import time

ready = pathlib.Path(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 14540))
ready.write_text("ready", encoding="utf-8")
try:
    time.sleep(30)
finally:
    sock.close()
PY
holder_pid=$!

for _ in {1..50}; do
  [[ -s "${ready_file}" ]] && break
  sleep 0.02
done
if [[ ! -s "${ready_file}" ]]; then
  echo "failed to establish occupied-port fixture" >&2
  exit 1
fi

set +e
output="$(NIDAR_SITL_TIMEOUT_SECONDS=2 "${project_root}/scripts/sitl-vehicle.sh" 2>&1)"
status=$?
set -e

if [[ ${status} -eq 0 ]] ||
   [[ "${output}" != *"required UDP port is unavailable"* ]]; then
  printf 'expected occupied-port rejection; status=%s output=%s\n'     "${status}" "${output}" >&2
  exit 1
fi
