#!/usr/bin/env bash
set -euo pipefail
docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev \
  cmake --build build/dev --parallel
