#!/usr/bin/env bash
# Start the X500 Gazebo GUI with narrowly scoped local X11 access.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${NIDAR_SIM_IMAGE:-nidar-px4-sim:v1.17.0-x500}"
simulation_name="nidar-sitl-gui"
output_dir="${project_root}/simulation/output/phase-2"
simulation_log="${output_dir}/sitl-gui.log"
overlay="${project_root}/simulation/scripts/px4-rc.mavlink"
px4_root="/opt/PX4-Autopilot/build/px4_sitl_default"
authority_file=""
cleanup_started=false

cleanup() {
  if [[ "${cleanup_started}" == true ]]; then
    return
  fi
  cleanup_started=true
  docker rm -f "${simulation_name}" >/dev/null 2>&1 || true
  if [[ -n "${authority_file}" && -e "${authority_file}" ]]; then
    unlink "${authority_file}"
  fi
}
trap cleanup EXIT INT TERM

if [[ -z "${DISPLAY:-}" ]]; then
  echo "DISPLAY is required for the local Gazebo GUI" >&2
  exit 2
fi
if ! command -v xauth >/dev/null; then
  echo "xauth is required to create a private Xauthority file" >&2
  exit 2
fi
if [[ ! -d /tmp/.X11-unix ]]; then
  echo "/tmp/.X11-unix is unavailable" >&2
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
if docker container inspect "${simulation_name}" >/dev/null 2>&1; then
  echo "refusing to replace existing container: ${simulation_name}" >&2
  exit 2
fi

authority_file="$(mktemp "${TMPDIR:-/tmp}/nidar-xauthority.XXXXXX")"
xauth nlist "${DISPLAY}" | xauth -f "${authority_file}" nmerge -
if [[ ! -s "${authority_file}" ]]; then
  echo "could not create an Xauthority entry for DISPLAY=${DISPLAY}" >&2
  exit 2
fi

mkdir -p "${output_dir}"
: >"${simulation_log}"

echo "Starting Gazebo GUI. Start host QGroundControl separately; it receives PX4 telemetry on UDP 14550."
docker run --name "${simulation_name}" --network host --init \
  -e DISPLAY="${DISPLAY}" \
  -e XAUTHORITY=/tmp/.Xauthority \
  -e QT_X11_NO_MITSHM=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "${authority_file}:/tmp/.Xauthority:ro" \
  -v "${overlay}:${px4_root}/etc/init.d-posix/px4-rc.mavlink:ro" \
  "${image}" bash -lc 'cd /opt/PX4-Autopilot && make px4_sitl gz_x500' \
  >"${simulation_log}" 2>&1
