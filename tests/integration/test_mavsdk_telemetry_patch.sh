#!/usr/bin/env bash
# Validate the MAVSDK telemetry-only patch before slow ARM64 compilation.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_fixture="${root}/tests/fixtures/mavsdk-plugins-CMakeLists-v3.17.2.txt"
patch="${root}/docker/runtime/mavsdk-telemetry-only.patch"
expected_blob="5493e6038ad2ca2d87a2c842e423ce8115632595"

[[ "$(git hash-object "${source_fixture}")" == "${expected_blob}" ]] || {
  echo "pinned MAVSDK v3.17.2 upstream fixture changed" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/src/mavsdk/plugins"
cp "${source_fixture}" "${tmp}/src/mavsdk/plugins/CMakeLists.txt"
git -C "${tmp}" init -q
git -C "${tmp}" apply --check "${patch}"
git -C "${tmp}" apply "${patch}"

result="${tmp}/src/mavsdk/plugins/CMakeLists.txt"
! grep -q 'mavlink_passthrough' "${result}"
grep -Fqx 'foreach(plugin ${ENABLED_PLUGINS})' "${result}"
grep -Fqx '    add_subdirectory(${plugin})' "${result}"
grep -Fqx 'endforeach()' "${result}"
grep -Fqx 'set(UNIT_TEST_SOURCES ${UNIT_TEST_SOURCES} PARENT_SCOPE)' "${result}"
echo "pinned MAVSDK telemetry-only patch validation passed"
