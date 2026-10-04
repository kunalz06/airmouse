#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mode="${1:---normal}"

if [[ "${mode}" == "--normal" ]]; then
  exec "${project_root}/scripts/sitl-vehicle.sh"
fi

if [[ "${mode}" != "--occupied-port" ]]; then
  echo "usage: $0 [--normal|--occupied-port]" >&2
  exit 2
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
