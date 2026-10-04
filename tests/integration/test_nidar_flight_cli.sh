#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

run_app() {
  docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev     build/dev/nidar-flight "$@"
}

run_app --help | grep -F -- "--sim" >/dev/null

set +e
output="$(run_app --sim --endpoint not-a-url --discovery-timeout-ms 10 2>&1)"
status=$?
set -e
if [[ ${status} -eq 0 ]]; then
  echo "malformed endpoint unexpectedly succeeded" >&2
  exit 1
fi
if [[ "${output}" != *"Usage: nidar-flight"* ]]; then
  echo "malformed endpoint did not produce stable usage output" >&2
  exit 1
fi

set +e
run_app --sim --endpoint udpin://127.0.0.1:14540 --discovery-timeout-ms 0 >/dev/null 2>&1
status=$?
set -e
if [[ ${status} -eq 0 ]]; then
  echo "zero discovery timeout unexpectedly succeeded" >&2
  exit 1
fi
