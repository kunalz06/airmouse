#!/usr/bin/env bash
# Passive GPS-denied PX4 SITL sensor fixture. Does not arm or issue flight commands.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${NIDAR_SIM_IMAGE:-nidar-px4-sim:v1.17.0-x500}"
container_name="nidar-sim-mtf01p-rplidar"
model_name="x500_mtf01p_rplidar"
mode="${1:---smoke}"
log_dir="${project_root}/simulation/output/sensors"
log_file="${log_dir}/px4-gazebo.log"
px4_root="/opt/PX4-Autopilot"
gz_models="${px4_root}/Tools/simulation/gz/models"
overlay="${project_root}/simulation/scripts/px4-rc.mavlink"
cleanup_done=false

cleanup() {
  if [[ "${cleanup_done}" == true ]]; then return; fi
  cleanup_done=true
  docker stop --time 5 "${container_name}" >/dev/null 2>&1 || true
  # Wait for docker run --rm to finish removing its ephemeral container.
  if [[ -n "${sim_pid:-}" ]]; then
    wait "${sim_pid}" >/dev/null 2>&1 || true
  fi
}
if [[ "${mode}" != "--smoke" && "${mode}" != "--run" ]]; then
  echo "usage: $0 [--smoke|--run]" >&2
  exit 2
fi
docker image inspect "${image}" >/dev/null 2>&1 || {
  echo "simulation image missing: ${image}" >&2; exit 2;
}
[[ -r "${overlay}" ]] || { echo "startup overlay missing" >&2; exit 2; }
for item in mtf_01p_flow x500_mtf01p_rplidar; do
  for file in model.sdf model.config; do
    [[ -r "${project_root}/simulation/models/${item}/${file}" ]] || {
      echo "missing model: ${item}/${file}" >&2; exit 2;
    }
  done
done
if docker container inspect "${container_name}" >/dev/null 2>&1; then
  echo "existing ${container_name} found; refusing to overwrite" >&2
  exit 2
fi
# Host networking uses the standard PX4/Gazebo ports. Never compete with an
# existing user/CI simulator or affect its lifecycle.
if docker ps --format '{{.Names}}' | grep -Eq '^(nidar-sitl|nidar-stock-flow-check|nidar-sim-)'; then
  echo "another NIDAR PX4/Gazebo simulator is already running" >&2
  exit 2
fi
# Use distinct names; never remove any other SITL job or persistent state.
mkdir -p "${log_dir}"
trap cleanup EXIT INT TERM
docker run --rm --name "${container_name}" --network host --init \
  -e HEADLESS=1 -e PX4_SYS_AUTOSTART=4021 \
  -e PX4_SIM_MODEL="gz_${model_name}" \
  -e GZ_SIM_RESOURCE_PATH="${gz_models}" \
  -v "${project_root}/simulation/models/mtf_01p_flow:${gz_models}/mtf_01p_flow:ro" \
  -v "${project_root}/simulation/models/x500_mtf01p_rplidar:${gz_models}/x500_mtf01p_rplidar:ro" \
  -v "${overlay}:${px4_root}/build/px4_sitl_default/etc/init.d-posix/px4-rc.mavlink:ro" \
  --entrypoint /bin/bash "${image}" -lc \
  'cd /opt/PX4-Autopilot/build/px4_sitl_default/src/modules/simulation/gz_bridge && exec /opt/PX4-Autopilot/build/px4_sitl_default/bin/px4' \
  >"${log_file}" 2>&1 &
sim_pid=$!
if [[ "${mode}" == "--run" ]]; then
  echo "Starting GPS-denied PX4 / Gazebo sensor model. Log: ${log_file}"
  wait "${sim_pid}"
  exit $?
fi
# Verify Gazebo sensor publications, not just presence of model XML.
model="/world/default/model/${model_name}_0"
flow="${model}/link/flow_link/sensor/optical_flow/optical_flow"
range="${model}/link/lidar_sensor_link/sensor/lidar/scan"
lidar="${model}/link/rplidar_link/sensor/rplidar_2d/scan"
ready=false
for _ in $(seq 1 100); do
  if ! kill -0 "${sim_pid}" 2>/dev/null; then
    echo "PX4 simulator process exited early" >&2
    tail -45 "${log_file}" >&2
    exit 1
  fi
  topics="$(docker exec "${container_name}" gz topic -l 2>/dev/null || true)"
  if [[ "${topics}" == *"${flow}"* && "${topics}" == *"${range}"* &&
        "${topics}" == *"${lidar}"* ]]; then
    ready=true
    break
  fi
  sleep 0.3
done
if [[ "${ready}" != true ]]; then
  echo "Gazebo sensor topic set not ready" >&2
  tail -45 "${log_file}" >&2
  exit 1
fi
# PX4 optical-flow messages use a custom protobuf type. Generic gz topic
# --echo may show no text even when flow data reaches PX4. Read PX4 uORB.
px4_bin="/opt/PX4-Autopilot/build/px4_sitl_default/bin"
for topic in sensor_optical_flow distance_sensor; do
  ready_sample=false
  sample=""
  if [[ "${topic}" == "sensor_optical_flow" ]]; then
    pattern="pixel_flow:|integration_timespan_us:"
  else
    pattern="current_distance:|orientation:"
  fi
  # A Gazebo topic can be advertised before the first valid PX4 uORB sample.
  # Bounded startup retries avoid false positives from topic existence alone.
  for _ in $(seq 1 45); do
    sample="$(docker exec "${container_name}" "${px4_bin}/px4-listener" "${topic}" 1 2>&1 || true)"
    if grep -Eq "${pattern}" <<<"${sample}"; then
      ready_sample=true
      break
    fi
    sleep 0.4
  done
  if [[ "${ready_sample}" != true ]]; then
    echo "PX4 uORB sensor missing or stale: ${topic}" >&2
    printf '%s\n' "${sample}" >&2
    exit 1
  fi
  echo "PX4 uORB ${topic} publication received"
done
# The RPLIDAR is Pi-side SLAM input and is *not* injected into PX4 EKF.
lidar_sample="$(docker exec "${container_name}" /bin/bash -lc \
  "timeout 8 gz topic -e -t '${lidar}' | head -n 120" 2>/dev/null || true)"
if ! grep -q 'angle_min:' <<<"${lidar_sample}"; then
  echo "no RPLIDAR scan messages published" >&2
  exit 1
fi
echo "RPLIDAR Gazebo LaserScan publication received"
if grep -Eqi 'Error Code 14.*Unable to find uri|Error Code 14' "${log_file}"; then
  echo "Gazebo model URI resolution error" >&2
  exit 1
fi
echo "GPS-denied MTF-01P-equivalent optical flow/range and RPLIDAR scan smoke passed"
