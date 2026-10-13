# Phase 4B — Definitive Blocker Closure Plan

## Baseline and authority

- Branch: codex/phase4b-release-exec. Verify actual HEAD and a clean worktree before implementation.
- Source review: passed for local remediation, with no outstanding P0/P1/release-correctness P2 findings reported by the independent reviewer.
- GitHub repository: kunalz06/airmouse, verified private.
- Actions-aware validation: official actionlint v1.7.12 Docker AMD64 image, pinned to manifest sha256:9d36088643581e728c969f35141f88139fec77280b2be23c1f66f8e40e1025e7, passed for ALL workflow files after correcting ShellCheck SC2155.
- 48 focused release/verifier/workflow/manifest tests passed after the correction; git diff --check passed.
- No hosted Phase 4B CI, no GHCR runtime package identity, no runtime registry digest, and no authorized publication has been established.
- No vehicle, PX4, active MAVSDK, Raspberry Pi, hardware, SITL, or flight changes.

## Release gates: avoid circular requirements

| Gate | What it proves | When / authorization |
| --- | --- | --- |
| A — Local implementation ready | Reviewed source, passing release tests, pinned actionlint, clean local commit | Codex may complete locally |
| B — Hosted PR ready | Workflow accepted by hosted parser; exact PR-head AMD64, SITL, ARM64 CI passes | Requires owner-authorized push and PR, NO release |
| C — Private GHCR access ready | Private GHCR package, ownership, repository link and workflow access verified | Owner-controlled; separately authorize bootstrap if needed |
| D — Runtime release VERIFIED | Manually authorized main release builds once, publishes private, preserves digest, pulls/test, uploads verified artifact | Requires separate release authorization |

A successful runtime release run is the OUTPUT of Gate D. It cannot be a prerequisite for Gate A or for opening a PR.

## Task 1 — Close Actions-aware lint

- [x] Obtain official actionlint from a verified Linux AMD64 Docker manifest digest. No need for the failed zero-byte tarball download.
- [x] Correct SC2155 by assigning the build timestamp and then exporting it, without disabling the warning.
- [x] Run pinned actionlint against every workflow: zero findings.
- [x] Re-run 48 focused Python tests and git diff --check.
- [ ] Commit the ShellCheck correction and record the pinned linter digest, result and test evidence in the independent review ledger.

For local repeat runs, use the installed verified actionlint container with Docker options: --rm, --pull=never, --network=none, --read-only, --cap-drop=ALL, --security-opt=no-new-privileges, and a read-only repository mount. Never execute a mutable tag as a release-quality gate.

## Task 2 — Resolve the private GHCR preflight

- [ ] Use owner-authenticated GitHub package settings or documented package APIs to learn whether ghcr.io/kunalz06/nidar-runtime exists. The read-only owner identity is distinct from the workflow installation GITHUB_TOKEN.
- [ ] If a package exists, require metadata: name nidar-runtime; type container; owner kunalz06; private visibility; linked repository kunalz06/airmouse; linked repository currently private; workflow has permitted package Actions access.
- [ ] Inspect the actual GitHub Actions GITHUB_TOKEN permission context, not merely the YAML declaration. It must be able to read package metadata and publish only where the repository owner has authorized write access.
- [ ] Test the real JSON and status semantics of the chosen authenticated API endpoint. A private package may be hidden from insufficiently authorized identities. A 404 alone does NOT prove absent.
- [ ] Existing private package, all checks true: leave the package alone and mark Gate C ready.
- [ ] Existing public, wrong owner, wrong association, wrong repository or access denied: BLOCK. Never auto-change visibility, delete versions or move immutable tags.
- [ ] Missing package or ambiguous 404: keep standard release BLOCKED and follow the separately authorized bootstrap below.
- [ ] Add deterministic negative tests for missing/private/public/mismatched/hidden/unauthorized/error cases and verify no tokens or raw secret-bearing API bodies are uploaded.

Do not assert that a private repository guarantees existing private GHCR package permissions. GitHub documents default visibility and repository association behavior for a newly published package, but those defaults are not evidence about an already existing package.

## Task 3 — One-time owner-authorized bootstrap, only if package truly absent

