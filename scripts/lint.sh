#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

if ! docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
    clang-format --dry-run --Werror include/nidar/vehicle/mock_vehicle.hpp; then
  echo "NIDAR_FORMAT_BEGIN:include/nidar/vehicle/mock_vehicle.hpp"
  docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev \
    clang-format include/nidar/vehicle/mock_vehicle.hpp | base64 -w0
  echo
  echo "NIDAR_FORMAT_END:include/nidar/vehicle/mock_vehicle.hpp"
  exit 1
fi
