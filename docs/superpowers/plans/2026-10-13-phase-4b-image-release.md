# Phase 4B ARM64 Image Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a verified, digest-qualified, telemetry-only NIDAR ARM64 runtime to GHCR from an exact `main` revision.

**Architecture:** A small, testable Python release-verification utility validates paginated exact-SHA CI evidence and OCI identity. A manual, pinned GitHub Actions workflow runs the existing one-build Phase 4A checks, uses a pinned Skopeo OCI-archive transfer with digest preservation, resolves and validates the registry identity, and uploads release evidence without repository writes.

**Tech Stack:** GitHub Actions, Buildx, OCI archive, pinned Skopeo, Python 3 standard library, existing Bash integration tests.

**Spec:** `docs/superpowers/specs/2026-10-13-phase-4b-image-release-design.md`

## Global Constraints

- Manual workflow-dispatch only; exact checked-out `main` SHA only.
- GitHub token permissions are exactly `contents: read`, `actions: read`, and `packages: write`.
- Use only full-SHA `ghcr.io/kunalz06/nidar-runtime:sha-<SHA>` tags; never use `latest`.
- Build once with the Phase 4A locks, verify before transfer, and never rebuild to publish.
- Preserve the existing non-root, bounded-runtime, APT closure, provenance, MAVSDK telemetry-only, and no-PX4 checks; command-boundary verification remains source-only. Keep the dev-image-dependent test_nidar_flight_cli.sh in AMD64 build-test CI, not the fresh release runner.
- Never deploy to a Pi, touch hardware, expose serial devices, or enable active vehicle commands.
- Keep Docker cache/artifacts bounded; do not delete unrelated images, packages, artifacts, or volumes.

## Review Focus

- Missing, failed, or wrong-SHA CI job evidence must block release before build or publication.
- A local image/config ID must never be treated as the registry manifest digest.
- A pre-existing SHA tag is accepted only for a verified idempotent retry; all other existing or incomplete tags block rather than overwrite a release.
- A changed manifest, config, layer, or media type during transfer must fail closed.
- Digest-pulled no-PX4 execution must remain bounded and reject active MAVSDK command paths.

### Task 1: Exact-SHA CI and OCI identity verification utility

**Files:**
- Create: `scripts/verify-runtime-release.py`
- Create: `tests/integration/test_runtime_release_verification.py`

**Interfaces:**
- Consumes: paginated GitHub Actions runs/jobs JSON and local/remote OCI manifest inspection JSON.
- Produces: `--verify-ci`, `--verify-remote`, and `--write-record` commands with nonzero fail-closed exits.

- [ ] **Step 1: Write failing CI-evidence tests**

Cover one successful exact-SHA push-on-main `build-test` run with `amd64`, `sitl`, and `arm64-runtime`, plus pagination, missing job, failed job, wrong event/ref, stale main, and wrong SHA fixtures.

- [ ] **Step 2: Run the CI-evidence tests and verify they fail because the utility is absent**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py -v`

Expected: FAIL with the utility/module absent.

- [ ] **Step 3: Implement fail-closed `--verify-ci` in `scripts/verify-runtime-release.py`**

Require a successful exact 40-character SHA `build-test` push-on-main run and successful job names `amd64`, `sitl`, and `arm64-runtime`. Reject missing, ambiguous, paginated-away, cancelled, failed, PR merge, feature-branch, stale-main, or mismatched evidence.

- [ ] **Step 4: Run the CI-evidence tests and verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py -v`

Expected: PASS.

- [ ] **Step 5: Write failing remote-identity tests**

Cover an ARM64 OCI manifest whose selected manifest digest, config digest, layers, source label, MAVSDK label, and platform match the verified local candidate; cover changed manifest, layer, provenance, media type, and wrong architecture failures.

- [ ] **Step 6: Implement `--verify-remote` and `--write-record`**

Require digest-preserving transport and reject any changed selected manifest, config, layer, or media type. Emit a concise record that distinguishes Git SHA, archive checksum, selected OCI manifest digest, config digest, build timestamp, workflow run/attempt, visibility, status, and canonical pull reference.

- [ ] **Step 7: Run the complete utility suite and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py tests/integration/test_runtime_manifest.py -v`

Expected: PASS.

Commit: `feat: verify exact-SHA runtime release evidence`

### Task 2: Manual, one-build GHCR release workflow

**Files:**
- Create: `.github/workflows/release-runtime-arm64.yml`
- Create: `tests/integration/test_release_runtime_workflow.py`
- Modify: `scripts/build-runtime-arm64.sh`

**Interfaces:**
- Consumes: exact main SHA, existing successful CI evidence, locked runtime build inputs.
- Produces: one verified local/OCI candidate and a digest-qualified GHCR publication or explicit `BLOCKED`/`UNVERIFIED` evidence.

- [ ] **Step 1: Write failing static workflow tests**

Assert `workflow_dispatch` only, main-only/current-main identity checks, concurrency keyed by immutable SHA, pinned action and Skopeo identities, exactly `contents: read`, `actions: read`, and `packages: write`, private-by-default policy, no mutable tag, pre-build and pre-push tag checks, and all existing runtime checks before registry transfer. Assert Skopeo --override-os linux --override-arch arm64, separately authenticated Docker private pull, exclusion of dev-image-dependent CLI tests, and if: always() failure-evidence upload.

- [ ] **Step 2: Run the workflow tests and verify they fail because the workflow is absent**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_release_runtime_workflow.py -v`

Expected: FAIL with the workflow absent.

