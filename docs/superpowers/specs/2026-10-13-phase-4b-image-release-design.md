# Phase 4B ARM64 Image Release Design

## 1. Purpose and scope

Publish a verified, telemetry-only NIDAR linux/arm64 runtime to GitHub Container Registry (GHCR) for a later Raspberry Pi 5 deployment. This phase covers **4B-01 release verification** and **4B-02 image publication** only. No Raspberry Pi setup/deployment, CUAV X7+ connection, serial device access, arming, motor control, Offboard, mission control, or active MAVSDK commands are authorized.

Keep the existing Phase 4A image, APT closure, immutable dependencies, telemetry-only patch, and runtime policy. Prefer one verified build and one publication, not extra reviews or duplicate builds.

## 2. Preconditions and exact-source gating

- Implement on the existing phase-4b-image-release branch; merge the tested workflow into main before first use. GitHub workflow_dispatch must run from a workflow present on the default branch.
- Manually dispatch .github/workflows/release-runtime-arm64.yml **only on refs/heads/main**. Check that the workflow event, ref, checked-out full Git SHA, and current remote main SHA agree before the build. Reject stale/non-main dispatches, including a main branch advancement detected during preflight.
- Query GitHub Actions with authenticated, paginated API calls for the build-test workflow on that **exact SHA**, event push, branch main, conclusion success. Confirm all three required jobs (amd64, sitl, arm64-runtime) succeeded, not merely that a run exists. Do not accept a cancelled run, feature-branch run, PR synthetic merge SHA, or previous SHA.
- The release workflow must itself be present in the merged source and pass the required exact-main CI before its first dispatch. Its release image is a **new build** with a new build timestamp; a previous Phase 4A image or evidence ZIP is not its image identity.
- Check the corresponding source and runtime policies before any registry write. Missing CI/API access or inconsistent identity blocks release.

## 3. Workflow permissions, credentials, and concurrency

- Workflow: manual workflow_dispatch only; no automatic image publication from push or pull_request.
- Job GITHUB_TOKEN permissions: **contents: read; actions: read; packages: write**. No repository contents write, administrative, deployment, or secret-scanning permissions.
- Pin third-party GitHub Actions to commit SHAs. Pin or verify the release transport tool version and provenance; do not install an unverified floating binary. Reuse pinned Buildx/QEMU and Phase 4A build infrastructure.
- Use the job GITHUB_TOKEN for GHCR authentication via stdin or a restricted temporary authfile. Never embed tokens in command arguments, artifacts, commits, or logs; clear temporary credentials after use.
- Serialize publication for a source SHA using an Actions concurrency group. Also check whether the destination tag exists **before building** and again immediately before pushing; concurrency alone is not an atomic GHCR tag-immutability guarantee.
- Target registry: ghcr.io/kunalz06/nidar-runtime. Publish only the tag sha-<full-40-character-git-sha>. Do not create or move latest.
- First publication is **private by default**; never change an existing package to public automatically. Check and record its actual visibility/access after creation. If registry permissions or the intended access policy cannot be established, stop and report the blocker. Later Pi pulls must use an approved authenticated read-only credential when the package is private.

## 4. Build once, verify before any push

- Capture the workflow run ID, run attempt, exact Git/source SHA, source timestamp, and one UTC build timestamp. Use one invocation of scripts/build-runtime-arm64.sh with --load and --output for the same linux/arm64 candidate; do not invoke a second build to publish.
- Reuse docker/runtime/Dockerfile, config/versions.lock, locked signed Ubuntu APT snapshot, MAVSDK v3.17.2 telemetry-only patch, and the committed three-stage package-closure inventories.
- Before publication, run the existing image tests: test_runtime_arm64_artifact.sh, test_runtime_arm64_execution.sh, test_runtime_image_policy.sh, and verify-runtime-apt-closure.py. Run the source-only test_mavsdk_boundary.sh separately; it must **not** be described as a test of a pulled image. Do **not** run test_nidar_flight_cli.sh in the release workflow: it needs a prebuilt nidar-dev image and build/dev/nidar-flight, which a fresh runner lacks. The existing AMD64 build-test job already owns that test; validate release-time CLI and negative paths directly against the verified ARM64 image.
- Use record-runtime-manifest.py to verify the candidate OCI archive/index, selected ARM64 image manifest, image config, all layer hashes, package closure, Docker loaded image identity, non-root user, image size limit, source/provenance labels, and timestamp consistency.
- Verify no command-capable MAVSDK plugin/CLI path is exposed. The bounded no-PX4 test must return the established discovery-timeout failure without hanging; do not connect real hardware.
- Record separate fields for Git SHA, selected OCI image manifest digest, OCI image config digest, OCI archive SHA-256, platform, lock hash, and source/run/build identity. Do not confuse these with the GitHub Actions artifact ZIP digest or a Docker image ID.

## 5. Digest-preserving GHCR transport

- Implement publication using a **pinned Skopeo copy tool** operating on the verified OCI archive, not a rebuild or an unverified retag-and-push. Use the oci-archive source and docker://ghcr.io/kunalz06/nidar-runtime:sha-<full-sha> destination.
- Require Skopeo --preserve-digests and --digestfile; explicitly select the source image using --override-os linux and --override-arch arm64 on the AMD64 runner, and verify the selected OCI manifest before transfer. Reject ambiguous platform selection. For a single-platform candidate, publish its verified ARM64 image manifest and preserve its OCI config and layer digests. If the source is an index, explicitly distinguish its top-level index digest from the selected ARM64 image manifest digest.
- Do not silently change media types, recompress layers, or fall back to a digest-changing upload. If the registry cannot accept an identity-preserving transfer, **fail closed** and report the precise incompatibility; no automatic image rebuild or policy downgrade.
- Verify no existing immutable SHA tag points to a different manifest before writing. The tag-name convention is a policy, not a registry-enforced immutability guarantee.

