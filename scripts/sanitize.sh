#!/usr/bin/env bash
set -euo pipefail

docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev   cmake --preset sanitizers

docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev   cmake --build build/test --parallel

docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev   ctest --test-dir build/test --output-on-failure
