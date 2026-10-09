# NIDAR Production Drone Software

NIDAR is a safety-first companion-computer flight application for a CUAV X7+
running PX4. PX4 retains ownership of stabilization, low-level control, state
estimation, flight modes, arming checks, and failsafes. The Raspberry Pi 5
application provides mission orchestration and PX4-approved high-level
interfaces.

Completed foundations include the repository/toolchain and pinned PX4
SITL/Gazebo environment. Phase 3A implements the first production vehicle
boundary: a C++20 MAVSDK adapter for bounded PX4 discovery and fresh telemetry.
Active flight commands remain prohibited by Phase 3A policy and are not sent
to PX4.

GitHub is the source of truth. Development, tests, and SITL run on the Ubuntu
laptop. Phase 4A ARM64 packaging is implemented on a separate branch, with local
tests passing; final hosted CI and independent review remain mandatory before
Phase 4B Raspberry Pi deployment or Phase 4C real X7+ bench integration.

See [the master plan](docs/MASTER_PLAN.md), [phase ledger](docs/TASKS.md), and
[progress ledger](docs/PROGRESS.md).
