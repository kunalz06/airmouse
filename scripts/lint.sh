#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

cpp_files=(
  apps/nidar-flight/main.cpp
  include/nidar/vehicle/vehicle_types.hpp
  include/nidar/vehicle/ivehicle.hpp
  include/nidar/vehicle/mock_vehicle.hpp
  include/nidar/vehicle/mavsdk_vehicle.hpp
  src/vehicle/mock_vehicle.cpp
  src/vehicle/mavsdk_vehicle.cpp
  tests/unit/vehicle_types_test.cpp
  tests/unit/mock_vehicle_test.cpp
  tests/unit/mavsdk_vehicle_test.cpp
)

format_failed=0
for file in "${cpp_files[@]}"; do
  if ! docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
      clang-format --dry-run --Werror "${file}"; then
    printf 'NIDAR_FORMAT_BEGIN:%s\n' "${file}"
    docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
      clang-format "${file}" | base64 -w0
    printf '\n'
    printf 'NIDAR_FORMAT_END:%s\n' "${file}"
    format_failed=1
  fi
done

if (( format_failed != 0 )); then
  exit 1
fi

docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
  clang-tidy -p build/dev \
    --checks='-*,bugprone-*,performance-*,portability-*' \
    --warnings-as-errors='bugprone-*,performance-*,portability-*' \
    apps/nidar-flight/main.cpp \
    src/vehicle/mock_vehicle.cpp \
    src/vehicle/mavsdk_vehicle.cpp
