#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

mapfile -d '' cpp_files < <(
  find apps include src tests/unit     -type f \( -name '*.cpp' -o -name '*.hpp' \) -print0
)

if (( ${#cpp_files[@]} > 0 )); then
  docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev     clang-format --dry-run --Werror "${cpp_files[@]}"
fi

docker run --rm -v "${project_root}:/workspace:ro" -w /workspace nidar-dev   shellcheck     scripts/*.sh     tests/integration/*.sh     tests/sitl/*.sh
