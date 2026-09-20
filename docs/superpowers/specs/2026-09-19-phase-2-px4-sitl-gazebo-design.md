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
listens for MAVLink discovery and heartbeat/telemetry traffic only.

## Pinned simulation baseline

| Component | Selected value | Pin |
|---|---|---|
| Container base | Ubuntu 24.04 | immutable image digest already recorded in `config/versions.lock` |
| PX4 | v1.17.0 stable | annotated tag object `a5eb12d2ab591251faa009f76b2685b8cc64405d`; peeled source commit `d6f12ad1c4f70ad3230afd7d86e971421e02fef4` |
| Simulator | Gazebo Harmonic LTS | PX4-supported Ubuntu 24.04 simulation environment, package versions locked during implementation |
| Vehicle | PX4 Gazebo X500 | `gz_x500` target |

The Dockerfile must fetch only the listed PX4 source commit. PX4 submodules
must be initialized from that commit's gitlinks; no submodule may follow an
unpinned branch. Gazebo package and image provenance must be recorded in
`config/versions.lock`; no `latest` image or dependency tag is acceptable.

## Architecture

`docker/sim/Dockerfile` is the single supported Ubuntu 24.04 PX4 build and
runtime image. It installs PX4's documented development dependencies, checks
out the pinned PX4 source, initializes pinned submodules, and builds the
`px4_sitl_default` target. The X500 Gazebo run target is invoked only by the
bounded launch scripts. The image may contain only the prebuilt SITL artifacts
necessary to run X500, never mutable logs, host state,
test-result output, or unrelated build trees. Launch scripts never download
source, models, packages, or dependencies at runtime.

The repository exposes two explicit launch paths:

1. `scripts/sitl-headless.sh` runs the pinned/prebuilt X500 simulation with
   `HEADLESS=1` in a bounded container lifecycle. It invokes a passive
   MAVLink smoke-test helper, records logs outside image layers, then shuts
   PX4 down cleanly.
2. `scripts/sitl-gui.sh` runs the same X500 target with the Gazebo GUI. It
   validates `DISPLAY` and `/tmp/.X11-unix`, creates and passes a private
   Xauthority file, mounts the X11 socket read-only, and leaves QGroundControl running on
   the host. QGroundControl discovers the PX4 MAVLink UDP endpoint on the
   host network.

Both paths use the same pinned source, image, vehicle target, and networking
configuration. The GUI path is local-only; the headless path is the
automatable and CI-supported path.

The GUI path must not use `xhost +`, `--privileged`, or shared host IPC.
Host-mounted simulation state must be writable by the invoking host user.

## Interfaces and data flow

```text
PX4 SITL (container) <-> Gazebo Harmonic (container)
        |
        +-- MAVLink UDP --> host QGroundControl (GUI observation)
        |
        +-- MAVLink UDP --> passive smoke-test listener (heartbeat/telemetry)
```

Document MAVLink UDP endpoints and port ownership for each launch mode. The
GUI/QGroundControl and headless smoke-test paths must not compete for a host
UDP bind port; each script validates its port before startup and reports a
clear diagnostic if it is occupied. Phase 3 must be able to reuse this
documented topology without guessing it.

The smoke-test listener opens a dedicated receive-only MAVLink UDP socket and
does not send commands, parameter writes, mode changes, arming requests, or
setpoints. It passes only after receiving a valid PX4 `HEARTBEAT`, identifying
the system as a PX4 autopilot, and receiving one documented additional passive
telemetry message, all before a documented startup deadline. The telemetry
assertion must not require a request or command from the listener.

## Lifecycle and error handling

The scripts must reject a dirty or incorrect PX4 checkout, a missing or
incorrect simulation image, unavailable X11, an occupied container name, or
an unavailable MAVLink port. They use bounded deadlines, show relevant logs on
timeout, and use `--init` where compatible. Trap-based cleanup is idempotent:
it terminates then removes only the container started by the script. It never
deletes volumes, named caches, source, the simulation image, or recorded logs.
Verification confirms no Phase 2 container remains after normal or failed
startup.

PX4 logs and generated run data are written below a Git-ignored local
simulation state directory. The disk-report script remains the source of
truth for image and cache consumption. Any cleanup remains explicit and
non-destructive under the existing disk policy.

## Verification

The implementation must produce fresh evidence for:

- simulation image build using the pinned PX4 source and submodules;
- exact Gazebo/package provenance in `config/versions.lock`;
- headless X500 startup and passive MAVLink smoke-test success;
- documented smoke-test endpoint, PX4 heartbeat, and additional telemetry;
- clean script shutdown and no lingering simulation container;
- failed-start cleanup behavior;
- graphical X500 Gazebo launch on the native Linux X11 desktop;
- QGroundControl connection to the simulated vehicle;
- documented QGroundControl endpoint and narrowly scoped GUI access;
- disk report after the build and runs.

CI will build the image and run the headless smoke test. It will not attempt
the GUI or QGroundControl check because GitHub-hosted runners have no desktop
session. The CI smoke test uses bounded timeouts and fails rather than hangs
if PX4, Gazebo, or MAVLink readiness is absent. Exact commands, endpoints,
telemetry assertion, and exit status are documented for local verification.

## Required Phase 2 evidence files

Fresh evidence under `docs/test-results/` must include
`phase-2-sim-image-build.txt`, `phase-2-sitl-smoke.txt`,
`phase-2-gui-qgc.md`, and `phase-2-disk-report.txt`. The smoke evidence
records the pin, image identity, deadline, bind endpoint, PX4 discovery,
heartbeat and telemetry results, shutdown result, lingering-container check,
and final status. The GUI evidence records the Gazebo and QGroundControl
results, endpoint, Xauthority method, and absence of `xhost +` and privileged
container access.

## Phase 2 exit criteria

Phase 2 passes only with verified pinned source and submodules, a built image,
headless X500 and passive-smoke success, bounded startup/shutdown, successful
failed-start cleanup, no remaining simulation container, local GUI and
QGroundControl verification, documented port ownership, narrowly scoped GUI
access, disk-policy compliance, and fresh evidence. Do not start Phase 3 while
any criterion is unresolved.

## Non-goals and successor boundary

This phase deliberately leaves MAVSDK, `IVehicle`, NIDAR application-to-SITL
communication, vehicle commands, mission logic, fault injection, and
hardware testing to their specified later phases. Phase 3 may consume this
environment but must not change the Phase 2 passive-smoke-test safety rule
without a new approved design. Phase 3 must reuse the documented Phase 2
MAVLink topology instead of creating an undocumented competing endpoint.

## References

- PX4 v1.17 Gazebo Simulation Guide:
  <https://docs.px4.io/v1.17/en/sim_gazebo_gz/index>
- PX4 v1.17.0 source release:
  <https://github.com/PX4/PX4-Autopilot/tree/v1.17.0>
- PX4 SITL container guidance:
  <https://docs.px4.io/main/en/dev_setup/sitl_container_builds>
- PX4 Gazebo container GUI guidance:
  <https://docs.px4.io/main/en/simulation/gazebo_container_gui>
