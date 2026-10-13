#!/usr/bin/env bash
set -euo pipefail

image_ref=${1:-}
if [[ -z "${image_ref}" ]]; then
  echo "usage: $0 IMAGE_REF" >&2
  exit 2
fi

help_output=$(docker run --rm --platform linux/arm64 "${image_ref}" --help)
grep -Fq -- '--sim' <<<"${help_output}"
grep -Fq -- '--endpoint' <<<"${help_output}"
if grep -Eqi '(arm|disarm|takeoff|land|offboard|mission upload)' <<<"${help_output}"; then
  echo "active vehicle command path is exposed by the runtime CLI" >&2
  exit 1
fi

set +e
no_px4_output=$(timeout 10 docker run --rm --platform linux/arm64 "${image_ref}" \
  --sim --endpoint udpin://127.0.0.1:14540 --discovery-timeout-ms 250 2>&1)
status=$?
set -e

if [[ ${status} -eq 124 ]]; then
  echo "no-PX4 runtime check exceeded its bounded timeout" >&2
  exit 1
fi
if [[ ${status} -ne 3 ]]; then
  printf '%s\n' "${no_px4_output}" >&2
  echo "no-PX4 runtime check returned ${status}, expected connection failure 3" >&2
  exit 1
fi
grep -Fq 'connection=discovery-timeout' <<<"${no_px4_output}"

runtime_user=$(docker image inspect --format '{{.Config.User}}' "${image_ref}")
[[ -n "${runtime_user}" && "${runtime_user}" != "root" && "${runtime_user}" != "0" ]]

echo "runtime ARM64 execution checks passed: ${image_ref}"
