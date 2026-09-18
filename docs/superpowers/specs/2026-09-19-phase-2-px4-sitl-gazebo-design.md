# Phase 2 PX4 SITL / Gazebo Design

## Purpose

Establish a reproducible, containerized PX4 software-in-the-loop (SITL)
environment for the standard X500 quadrotor. The environment must let a host
installation of QGroundControl observe the simulated vehicle, while an
automated headless smoke test verifies non-commanding MAVLink discovery and
telemetry.

## Scope and safety boundary

This phase creates simulation infrastructure only. It does not add MAVSDK to
NIDAR, arm the simulated vehicle, issue flight commands, change PX4 safety
parameters, or perform hardware or powered-flight testing.

PX4 continues to own its existing flight-control, state-estimation, arming,
flight-mode, and failsafe behavior. The Phase 2 smoke test is passive: it
listens for MAVLink discovery and heartbeat traffic only.

## Pinned simulation baseline

| Component | Selected value | Pin |
|---|---|---|
| Container base | Ubuntu 24.04 | immutable image digest already recorded in `config/versions.lock` |
| PX4 | v1.17.0 stable | annotated tag object `a5eb12d2ab591251faa009f76b2685b8cc64405d`; peeled source commit `d6f12ad1c4f70ad3230afd7d86e971421e02fef4` |
| Simulator | Gazebo Harmonic LTS | PX4-supported Ubuntu 24.04 simulation environment, package versions locked during implementation |
| Vehicle | PX4 Gazebo X500 | `gz_x500` target |

The Dockerfile must fetch only the listed PX4 source commit. The selected
Gazebo and all image/package provenance must be recorded in
`config/versions.lock`; no `latest` image or dependency tag is acceptable.

## Architecture

`docker/sim/Dockerfile` is the single supported Ubuntu 24.04 PX4 build and
runtime image. It installs PX4's documented development dependencies, checks
out the pinned PX4 source, and builds the `px4_sitl_default`/Gazebo X500
target. The image does not embed mutable PX4 logs, generated build output,
or host simulation state.

The repository exposes two explicit launch paths:

1. `scripts/sitl-headless.sh` runs `HEADLESS=1 make px4_sitl gz_x500` in a
   bounded container lifecycle. It invokes a passive MAVLink smoke-test
   helper, records logs outside image layers, then shuts PX4 down cleanly.
2. `scripts/sitl-gui.sh` runs the same X500 target with the Gazebo GUI. It
   validates `DISPLAY` and `/tmp/.X11-unix`, passes a private Xauthority file
   and the X11 socket to the container, and leaves QGroundControl running on
   the host. QGroundControl discovers the PX4 MAVLink UDP endpoint on the
   host network.

Both paths use the same pinned source, image, vehicle target, and networking
configuration. The GUI path is local-only; the headless path is the
automatable and CI-supported path.

## Interfaces and data flow

```text
PX4 SITL (container) <-> Gazebo Harmonic (container)
        |
        +-- MAVLink UDP --> host QGroundControl (GUI observation)
        |
        +-- MAVLink UDP --> passive smoke-test listener (heartbeat/telemetry)
```

The smoke-test listener opens a dedicated receive-only MAVLink UDP socket and
does not send commands, parameter writes, mode changes, arming requests, or
setpoints. It passes only after discovering a PX4 system and receiving the
required heartbeat/telemetry before a documented deadline.

## Lifecycle and error handling

The scripts must reject a dirty or incorrect PX4 checkout, a missing image,
an unavailable X11 display for GUI mode, and an already occupied simulation
container name. They must use a bounded startup deadline and report the
container logs on timeout. Trap-based cleanup sends a termination signal,
waits a bounded interval, then removes only the container started by that
script. It must not delete Docker volumes, named caches, source checkouts, or
recorded simulation logs.

PX4 logs and generated run data are written below a Git-ignored local
simulation state directory. The disk-report script remains the source of
truth for image and cache consumption. Any cleanup remains explicit and
non-destructive under the existing disk policy.

## Verification

The implementation must produce fresh evidence for:

- sim image build using the pinned PX4 commit;
- headless X500 startup and passive MAVLink smoke-test success;
- clean script shutdown and no lingering simulation container;
- graphical X500 Gazebo launch on the native Linux X11 desktop;
- QGroundControl connection to the simulated vehicle;
- disk report after the build and runs.

CI will build the image and run the headless smoke test. It will not attempt
the GUI or QGroundControl check because GitHub-hosted runners have no desktop
session. Exact commands and observed endpoints are documented for repeatable
local verification.

## Non-goals and successor boundary

This phase deliberately leaves MAVSDK, `IVehicle`, NIDAR application-to-SITL
communication, vehicle commands, mission logic, fault injection, and
hardware testing to their specified later phases. Phase 3 may consume this
environment but must not change the Phase 2 passive-smoke-test safety rule
without a new approved design.

## References

- PX4 v1.17 Gazebo Simulation Guide:
  <https://docs.px4.io/v1.17/en/sim_gazebo_gz/index>
- PX4 v1.17.0 source release:
  <https://github.com/PX4/PX4-Autopilot/tree/v1.17.0>
- PX4 SITL container guidance:
  <https://docs.px4.io/main/en/dev_setup/sitl_container_builds>
- PX4 Gazebo container GUI guidance:
  <https://docs.px4.io/main/en/simulation/gazebo_container_gui>
