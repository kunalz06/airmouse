#!/usr/bin/env bash
set -euo pipefail

docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev \
  ctest --test-dir build/dev --output-on-failure --timeout 10
