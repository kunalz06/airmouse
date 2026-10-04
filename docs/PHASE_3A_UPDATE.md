# Phase 3A update — vehicle telemetry layer

Phase 3A establishes NIDAR's first production vehicle boundary while keeping
active flight commands disabled.

## Delivered

- MAVSDK C++ v3.17.2 pinned and checksum-verified in the Ubuntu 24.04 amd64
  development image.
- MAVSDK-free `IVehicle` contracts and deterministic `MockVehicle`.
- `MavsdkVehicle` as the sole MAVSDK implementation.
- Explicit `CompanionComputer` identity and MAVSDK forwarding disabled.
- Connected-PX4-only discovery with typed transport, discovery-timeout, and
  cancellation results.
- Independent armed, flight-mode, and battery timestamps/validity using
  `steady_clock`.
- Disconnect invalidation, callback-generation protection, explicit
  reconnect, and repeated endpoint-release coverage.
- Bounded `nidar-flight --sim` telemetry mode.
- Source-boundary enforcement that prevents MAVSDK leakage and active-command
  plugins outside the approved adapter boundary.
- Normal and sanitizer-instrumented PX4 v1.17 X500 SITL verification.
- Bounded unit-test and CI deadlines.

## Verification

Fresh GitHub Actions run #76 on implementation commit
`6a4c1107af32db1298b9d4b3529825221020f3d6` passed:

- 18/18 normal tests;
- dependency, boundary, and CLI integration checks;
- clang-format, clang-tidy, and ShellCheck;
- 18/18 ASan/UBSan tests;
- PX4/Gazebo image build and existing Phase 2 SITL gates;
- occupied UDP 14540 negative test;
- normal Phase 3A X500 vehicle telemetry;
- sanitizer-instrumented Phase 3A X500 vehicle telemetry;
- Docker disk reports.

Both live vehicle runs discovered PX4 system ID 1 through MAVSDK v3.17.2,
reported `CompanionComputer`, forwarding off, fresh armed/mode/battery
telemetry, and completed launcher cleanup.

Detailed evidence is under `docs/test-results/phase-3a-*`.

## Safety boundary

Phase 3A does not instantiate MAVSDK Action, Offboard, Mission, MissionRaw, or
Param command plugins. Arm, disarm, takeoff, land, hold, Offboard start/stop,
position targets, and velocity targets remain locally rejected with
`RejectedByPhasePolicy`.

PX4 continues to own stabilization, state estimation, arming checks, flight
modes, and failsafes.

## Review

The final technical review records no unresolved Critical or Important
finding. The review is auditable in PR #1 and
`docs/test-results/phase-3a-independent-review.md`; it is not represented as
a second-human safety signoff.

## Next boundary

Phase 3B active vehicle commands remain **not started** and require their own
approved design, tests, and safety review.

The next hardware-oriented work may proceed as Phase 4 read-only Raspberry Pi
deployment: verified linux/arm64 MAVSDK/runtime packaging, deployment
automation, Pi-to-CUAV X7+ transport bring-up, and telemetry-only bench
verification with propulsion made safe. Phase 4 must not silently enable
Phase 3B command paths.
