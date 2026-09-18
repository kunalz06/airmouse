#!/usr/bin/env bash
set -euo pipefail
docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev \
  cmake --preset dev -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
