#!/usr/bin/env bash
set -euo pipefail

docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev \
  ctest --test-dir build/dev --output-on-failure --timeout 10

docker run --rm -v "$PWD:/workspace" -w /workspace nidar-dev \
  env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
    tests/unit/test_bounded_log.py -v
