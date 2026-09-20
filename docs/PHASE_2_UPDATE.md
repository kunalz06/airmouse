# Phase 2 update — PX4 SITL / Gazebo

Phase 2 is complete locally with a pinned Ubuntu 24.04 PX4/Gazebo Harmonic
image, PX4 v1.17.0 X500 SITL, passive MAVLink verification, and secure local
GUI observation through QGroundControl.

## Delivered

- Pinned PX4 source commit and recursive submodule provenance.
- Reproducible `nidar-px4-sim:v1.17.0-x500` image with Gazebo Harmonic.
- Localhost-only observer telemetry: UDP 14550 for QGroundControl and UDP
  14560 for the passive smoke listener.
- Bounded headless launcher and receive-only `HEARTBEAT` plus
  `LOCAL_POSITION_NED` smoke test.
- X11 GUI launcher using a temporary private Xauthority cookie and read-only
  X11 mounts, without privileged mode, host IPC, or `xhost +`.
- A bounded CI image-build and headless-smoke job; it intentionally excludes
  GUI execution.

## Verification

Fresh local verification passed the unused-port smoke test, X500 headless
SITL smoke run, shell syntax checks, project configure/build/test suite, local
Gazebo GUI startup, and QGroundControl PX4 vehicle recognition. Evidence is
under `docs/test-results/phase-2-*`.

The disk report records the post-cleanup 374 GB free space and the explicit
Phase 2 BuildKit budget revision needed for the active PX4/Gazebo layers.

## Safety boundary

Phase 2 added no MAVSDK integration, vehicle commands, parameter changes,
arming, mission logic, or hardware flight behavior. PX4 remains the owner of
flight-critical safety and stabilization.
