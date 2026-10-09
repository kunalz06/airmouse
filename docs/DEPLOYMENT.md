# Deployment — Phase 4B handoff (no hardware deployment performed)

Phase 4A produces a **telemetry-only** `linux/arm64` Docker image for Raspberry Pi 5, using Ubuntu 24.04 runtime and MAVSDK v3.17.2 from the pinned source commit. The runtime has no Gazebo, PX4 development toolchain, compilers, IDE, CI tools, or project source tree.

## Phase 4B inputs and authorization

Phase 4B must be separately planned and authorized after Phase 4A has a green final-commit CI run and independent review. Consume the **verified image by its immutable OCI manifest digest**, not merely the mutable `phase-4a-local` tag. Verify its platform (`linux/arm64`), source revision, MAVSDK commit, OS base, size policy and runtime library closure against the published CI manifest. Archive/registry digest identity and transport must be recorded explicitly; a local Docker image ID must **not be assumed** to identify the OCI manifest (Docker storage backends vary).

Phase 4A deliberately does **not** publish a deployable runtime image to a registry or release: repository credentials and a release-publication policy have not been authorized. The CI artifact is verification evidence, not a deployment channel. A future authorized release must publish an OCI artifact to an approved immutable registry/release location, record the manifest digest and archive checksum, and make Phase 4B consume exactly that identity.

Provision the Raspberry Pi 5 as a runtime host. Do not compile the project or install the simulation/toolchain on the Pi. Use a validated hardware configuration and provide one serial device path and baud rate explicitly after actual device discovery; `config/hardware.yaml` intentionally keeps them `null`. Do not guess `/dev/ttyAMA0` or a TELEM baud value based on earlier devices.

Run with a numeric non-root user and only the minimum required device access. Do not use `--privileged`; any device mapping belongs to Phase 4C and must be verified on the bench first. Keep structured application logs and PX4/flight evidence on persistent host storage outside the container, with bounded retention that never silently deletes unarchived evidence.

Phase 4B verifies image transfer, architecture, startup, deterministic failure without PX4, service lifecycle and persistent logs **without the flight controller connected**. Phase 4C covers separately authorized read-only Raspberry Pi ↔ CUAV X7+ MAVLink/serial telemetry with propulsion rendered safe and failsafes independently checked.

**Safety boundary:** This Phase 4A image contains no enabled arming, disarming, takeoff, land, Hold, Offboard, position, velocity, mission or parameter command plugins. These remain locally rejected by `RejectedByPhasePolicy`. Phase 3B is a separate unmerged and unapproved track.
