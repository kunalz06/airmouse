# Deployment — Phase 4B handoff (no hardware deployment performed)

Phase 4A produces a **telemetry-only** `linux/arm64` Docker image for Raspberry Pi 5, using Ubuntu 24.04 runtime and MAVSDK v3.17.2 from the pinned source commit. The runtime has no Gazebo, PX4 development toolchain, compilers, IDE, CI tools, or project source tree.

## Phase 4B inputs and authorization

Phase 4B must be separately planned and authorized after Phase 4A has a green final-commit CI run and independent review. Consume the **verified image by its immutable OCI manifest digest**, not merely the mutable `phase-4a-local` tag. Verify its platform (`linux/arm64`), source revision, MAVSDK commit, OS base, size policy and runtime library closure against the published CI manifest. Archive/registry digest identity and transport must be recorded explicitly; a local Docker image ID must **not be assumed** to identify the OCI manifest (Docker storage backends vary).

Phase 4A deliberately does **not** publish a deployable runtime image to a registry or release: repository credentials and a release-publication policy have not been authorized. The CI artifact is verification evidence, not a deployment channel. A future authorized release must publish an OCI artifact to an approved immutable registry/release location, record the manifest digest and archive checksum, and make Phase 4B consume exactly that identity.

Provision the Raspberry Pi 5 as a runtime host. Do not compile the project or install the simulation/toolchain on the Pi. Use a validated hardware configuration and provide one serial device path and baud rate explicitly after actual device discovery; `config/hardware.yaml` intentionally keeps them `null`. Do not guess `/dev/ttyAMA0` or a TELEM baud value based on earlier devices.

Run with a numeric non-root user and only the minimum required device access. Do not use `--privileged`; any device mapping belongs to Phase 4C and must be verified on the bench first. Keep structured application logs and PX4/flight evidence on persistent host storage outside the container, with bounded retention that never silently deletes unarchived evidence.

Phase 4B verifies image transfer, architecture, startup, deterministic failure without PX4, service lifecycle and persistent logs **without the flight controller connected**. Phase 4C covers separately authorized read-only Raspberry Pi ↔ CUAV X7+ MAVLink/serial telemetry with propulsion rendered safe and failsafes independently checked.

**Safety boundary:** This Phase 4A image contains no enabled arming, disarming, takeoff, land, Hold, Offboard, position, velocity, mission or parameter command plugins. These remain locally rejected by `RejectedByPhasePolicy`. Phase 3B is a separate unmerged and unapproved track.

## APT reproducibility evidence and CI identity required at release consumption

Only `docker/runtime/Dockerfile` uses the signed Ubuntu snapshot pinned in
`config/versions.lock` (`20261001T000000Z`, Noble plus updates, security and
backports). Every source entry is `signed-by` Ubuntu's archive keyring, and
APT uses strict update errors. TLS bootstrap is an in-repository SHA-256-pinned
trust bundle with provenance in `docker/apt/README.md`; no TLS peer or APT
signature verification is disabled. `docker/dev/Dockerfile` and
`docker/sim/Dockerfile` are unchanged by this runtime APT work.

The committed `config/apt-closure.lock.json` and
`config/apt-closure/{mavsdk-build,app-build,runtime}-packages.tsv` are the
full byte-sorted installed package/version/architecture closure for the three
ARM64 runtime stages. CI fails before building if either the snapshot policy or
any closure hash is changed. CI evidence contains a second copy of those
inventories and a summary tied to the committed lock SHA-256. Validate both the
manifest and lock checksums before any future release. Do not use the explicit
bootstrap regeneration path as a routine build mode.

Verify the distinct GitHub PR head SHA and checked-out merge SHA, CI run ID/attempt, source-commit timestamp and wall-clock UTC build time along with the immutable OCI manifest digest. Continue to prohibit Pi deployment without a separately authorized digest-qualified artifact transport.

The first generated closure contains 197 MAVSDK-build, 170 application-build,
and 94 runtime packages. Its authorized-host bootstrap succeeded; the locked
replay is still running. This is not hosted-CI evidence and does not authorize
hardware deployment, publication, or Phase 4A completion. Final hosted CI and
an independent review remain required.