## 6. Idempotent retry and partial-publication policy

- **Before building**, query the SHA tag. If absent, proceed. If present, do not overwrite it.
- An existing tag may be accepted only when its digest, exact source SHA, image/platform provenance, and earlier **successful** publication evidence can be verified. In that case, reverify the digest-qualified pull and report an idempotent success without rebuilding.
- If an existing tag disagrees, lacks trustworthy prior success evidence, or represents an incomplete publication, stop with **BLOCKED / UNVERIFIED**. A fresh build embeds a new timestamp, so the same source SHA alone does not justify replacing a tag.
- If a push succeeds but subsequent checks fail, the remote image may already exist. Mark publication **UNVERIFIED**, record the observed digest and failed check in the workflow evidence, and forbid deployment consumption. Do not claim the failed run prevented upload, delete the package, silently overwrite it, or auto-retry with a different digest. Recovery requires a separately documented decision.
- Registry authentication/authorization failure before upload leaves publication **BLOCKED**, not completed.

## 7. Mandatory post-push remote verification

- Resolve the canonical **registry manifest digest** from GHCR after publication; distinguish a top-level index digest from the selected linux/arm64 manifest digest if both exist.
- Verify the remote image platform linux/arm64; selected manifest, OCI config and layer identities; source, MAVSDK and OS-base labels; package-lock/provenance references; and the published digest against the verified candidate.
- Authenticate Docker independently for a private GHCR pull (for example, docker login ghcr.io with the job token through --password-stdin). A Skopeo authfile does **not** automatically authenticate Docker. Protect and clear temporary credentials.
- Pull the registry image using its **digest-qualified reference** on the verified CI test host; do not run from a mutable tag or assume the locally loaded candidate is the pulled image.
- Run the ARM64 artifact, runtime execution, and image policy tests against this pulled digest-qualified image. The source-only command-boundary test remains a separate pre-push validation.
- Confirm the expected bounded no-PX4 discovery timeout and non-root execution. Do not connect a flight controller. Check the actual package visibility and intended pull authentication.
- Only after **all** checks succeed emit the usable canonical reference: ghcr.io/kunalz06/nidar-runtime@sha256:<verified-registry-digest>. A tag by itself is not deployment approval.

## 8. Evidence and documentation without repository writes

- The publication job has contents: read and **must not try to commit or push** documentation.
- Generate a machine-readable release manifest (JSON or equivalent) and concise human-readable summary on success **and** failure. Run final status generation and evidence-artifact upload with GitHub Actions if: always(), including after a post-push verification failure. If normal record generation was interrupted, produce a minimal BLOCKED/UNVERIFIED diagnostic record. Set an explicit retention period (prefer 90 days where repository policy permits). Include full Git SHA, run ID/attempt, UTC timestamp, exact local/remote image identities, OCI archive checksum, ARM64 platform, lock/closure checks, GHCR visibility when known, canonical digest-qualified pull reference only for VERIFIED releases (otherwise null), test results, and VERIFIED / UNVERIFIED / BLOCKED status.
- Generate a GitHub Actions job summary even on post-push failure when feasible, retaining failure diagnostics. Do not put secrets or large runtime archives into the evidence artifact.
- Durable release evidence beyond Actions retention should be kept in an authorized registry-associated record or a **separate** documentation PR/commit, not by granting contents: write to this release workflow. Until durable evidence is available, treat expiring artifacts as a deployment handoff limitation.
- Update docs/DEPLOYMENT.md, docs/TASKS.md and docs/PROGRESS.md **in the implementation PR** to describe the manual workflow and how to find the resulting release manifest; only record a real digest after a successful run, through a subsequent authorized docs update if desired.
- Keep GHCR private unless explicitly authorized to change visibility. Document the later Pi pull-auth requirement without distributing credentials.

## 9. Implementation checks and failure cases

Add focused, deterministic tests for exact-SHA CI acceptance/rejection, wrong event/ref, missing required jobs, stale main, invalid release identity, existing tag (verified match versus mismatch/unverified), transport/digest mismatch, missing GHCR permission, independent Docker authentication for private pulls, post-pull runtime failure, and always-uploaded failure evidence. Mock external API and registry calls where possible; do not publish test images just to exercise error paths.

The first implementation PR should run the existing AMD64/SITL/ARM64 gates on main after merge. Execute the release workflow manually only after its exact-main CI is green. Avoid unnecessary repeated image builds, unrelated Docker cleanup, or new runtime capabilities.

## 10. Completion criteria

**4B-01 complete:** source is the verified exact main SHA; required build-test jobs and local release candidate checks pass; OCI/closure/provenance identities are recorded.

**4B-02 complete:** GHCR accepts the single verified image without identity change; SHA tag has no conflicting previous content; authenticated digest-qualified remote pull and bounded tests pass; effective visibility is verified; release manifest/summary are recorded and accessible.

Report actual full Git SHA, CI runs, release workflow run/attempt, selected OCI manifest digest, remote manifest digest, archive checksum, digest-qualified pull URL, and any blockers. No fabricated values or implied release approval. If authorization, immutable publication, or post-push verification fails, stop at the explicit BLOCKED or UNVERIFIED outcome.

**Out of scope:** Raspberry Pi provisioning/deployment (4B-03 onward); CUAV serial telemetry (4C); propulsion or flight actuation.
