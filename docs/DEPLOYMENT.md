# Deployment — Phase 4B handoff (no hardware deployment performed)

Phase 4A produces a **telemetry-only** `linux/arm64` Docker image for Raspberry Pi 5, using Ubuntu 24.04 runtime and MAVSDK v3.17.2 from the pinned source commit. The runtime has no Gazebo, PX4 development toolchain, compilers, IDE, CI tools, or project source tree.

## Phase 4B verified runtime release procedure

Phase 4B Tasks 01/02 are authorized only through the manual
`release-runtime-arm64` GitHub Actions workflow on `main`. It requires a
successful exact-SHA AMD64, SITL, and ARM64 runtime `build-test` run, then
builds one locked ARM64 candidate, verifies it before publication, transfers
its OCI archive with digest preservation, and verifies a digest-pulled image.
Consume a **VERIFIED** image only by its immutable OCI manifest digest, never
by a mutable tag or local Docker image ID. A failed preflight is **BLOCKED**;
a failed post-push check is **UNVERIFIED** and is not deployable.

The workflow first uploads a provisional BLOCKED/UNVERIFIED diagnostic
GitHub Actions artifact, then uploads the final release evidence artifact.
Only a successful final upload and successful workflow run allow the job
summary to expose a
VERIFIED record and canonical pull reference. The final artifact has 90-day
retention and contains the source SHA, run/attempt, image identities, archive
checksum, APT closure result, package verification and status. A consumer
must verify the matching completed-successful workflow run and artifact
identity; a standalone JSON file marked VERIFIED is insufficient. A separate
authorized documentation update may retain an actual release identity. No
digest has been issued here.

The repository `kunalz06/airmouse` is **private**, confirmed through
authenticated GitHub repository access on October 13, 2026. GHCR package
existence, visibility, ownership, association and workflow write access have
not been verified locally. GitHub documents that a new container package is
[private by default](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
and that publication with `GITHUB_TOKEN` links the workflow repository;
[package access rules](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)
separate repository access inheritance from package visibility. The image
must carry `org.opencontainers.image.source=https://github.com/kunalz06/airmouse`.
These defaults support a private first publication, but do not prove that this
package namespace is absent or writable with the actual workflow token.

The workflow therefore requires an authenticated HTTP 200 package response
with exact `nidar-runtime` container identity, `kunalz06` ownership, private
visibility and association to the private `kunalz06/airmouse` repository before
any write. A 404 may mean absent or hidden/unauthorized and remains BLOCKED;
401/403, rate limits, malformed payloads and network failures also BLOCK.
An owner must separately establish and verify a private, repository-linked
package with authorized Actions access before using this workflow. The
distinct `bootstrap-private-ghcr` workflow is prepared for a separately
approved one-time bootstrap after the owner checks the GitHub package settings
and confirms that `nidar-runtime` is absent or inaccessible. It runs manually
on main only, requires the exact `BOOTSTRAP_PRIVATE_NIDAR_RUNTIME` input, and
uses only `contents: read` and `packages: write`. Its unique
`bootstrap-sentinel-<run>-<attempt>-<source-sha>` tag contains a zero-layer
`scratch` image with repository source, revision and sentinel-kind labels; it
is never a runtime `sha-` tag. The owner must verify absence independently and
establish a private, repository-linked package with Actions access manually.
The workflow requires positive HTTP 200 private package metadata before
publication. A 404 remains ambiguous even with a confirmation input and
blocks the workflow before any registry write. After publication it verifies
the remote tag and digest-qualified image have the same manifest digest and
the expected source and sentinel-kind labels before recording package readiness. The
only uploaded bootstrap artifact is sanitized status metadata; raw API
responses and credentials remain temporary. A failed post-publication check
leaves the sentinel UNVERIFIED and the runtime release BLOCKED. Owner settings
must then establish package Actions access; the standard read-only package
preflight must return valid HTTP 200 metadata before any runtime release.
Preparing this workflow does not authorize dispatch, visibility changes,
sentinel deletion, or a runtime publication. Runtime permission denial before
upload is BLOCKED.

The typed v2 release record requires Boolean-true telemetry patch, source
command boundary, ARM64 artifact/execution/policy, APT closure, runtime
manifest/provenance, remote OCI identity, digest-pulled image tests, and
private-visibility checks. Missing, null, false, or string results cannot
authorize VERIFIED. A retry must prove the original successful workflow run
and attempt, retained artifact digest and source identity, original all-true
evidence, and current-run digest-pull tests; it never rebuilds or moves the
existing SHA tag. Absent or ambiguous retained evidence blocks retries.

BLOCKED records have no approved registry write; UNVERIFIED records indicate
a possible/interrupted upload. A failed final evidence upload leaves only the
provisional diagnostic artifact as trusted evidence and cannot authorize the
release. Signed artifact URLs and API/registry credentials remain in
temporary restricted files and are excluded from uploaded evidence. The
same-SHA Actions concurrency group and immediate pre-push tag check reduce
races but GHCR does not provide an atomic conditional tag write here. If a tag
appears or publication stops after a possible write, preserve it, mark the
release BLOCKED/UNVERIFIED, inspect the remote digest and original run/artifact
evidence, and obtain an owner-reviewed recovery decision. Never overwrite or
delete an existing tag automatically.

A later consumer must use an approved authenticated read-only pull credential;
do not copy credentials into this repository, image, logs, or documentation.
The release workflow neither changes package visibility nor grants repository
contents write access. Owner-approved private bootstrap, hosted CI and
publication are not completed here. `build-test` now runs official actionlint
v1.7.12 from the immutable Linux AMD64 Docker manifest
`sha256:9d36088643581e728c969f35141f88139fec77280b2be23c1f66f8e40e1025e7`
against the exact checked-out source SHA. The amd64, SITL and ARM64 jobs also
check out and verify the exact PR head or push SHA; the PR jobs do not write to
GHCR. F-4B-05 has been resolved locally by
running official actionlint v1.7.12 from its immutable Linux AMD64 Docker
manifest; a ShellCheck SC2155 warning was corrected and all workflows passed.
Hosted GitHub Actions parsing and exact-head CI are still separate PR gates.
See docs/superpowers/plans/2026-10-13-phase-4b-blocker-closure.md for the
non-circular PR, registry bootstrap and manual release sequence.

Provision the Raspberry Pi 5 as a runtime host. Do not compile the project or install the simulation/toolchain on the Pi. Use a validated hardware configuration and provide one serial device path and baud rate explicitly after actual device discovery; `config/hardware.yaml` intentionally keeps them `null`. Do not guess `/dev/ttyAMA0` or a TELEM baud value based on earlier devices.

Run with a numeric non-root user and only the minimum required device access. Do not use `--privileged`; any device mapping belongs to Phase 4C and must be verified on the bench first. Keep structured application logs and PX4/flight evidence on persistent host storage outside the container, with bounded retention that never silently deletes unarchived evidence.

Phase 4B verifies image transfer, architecture, startup, deterministic failure without PX4, service lifecycle and persistent logs **without the flight controller connected**. Phase 4C covers separately authorized read-only Raspberry Pi ↔ CUAV X7+ MAVLink/serial telemetry with propulsion rendered safe and failsafes independently checked.

This release procedure performs **no hardware** deployment: it does not
provision a Raspberry Pi, connect a CUAV X7+, map a serial device, or enable
flight actuation.

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
and 94 runtime packages. Its authorized-host bootstrap and independent locked
APT-only replay succeeded with identical inventory hashes. This does not
replace full-image hosted CI evidence or authorize hardware deployment,
publication, or Phase 4A completion. Final hosted CI remains required.