- [ ] **Step 3: Extend the runtime build script only as needed to export a named OCI layout from the existing single Buildx invocation**

Keep its existing locked ARM64 build arguments and local verification behavior. Add only OCI archive metadata needed for Skopeo's single-platform digest-preserving transfer; do not add a second build or mutable image tag.

- [ ] **Step 4: Implement `.github/workflows/release-runtime-arm64.yml`**

Use pinned checkout, Buildx/QEMU, and Skopeo setup. Validate `refs/heads/main`, clean tree, current remote-main, and `GITHUB_SHA`/checked-out SHA equality; query authenticated, paginated Actions evidence and invoke `--verify-ci`. Run existing ARM64 artifact, execution, policy, APT closure, manifest, MAVSDK patch, and source-only boundary checks. Do not run test_nidar_flight_cli.sh here: it depends on nidar-dev and build/dev/nidar-flight, which are not prepared on the fresh release runner. AMD64 build-test CI already covers that test; use the verified ARM64 image for release CLI/negative-path checks.

Check the immutable tag before build and immediately before push. Select the source with Skopeo --override-os linux --override-arch arm64; transfer the verified OCI archive with --preserve-digests --digestfile, without rebuilding. Reject source-platform or digest changes. Resolve the remote manifest and invoke --verify-remote. Authenticate Docker separately for private GHCR via --password-stdin, pull by the registry digest, and rerun ARM64 artifact, image-policy, and bounded no-PX4 execution checks.

Generate a failure record if any stage fails, preserving BLOCKED versus UNVERIFIED semantics. Run release status/summary generation and evidence artifact upload with if: always(), including after post-push failure. Retain the artifact for 90 days where permitted, and never grant contents write. Do not mark the digest-qualified image verified until remote pull and tests succeed.

- [ ] **Step 5: Run workflow and shell static checks**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_release_runtime_workflow.py -v && bash -n scripts/build-runtime-arm64.sh && git diff --check`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit: `ci: add verified ARM64 runtime release workflow`

### Task 3: Release records and local verification

**Files:**
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/PROGRESS.md`
- Modify: `tests/integration/test_release_runtime_workflow.py`

**Interfaces:**
- Consumes: the workflow release record from Task 2.
- Produces: digest-qualified consumption guidance without a fabricated release identity and an explicit private-pull authentication boundary.

- [ ] **Step 1: Write failing documentation/record-policy tests**

Require the release artifact schema to distinguish all artifact identities, forbid a fabricated digest, require a `VERIFIED`/`UNVERIFIED`/`BLOCKED` status, and require deployment documentation to state private-pull authentication and the telemetry-only/no-hardware boundary.

- [ ] **Step 2: Run the documentation tests and verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_release_runtime_workflow.py -v`

Expected: FAIL because release-record policy/documentation has not been updated.

- [ ] **Step 3: Update the three ledgers with the release procedure and evidence-artifact policy**

Document that only a successful workflow evidence artifact supplies actual values. Do not invent an image digest, change GHCR visibility, or claim publication before it completes.

- [ ] **Step 4: Run focused local verification**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py tests/integration/test_release_runtime_workflow.py tests/integration/test_runtime_manifest.py -v && tests/integration/test_mavsdk_boundary.sh && tests/integration/test_mavsdk_telemetry_patch.sh && git diff --check`

The dev-image-dependent test_nidar_flight_cli.sh remains in normal AMD64 CI. Release-time CLI validation must run against the already-built ARM64 candidate instead of assuming a prebuilt nidar-dev container.

Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `docs: record Phase 4B runtime release procedure`

### Task 4: Hosted integration and authorized publication

**Files:**
- Create: `docs/releases/phase-4b-runtime-release.yaml` only in a separate authorized documentation update after a successful release workflow.

**Interfaces:**
- Consumes: PR exact-head `build-test` results, merged-main exact-head `build-test` results, and manual release workflow outputs.
- Produces: a verified GHCR digest-qualified pull reference or a precise authorization blocker.

- [ ] **Step 1: Push the branch, open a pull request, and wait for exact-head `amd64`, `sitl`, and `arm64-runtime` success**

Expected: all required jobs pass on the PR head; failures are fixed, never bypassed.

- [ ] **Step 2: Merge only after green enforced checks, then verify a successful exact-main build-test run**

Expected: `main` points to the merged release-workflow source and all three jobs pass for that exact SHA.

- [ ] **Step 3: Dispatch the manual release workflow for that exact main SHA**

Expected: successful preflight, single locked build, pre-push verification, explicit ARM64 Skopeo transfer, remote-digest resolution, separately authenticated Docker digest-pull verification, private visibility confirmation, and a 90-day release-evidence artifact. A failure record and artifact upload must execute even when publication or post-push checks fail (if: always()); a post-push failure is `UNVERIFIED`, never silent cleanup, overwrite, or false success.

- [ ] **Step 4: Commit actual release identity only after successful publication**

Record in a separate authorized documentation commit the source SHA, workflow run/attempt, timestamp, archive checksum, actual registry manifest digest, config digest, architecture, verification status, visibility/authentication, canonical pull reference, and telemetry-only limits. Do not grant the release workflow contents write.

- [ ] **Step 5: Final verification and report**

Run: exact-head GitHub Actions jobs and manual release workflow inspection.

Expected: an actual `ghcr.io/kunalz06/nidar-runtime@sha256:<registry-manifest>` reference, or an explicit missing-GHCR-permission blocker with no falsely claimed publication.
