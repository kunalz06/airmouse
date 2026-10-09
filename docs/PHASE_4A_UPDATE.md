# Phase 4A update — ARM64 telemetry-only runtime

Phase 4A work is implemented in `phase-4a-arm64-runtime` and undergoing closeout. **Phase 4A is not yet authorized as complete** until hosted CI on the exact final commit and an independent review meet the approved plan.

## Delivered

- Locked MAVSDK v3.17.2 ARM64 source build to upstream commit `9e3ca17faa84aa868caea10a3bbdab7e53810ced`.
- Produced a minimal non-root Ubuntu 24.04 linux/arm64 `nidar-flight` Docker image with MAVSDK shared library.
- Restored the development host's pinned QEMU/binfmt ARM64 support for verification without touching project safety settings.
- Added ARM64 runtime artifact, dynamic-link, bounded no-PX4 execution and runtime size/hygiene policy gates.
- Added a bounded dedicated `arm64-runtime` GitHub Actions job; preserved existing amd64 and PX4 X500 SITL jobs.
- Added OCI index/blob validation and a machine-generated manifest with image manifest digest, config digest, source SHA, MAVSDK source commit, target platform, runtime base digest, image size and build timestamp.
- Documented Phase 4B Pi image-consumption inputs without guessing UART/TELEM parameters or starting hardware work.

## Local evidence

See `docs/test-results/phase-4a-*`. The initial image was 173,576,024 bytes uncompressed, below the explicit 220,000,000-byte policy budget. Both runtime artifact/execution checks and policy check passed locally under QEMU. The manifest snapshot in this repository is associated with **pre-closeout local build** commit `ee45a6f`; it is **not** to be presented as the immutable digest of a later source revision.

The final-commit CI job creates its own immutable OCI manifest evidence as `phase-4a-runtime-manifest.txt`, published as a small Actions artifact and job summary. Do not substitute the local snapshot for final CI output.

## Mandatory remaining gates

- GitHub Actions candidate runs `37888297626` and `37888278631` passed amd64, ASan/UBSan, X500 SITL and ARM64 runtime jobs for `ac0823c`; they are not evidence for a later corrective commit.
- Verify all amd64, ASan/UBSan and X500 SITL jobs green on the exact final branch commit in GitHub Actions.
- Verify the new ARM64 CI job green and retain its manifest, size and disk evidence.
- Obtain an independent review with no unresolved Critical or Important findings; the author/assistant's own inspection is not an independent signoff.
- Close phase ledgers as **Complete** only after the above evidence is recorded. Until then the explicit status is **in progress / verification and review pending**.

Phase 3B active vehicle commands remain separate and unmerged. No serial, Raspberry Pi, CUAV X7+, propulsion or flight hardware integration was performed.