- [ ] First ask the owner to confirm in GitHub package settings that nidar-runtime is absent or inaccessible and to approve a package bootstrap. Do not run it automatically.
- [ ] Prepare a distinct manual bootstrap workflow on the private repository with only the minimum required token permissions, an explicit human confirmation input, concurrency and no runtime release tag.
- [ ] Publish a tiny, non-sensitive sentinel image using the repository GITHUB_TOKEN and source label pointing to https://github.com/kunalz06/airmouse. Use a unique bootstrap-specific tag that cannot be mistaken for sha-<full-source-sha>. Never include application source, MAVSDK, credentials, hardware or flight actuation.
- [ ] Immediately verify the resulting package's actual private visibility, kunalz06 owner, linked airmouse repository, and Actions access using an appropriately authenticated identity. Fail closed if any check is absent or contradictory. Record sanitized bootstrap evidence only.
- [ ] Do not mark a sentinel image as a VERIFIED runtime release. Do not invent or promote a deployment digest. Keep the bootstrap tag as distinct provenance until the owner separately authorizes deletion.
- [ ] If GitHub package creation or association cannot be proven safe, stop with exact required manual owner settings. Do NOT relax the real release's private-package preflight.
- [ ] After an authorized bootstrap succeeds, rerun the standard read-only package preflight. Only a positive response with correct private package metadata can unlock Gate C.

Bootstrap is a separate registry publication action requiring explicit approval. Preparing code for it does not authorize dispatch.

## Task 4 — GitHub integration and hosted workflow validation

- [ ] After Gate A, request user permission to push this branch and open the PR.
- [ ] In build-test, install or run an image-digest-pinned actionlint check; validate workflow syntax, expression types, shell inputs and security findings with exact source SHA.
- [ ] Require normal AMD64, SITL and ARM64 runtime jobs on the exact PR head; no manual release workflow or GHCR writes during PR checks.
- [ ] Fix genuine CI issues in one consolidated pass; one targeted independent re-review only if security-critical release code changes.
- [ ] Require explicit owner approval before protected merge into main.
- [ ] After merge, wait for successful exact-main build-test covering required three jobs. Prior PR evidence alone is not sufficient.

Gate B may complete before Gate C. Neither Gate B nor Gate C authorizes the runtime publication without explicit user approval.

## Task 5 — Authorized manual production release

- [ ] Owner approves Gate D after Gate B and Gate C.
- [ ] Manually dispatch release-runtime-arm64 on the current main SHA.
- [ ] Recheck exact-main CI and private GHCR package ownership/association/visibility with workflow identity.
- [ ] Build one locked telemetry-only ARM64 OCI candidate, run bounded tests, verify source labels/lock/APT closure, then check immutable SHA tag immediately before any registry write.
- [ ] Copy exactly that candidate via pinned Skopeo with manifest/config/layers digests preserved; do not overwrite existing tags. If a previous matching release is verified, use documented idempotent retry.
- [ ] Authenticate Docker independently, pull by verified registry manifest digest, repeat mandatory artifact/execution/image-policy tests without flight controller attached.
- [ ] Recheck private GHCR metadata AFTER publication. Complete evidence artifact upload and final verified record only when all Boolean gates and the whole workflow succeed.
- [ ] Record true Git SHA, workflow run ID and attempt, OCI registry digest, source and build provenance, package visibility, image tests, evidence artifact ID and success status in the release ledger.
- [ ] Any interrupted copy, post-push failure or failed artifact upload is UNVERIFIED, no deployable reference, no auto-overwrite and no automatic deletion.
- [ ] No Raspberry Pi rollout or telemetry-on-hardware until a later separately authorized phase.

## Fast-track execution and final handoff

- Reuse the existing 48 focused tests and pinned actionlint image. One reviewer has already examined the security-critical source. Do not repeat broad architecture review.
- One focused negative-test pass for GHCR/first-bootstrap policy, one consolidated fix pass, and one targeted review ONLY when trust boundaries change.
- No unneeded Docker application rebuild, Gazebo simulation, hardware operation or deletion of unrelated images/volumes.
- Commit a clean local branch and report exact test evidence and each gate's current state.
- Stop at each external authorization boundary rather than executing writes to GitHub or GHCR automatically.
- End report with Gate A/B/C/D status and exact next human approval required.
