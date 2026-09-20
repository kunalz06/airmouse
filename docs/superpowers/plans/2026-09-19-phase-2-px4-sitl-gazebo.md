# Phase 2 PX4 SITL / Gazebo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pinned, passive, containerized PX4 v1.17.0 X500 SITL environment with headless smoke testing and local X11/QGroundControl observation.

**Architecture:** A single Ubuntu 24.04 sim image builds PX4 and Gazebo Harmonic once. Shell launchers run it with host networking and bounded cleanup; a Python listener passively validates `HEARTBEAT` and `LOCAL_POSITION_NED` on a dedicated UDP port.

**Tech Stack:** Docker, Ubuntu 24.04, PX4 v1.17.0, Gazebo Harmonic, Bash, Python 3, pymavlink.

**Spec:** `docs/superpowers/specs/2026-09-19-phase-2-px4-sitl-gazebo-design.md`

## Global Constraints

- Pin PX4 to `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`; initialize only its recorded submodule gitlinks.
- Use X500 `gz_x500`; never arm, command, request telemetry, or alter parameters.
- Do not use `latest`, `xhost +`, `--privileged`, or host IPC.
- Use distinct documented host UDP ports for QGroundControl and smoke testing.
- All lifecycle deadlines are bounded; cleanup never deletes persistent data.

---

### Task 1: Pin and build the simulation image

**Files:** Create `docker/sim/Dockerfile`; modify `config/versions.lock`, `.dockerignore`.

- [x] Add pinned PX4/Gazebo provenance and a reproducible Dockerfile that checks out the commit, runs `git submodule update --init --recursive`, installs PX4's Ubuntu 24.04 prerequisites, and prebuilds `make px4_sitl_default`; launch scripts alone invoke `make px4_sitl gz_x500`.
- [x] Build `nidar-px4-sim:v1.17.0-x500`, capture `docker image inspect` and package versions in `docs/test-results/phase-2-sim-image-build.txt`.
- [x] Verify the source commit and submodule status in the image; verify mutable logs/state are not image inputs.
- [x] Commit the image definition and lock changes.

### Task 2: Add passive smoke test and lifecycle launcher

**Files:** Create `scripts/sitl-smoke.py`, `scripts/sitl-headless.sh`, `tests/sitl/test_sitl_smoke.sh`.

**Interfaces:** `sitl-smoke.py --port 14560 --timeout 90` exits zero only after PX4 `HEARTBEAT` and `LOCAL_POSITION_NED`; it sends no MAVLink frames. `sitl-headless.sh` starts `nidar-px4-sim:v1.17.0-x500` with `--init`, exposes only UDP 14560 for the listener, and performs idempotent cleanup.

- [x] Write a shell test that asserts smoke failure on an unused UDP port.
- [x] Implement the receive-only listener with explicit heartbeat autopilot validation and `LOCAL_POSITION_NED` assertion.
- [x] Implement the bounded launcher with port/container-name checks, log capture in `simulation/output/`, signal traps, timeout diagnostics, and lingering-container verification.
- [x] Run the failure test and the headless X500 smoke test; record endpoint, deadline, image identity, discovery, telemetry, shutdown, and final status in `docs/test-results/phase-2-sitl-smoke.txt`.
- [x] Commit the launcher, listener, and tests.

### Task 3: Add secure local GUI and QGroundControl procedure

**Files:** Create `scripts/sitl-gui.sh`, `docs/SIMULATION.md`.

- [x] Implement a GUI launcher that validates X11, creates a temporary private Xauthority file, mounts `/tmp/.X11-unix` read-only, uses host networking, and cleans only its temporary authority file/container.
- [x] Document `14550` as PX4-to-host QGroundControl telemetry and `14560` as headless smoke listener telemetry; document port ownership and launch commands.
- [x] Run the GUI locally, observe X500 in Gazebo and QGroundControl, then record results, endpoint, Xauthority method, and no-privileged/no-`xhost +` confirmation in `docs/test-results/phase-2-gui-qgc.md`.
- [x] Commit GUI script and simulation documentation.

### Task 4: CI, evidence, and phase closeout

**Files:** Modify `.github/workflows/build-test.yml`, `docs/REFERENCES.md`, `docs/PROGRESS.md`, `docs/TASKS.md`; create `docs/test-results/phase-2-disk-report.txt`, `docs/PHASE_2_UPDATE.md`.

- [x] Add a bounded CI simulation-image build and headless smoke job; no GUI job.
- [x] Add official PX4 references, run `scripts/docker-disk-report.sh`, and retain evidence.
- [x] Verify all Phase 2 exit gates, update the ledgers and Phase 2 update, then commit the completion record.
