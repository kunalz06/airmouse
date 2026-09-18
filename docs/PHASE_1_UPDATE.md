# Phase 1 Update — Build and Toolchain

**Status:** Complete. Phase 2 has not started.

## Completed

- Created the pinned Ubuntu 24.04 `nidar-dev` image with GCC 13.3, CMake 3.28, Ninja, ccache, GDB, clang-format, clang-tidy, sanitizers, GoogleTest, yaml-cpp, spdlog, Python, and ShellCheck.
- Added the minimal C++20 `nidar-flight` executable and its first GoogleTest unit test.
- Added containerized `configure.sh`, `build.sh`, and `test.sh` scripts.
- Enabled CMake compilation-database export and verified clang-tidy against the executable source.
- Added a multi-stage linux/arm64 runtime image; built and exported `/tmp/nidar-runtime-arm64.tar` using Buildx/QEMU.
- Added the GitHub amd64 build/test and arm64 runtime-package workflow.
- Configured ARM64 QEMU emulation through Buildx binfmt registration.
- Added the per-user QGroundControl GUI launcher at `~/.local/share/applications/qgroundcontrol.desktop`.

## Verification Evidence

- Build, unit-test, static-analysis, and arm64-package verification: `docs/test-results/phase-1-build-test.txt`
- Docker capacity report: `docs/test-results/phase-1-disk-report.txt`
- Implementation plan: `docs/superpowers/plans/2026-09-19-phase-1-build-toolchain.md`
- Completion commit: `af0444a` (`build: establish Phase 1 toolchain`)

## Exit Criteria

| Criterion | Result |
|---|---|
| Clean amd64 build | PASS |
| Unit test passes | PASS |
| Static analysis works | PASS |
| ARM64 runtime package builds | PASS |
| CI workflow exists | PASS |
| Disk limits respected | PASS |

## Deferred to Phase 2

PX4 source selection and pinning, PX4 SITL, Gazebo, QGroundControl vehicle connection, simulation startup/shutdown, and SITL smoke testing are not part of Phase 1.
