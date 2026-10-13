# Phase 4A update — ARM64 telemetry-only runtime

Phase 4A is complete and merged to `main` as `741cda8c5ab40460c1df7beea47e7c57f11c9e89`. The final exact-head GitHub Actions run #119 (workflow run ID `38207165859`) passed AMD64, full PX4 X500 SITL and ARM64 runtime/provenance validation on `4328e4f4798d617b99d5b95f50704e3fbab0f69b`.

## Implemented scope

- Locked MAVSDK v3.17.2 ARM64 source build to upstream commit `9e3ca17faa84aa868caea10a3bbdab7e53810ced`.
- Produced a minimal non-root Ubuntu 24.04 linux/arm64 `nidar-flight` Docker image with MAVSDK shared library.
- Restored the development host's pinned QEMU/binfmt ARM64 support for verification without touching project safety settings.
- Added ARM64 runtime artifact, dynamic-link, bounded no-PX4 execution and runtime size/hygiene policy gates.
- The **runtime Dockerfile only** uses the signed, dated
  `20261001T000000Z` Ubuntu snapshot. Its three stages
  now install and byte-compare a full sorted package/version/architecture
  closure. `apt-get update` uses `APT::Update::Error-Mode=any`; Ubuntu Release
  signatures and TLS peer verification remain enabled. Development and
  simulation Dockerfiles are unchanged by this runtime APT work.
- Added a checked-in, SHA-256 verified ISRG Root X1 bootstrap bundle for the
  minimal Ubuntu base's first HTTPS update. The normal snapshot-pinned
  `ca-certificates` package replaces that bootstrap trust store immediately.
- Added a bounded dedicated `arm64-runtime` GitHub Actions job; preserved existing amd64 and PX4 X500 SITL jobs.
- Added OCI index/blob validation and a machine-generated manifest with image manifest digest, config digest, source SHA, MAVSDK source commit, target platform, runtime base digest, image size and build timestamp.
- Documented Phase 4B Pi image-consumption inputs without guessing UART/TELEM parameters or starting hardware work.

## Local evidence

The first checked-in closure exists: MAVSDK build 197 packages, application
build 170 packages, and runtime 94 packages. An authorized host completed the
ARM64 APT-only bootstrap that generated those inventories. A separate locked
APT-only replay reproduced all three inventories byte-for-byte with matching
package counts and SHA-256 checksums. The expanded local suite passed 22 tests.
The final hosted run completed successfully. Its ARM64 job verified architecture, libraries, bounded no-PX4 execution, package closure, OCI manifest provenance and disk hygiene; its SITL job ran smoke, headless and both vehicle-launch paths.

See `docs/test-results/phase-4a-*`. The initial image was 173,576,024 bytes uncompressed, below the explicit 220,000,000-byte policy budget. Both runtime artifact/execution checks and policy check passed locally under QEMU. The manifest snapshot in this repository is associated with **pre-closeout local build** commit `ee45a6f`; it is **not** to be presented as the immutable digest of a later source revision.

The final-commit CI job creates its own immutable OCI manifest evidence as `phase-4a-runtime-manifest.txt`, published as a small Actions artifact and job summary. Do not substitute the local snapshot for final CI output.

## Completed closeout gates

- Review the checked-in initial ARM64 three-stage closure and retain evidence
  of the successful authorized-host locked APT-only replay. The Codex sandbox
  cannot run Docker or contact the signed snapshot. Normal runtime builds fail
  closed against this closure; regeneration remains an explicit reviewed operation.
- The locked-replay procedure is:

  ```bash
  docker buildx create --name nidar-builder --driver docker-container --use
  docker buildx inspect nidar-builder --bootstrap
  python3 scripts/verify-runtime-apt-closure.py --check-repository
  scripts/build-runtime-arm64.sh --load \
    --output build/release/nidar-runtime-arm64.oci.tar \
    --image-ref nidar-runtime:phase-4a-closure-validated
  python3 scripts/verify-runtime-apt-closure.py \
    --image-ref nidar-runtime:phase-4a-closure-validated \
    --output-dir build/release/phase-4a-apt-closure
  tests/integration/test_runtime_arm64_artifact.sh nidar-runtime:phase-4a-closure-validated
  tests/integration/test_runtime_arm64_execution.sh nidar-runtime:phase-4a-closure-validated
  tests/integration/test_runtime_image_policy.sh nidar-runtime:phase-4a-closure-validated
  ```

  Inspect the checked-in `config/apt-closure.lock.json` and all three TSV files
  in review before running CI. Regeneration refuses to overwrite the existing
  lock; changing one is an explicit reviewed operation, never an automatic CI
  action.

- The corrected final run #119 passed all AMD64, SITL and ARM64 runtime jobs on `4328e4f`.
- The final ARM64 artifact preserved the non-root `65532:65532` runtime identity, pinned MAVSDK source and generated OCI provenance record.
- The independent Phase 4A review had no unresolved P0/P1 findings; the ownership and bounded-preflight corrections were included in the final run.

Phase 3B active vehicle commands remain separate and unmerged. No serial, Raspberry Pi, CUAV X7+, propulsion or flight hardware integration was performed.

## Final Important finding corrections

The prior evidence-only APT inventory has been superseded by a signed, dated
snapshot and a committed exact closure lock. `config/versions.lock` is the
authoritative snapshot/trust/closure policy, and normal build CLI has no
bootstrap switch. The build does not use a mutable Ubuntu mirror or weaken
TLS/Release signature verification.

CI captures one build-initiation UTC timestamp, derives `SOURCE_DATE_EPOCH`
from it, and creates the loaded image and OCI archive in one build. Manifest
validation requires the label, OCI config creation time, and Docker image
creation time to agree. New stage inventories and provenance must pass full,
fresh hosted CI before reviewer reconsideration.

Phase 4B/C, Raspberry Pi deployment, powered hardware connection and active flight commands remain outside this completed Phase 4A scope.
