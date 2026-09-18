# NIDAR Phase 1 Build Toolchain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create reproducible amd64 development and arm64 runtime packaging with one C++20 executable and GoogleTest unit test.

**Architecture:** Ubuntu 24.04 Docker images own all development tooling. The host retains only Docker and QGroundControl; a per-user launcher starts the verified AppImage. No PX4, MAVSDK, simulator, or flight logic is introduced.

**Tech Stack:** Ubuntu 24.04, GCC/Clang, CMake, Ninja, ccache, GoogleTest, yaml-cpp, spdlog, Docker Buildx, GitHub Actions.

**Spec:** `docs/MASTER_PLAN.md` Section 43 and approved Phase 1 design.

## Global Constraints

- C++20 only; development/PX4 tooling remains in Ubuntu 24.04 containers.
- Pin base-image digest and package versions in `config/versions.lock` before builds.
- Preserve Docker limits and never use broad volume deletion.
- Runtime target is linux/arm64 and excludes compilers/dev tooling.

### Task 1: Pin dependencies and create dev image

**Files:** `docker/dev/Dockerfile`, `config/versions.lock`, `.dockerignore`.

- [ ] Resolve official Ubuntu 24.04 image digest and apt package versions; record URL, digest/version, architecture, and verification date in `config/versions.lock`.
- [ ] Create `nidar-dev` with C++20 toolchain, CMake, Ninja, ccache, GDB, clang-format/tidy, sanitizers, GoogleTest, yaml-cpp, spdlog, Python, and ShellCheck.
- [ ] Build `--platform linux/amd64 -t nidar-dev` and record output.

### Task 2: Add executable, test, and developer scripts

**Files:** `apps/nidar-flight/main.cpp`, `tests/unit/nidar_flight_test.cpp`, `CMakeLists.txt`, `scripts/configure.sh`, `scripts/build.sh`, `scripts/test.sh`.

- [ ] Write a failing GoogleTest asserting the executable build target is registered.
- [ ] Add the minimal `nidar-flight` executable returning zero and CMake target/test registration.
- [ ] Make scripts run configure, build, CTest, clang-format check, and clang-tidy inside `nidar-dev`.
- [ ] Verify clean amd64 build and passing unit test.

### Task 3: Package runtime, CI, and GUI launcher

**Files:** `docker/runtime/Dockerfile`, `deployment/compose.pi.yaml`, `.github/workflows/build-test.yml`, `~/.local/share/applications/nidar-qgroundcontrol.desktop`.

- [ ] Create a multi-stage linux/arm64 runtime image with no compiler or development packages.
- [ ] Build/package the runtime for linux/arm64 without loading both architectures locally.
- [ ] Add CI for amd64 build/test/static analysis and arm64 runtime package build.
- [ ] Add a per-user desktop entry pointing to `/opt/qgroundcontrol/QGroundControl.AppImage`.

### Task 4: Verify and close Phase 1

- [ ] Run `scripts/docker-disk-report.sh`, inspect limits, and safely prune only temporary cache if needed.
- [ ] Save build/test/arm64 evidence under `docs/test-results`, update `docs/PROGRESS.md`, review the diff, and commit.

## Plan Self-Review

Tasks cover all Section 43 actions, retain Phase 2 scope boundaries, and provide specific verification for each exit criterion.
