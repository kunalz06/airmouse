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

docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
  clang-format --dry-run --Werror "${cpp_files[@]}"

docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
  clang-tidy -p build/dev \
    --checks='-*,bugprone-*,performance-*,portability-*' \
    --warnings-as-errors='bugprone-*,performance-*,portability-*' \
    apps/nidar-flight/main.cpp \
    src/vehicle/mock_vehicle.cpp \
    src/vehicle/mavsdk_vehicle.cpp

docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
  shellcheck \
    scripts/sanitize.sh \
    scripts/lint.sh \
    scripts/sitl-vehicle.sh \
    scripts/build-runtime-arm64.sh \
    tests/integration/test_runtime_arm64_artifact.sh \
    tests/integration/test_runtime_arm64_execution.sh \
    tests/integration/test_runtime_image_policy.sh \
    tests/integration/test_mavsdk_dependency.sh \
    tests/integration/test_mavsdk_boundary.sh \
    tests/integration/test_nidar_flight_cli.sh \
    tests/sitl/test_vehicle_sitl.sh
