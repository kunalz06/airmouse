# Phase 4B Release-Safety Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Phase 4B release records and idempotent retries safe evidence of an actual telemetry-only ARM64 GHCR release.

**Architecture:** Extend the existing standard-library Python verifier with an explicit, typed release-record schema and separate original-release/current-retry evidence. Keep GitHub/GHCR orchestration in the manual workflow, but make its package/tag API paths fail closed and emit precise state evidence. No runtime, vehicle, MAVSDK, PX4, or hardware behavior changes.

**Tech Stack:** Python 3 standard library, GitHub Actions YAML, Bash, existing unittest integration tests.

**Spec:** `docs/superpowers/specs/2026-10-13-phase-4b-image-release-design.md`

## Global Constraints

- Work only on `codex/phase4b-release-exec`; do not push, open a PR, merge, dispatch a workflow, or publish.
- Preserve manual-only dispatch, exact-main gating, one new-build policy, pinned transport, telemetry-only policy, non-root runtime, and no-hardware boundary.
- A non-idempotent VERIFIED record requires every mandatory Boolean check to be `true`; missing, null, string, or false values block it.
- An idempotent VERIFIED retry must bind the original VERIFIED record to its exact successful workflow run ID **and attempt**, source SHA, registry manifest/config/layers/labels, and retained artifact metadata (ID, digest, workflow_run.id and head_sha). GitHub artifact metadata does not intrinsically establish the attempt: independently verify the attempt's successful conclusion and explicitly reject ambiguous artifact-to-attempt association. Current retry checks remain separate and must each pass; NEVER manufacture original-local success markers for skipped work.
- Package/tag absence, authorization, API, registry, malformed-response, and race ambiguity fail closed; no tag is overwritten.
- Credentials remain step-scoped, temporary, and excluded from artifacts.

## Review Focus

- A syntactically valid VERIFIED record with false or non-Boolean checks must be rejected by Task 1.
- A record from a different workflow attempt, artifact, source, config, or manifest must not authorize Task 2 retry.
- An HTTP 404 that could be authorization hiding rather than proven absence must block in Task 3.
- A post-push or interrupted transfer must remain UNVERIFIED, with a precise failed stage and no usable reference, in Task 3.
- Artifact and temporary credential paths must not include auth files, and no flight-capable MAVSDK path may be introduced, in Tasks 3–4.

### Task 1: Typed release-record and prior-evidence verifier

**Files:**
- Modify: `scripts/verify-runtime-release.py`
- Modify: `tests/integration/test_runtime_release_verification.py`

**Interfaces:**
- Consumes: JSON release records, remote OCI identity, successful workflow metadata, and prior-artifact identity.
- Produces: a normalized release record only when its type-checked evidence is complete; an idempotent verification result only when original and retry evidence agree.

- [ ] **Step 1: Write failing verifier tests**

Cover VERIFIED records with individually typed mandatory Boolean gates: telemetry-only patch, source command boundary, ARM64 artifact, bounded execution, image policy, APT closure, runtime manifest/provenance, remote digest identity, digest-qualified post-pull artifact/execution/image-policy, and private visibility. Exercise each gate false/missing/null/string; reject record identities with incorrect run attempt/config/artifact. Separate original-build evidence from current-retry checks: original must be all-true, current retry must have all applicable checks true and original-local checks NOT_RUN, never passed.

- [ ] **Step 2: Run the new verifier tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py -v`

Expected: failures demonstrating that false or incomplete VERIFIED records are currently accepted.

- [ ] **Step 3: Implement explicit schemas**

Implement typed validators for required digest/string/Boolean/object fields. Make `make_release_record(raw: dict) -> dict` require all original-release checks for a non-idempotent VERIFIED record. Make `verify_existing_release(remote: dict, evidence: list[dict], source_sha: str, prior_record: dict, prior_artifact: dict) -> str` require run ID/attempt/artifact binding and all true original checks; validate retry evidence separately.

- [ ] **Step 4: Run verifier tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py tests/integration/test_runtime_manifest.py -v`

Expected: PASS.

Commit: `fix: validate Phase 4B release evidence strictly`

### Task 2: Fail-closed GHCR package and tag orchestration

**Files:**
- Modify: `.github/workflows/release-runtime-arm64.yml`
- Modify: `tests/integration/test_release_runtime_workflow.py`

**Interfaces:**
- Consumes: GitHub package/tag/API responses and retained artifact metadata.
- Produces: only a proven private initial-publication route or a verified immutable retry; all ambiguous/unauthorized states become BLOCKED.

- [ ] **Step 1: Write failing workflow-orchestration tests**

Add **executable** decision-helper tests (not string-matching alone) for authenticated private/public/absence/ambiguous 404/401/403/429/5xx/malformed package responses, registry tag outcomes (absent/matching/mismatched/unverified/reappearing), and authentic prior artifact-to-run/attempt binding. Include failed API/registry calls and interrupted publication. The /users/{username}/packages endpoint cannot be treated as authoritative for private package visibility; use an authenticated private-package-capable endpoint and verify its real token access.

- [ ] **Step 2: Run workflow tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_release_runtime_workflow.py -v`

Expected: FAIL because the existing workflow permits insufficiently proven package/tag absence or does not bind artifact metadata completely.

- [ ] **Step 3: Harden workflow inputs and recovery**

Use an authenticated private-package-aware GitHub API endpoint with validated token access. For initial package creation, require explicit proof that creation is authorized and private-by-default; if a 404 could indicate hidden/unauthorized access, return BLOCKED with owner-configuration guidance rather than assuming absence. Enforce registry tag absence via explicit error classification and independent fresh pre-push check; a SHA tag is policy-immutable, not atomic registry immutability. Obtain and validate actual prior artifact metadata and its run ID/head SHA/digest, the successful exact attempt and the embedded record attempt; reject unverifiable attempt binding. Use executable verification helpers, not only workflow text assertions. Never increase permissions, change package visibility or overwrite tags.

- [ ] **Step 4: Run workflow checks and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_release_runtime_workflow.py -v && git diff --check`. Additionally run actionlint (pinned/verified binary if needed) or another GitHub-Actions-aware validator; generic PyYAML treats `on` as a Boolean and does **not** validate workflow dispatch semantics. Fail closed or record an explicit validation blocker if Actions-aware validation is unavailable.

Expected: PASS.

Commit: `fix: fail closed on Phase 4B registry ambiguity`

### Task 3: Evidence-state accuracy and documentation

**Files:**
- Modify: `.github/workflows/release-runtime-arm64.yml`
- Modify: `tests/integration/test_release_runtime_workflow.py`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/PROGRESS.md`

**Interfaces:**
- Consumes: per-check workflow markers and verifier schema.
- Produces: BLOCKED, UNVERIFIED, or VERIFIED records with exact stage/reason, explicit nulls, original/retry evidence, and no non-verified canonical reference.

- [ ] **Step 1: Write failing evidence-state tests**

Cover interrupted preflight, copy, remote identity, post-pull, visibility, **record generation**, and evidence upload; all-true VERIFIED, and idempotent retry with NOT_RUN current-run original-local checks. Prove VERIFIED depends on a successful entire execution path, not just a touched post-pull marker; a failed final validator must not leave a trusted VERIFIED record. Assert token/temporary-auth files cannot enter uploaded artifacts. Require status and evidence steps with if: always(), a correctly validated machine-readable failure stage/reason, and safe handling of failed artifact publication.

- [ ] **Step 2: Implement per-check state records and documentation**

Emit typed original evidence, current retry evidence, and `NOT_RUN` only for legitimately unexecuted idempotent-local checks. Preserve observed digests and diagnostics, never generate a usable reference outside VERIFIED, and document private access, immutable-tag limits, and explicit UNVERIFIED recovery authorization. Do not add a fictional digest.

- [ ] **Step 3: Run focused suite and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/integration/test_runtime_release_verification.py tests/integration/test_release_runtime_workflow.py tests/integration/test_runtime_manifest.py -v && tests/integration/test_mavsdk_boundary.sh && tests/integration/test_mavsdk_telemetry_patch.sh && git diff --check`

Expected: PASS.

Commit: `docs: clarify Phase 4B release recovery evidence`

### Task 4: Full local verification and independent review

**Files:**
- Modify only if review identifies a release-safety defect.

**Interfaces:**
- Consumes: final local branch diff and all release-safety evidence paths.
- Produces: an independent finding list and a clean local commit sequence, or explicit blockers.

- [ ] **Step 1: Run complete local verification**

Run: `./scripts/test.sh && ./scripts/lint.sh`, plus the Task 3 focused suite, GitHub Actions-aware validation (prefer actionlint), extracted embedded Bash syntax, Python compilation/import, and `git diff --check`. Preserve and use the existing nidar-dev image/build/dev when available; do not rebuild just to satisfy a documentation-only check.

Expected: all 19 C++ and 11 bounded-log tests, focused tests, telemetry-only boundary checks, lint, and static checks pass. Do not perform a Docker rebuild, SITL, hardware access, push, or registry publication.

- [ ] **Step 2: Request an independent reviewer**

Review all release-record truth conditions, API/registry ambiguity, idempotent artifact binding, credential isolation, partial-publication transitions, tests, and telemetry-only boundary. Fix Critical/High and release-correctness Medium findings with RED→GREEN tests, then request a final re-review.

- [ ] **Step 3: Commit and record final state**

Run: `git status --short && git diff --check && git log --oneline -n 4`

Expected: only scoped commits, clean tree, no external side effects. **Add and commit this initially untracked hardening plan**. Record reviewer name/context, reviewed commit SHA, severity/file/line findings, correction/re-review outcomes, test evidence and final readiness in docs/test-results/phase-4b-independent-review.md plus the SDD ledger. Do not claim independent review where none was performed.

## Implementation checkpoint — October 13, 2026

- Tasks 1–3: local code and documentation changes implemented, including typed
  Boolean release gates, first-party private-package checks, unverified first
  publication BLOCKED on ambiguous package 404, exact prior artifact ZIP digest
  and run-attempt time-window binding, and separate original/retry results.
- Local tests: 43 focused Python tests, 19 C++ and 11 bounded-log tests, lint,
  telemetry patch/boundary, and inline workflow Bash syntax passed.
- Repository visibility changed: authenticated GitHub repository access on
  October 13, 2026 confirmed `kunalz06/airmouse` private (ID `1403957960`).
  GHCR package existence, visibility, owner, repository link and Actions write
  access remain unverified locally. GitHub's container registry documentation
  says a first package is private by default and `GITHUB_TOKEN` publication
  links the workflow repository; neither fact resolves a package API 404,
  which may also mean hidden/unauthorized. The workflow blocks this state
  pending an owner-reviewed private-package bootstrap and a proven package
  response; no image was pushed to test it.
- Independent findings F-4B-01/02/03 prompted executable regression tests and
  scoped corrections: strict package identity/owner/private repository checks,
  full post-pull package rechecks, source-label verification, provisional
  diagnostic evidence before final artifact upload, and summary/reference only
  after the final upload succeeds. F-4B-04 updates the deployment/task/ledger
  state and documents tag-race recovery. Independent re-review remains pending.
- F-4B-05 remains BLOCKED: actionlint is unavailable locally. A pinned
  v1.7.12 binary download yielded a zero-byte file and failed checksum
  verification. Generic YAML/Bash checks are insufficient Actions-aware proof.
- Task 4 is **not complete**: one independent reviewer and GitHub-hosted Actions
  validation remain outstanding. A locally passing suite is not approval to
  push, merge, dispatch a release or publish.

## Fast-track completion protocol (mandatory for the remaining work)

1. Treat `8c7aa91` as the last committed implementation baseline; verify actual HEAD and clean worktree first. No Codex CLI review/build worker was running at the latest status check, so **start one deliberate review task instead of waiting on idle processes**.
2. **One independent, focused release-safety review** of the final diff, limited to GHCR authentication/private visibility, package/tag absence and immutable retries, exact SHA/run/attempt/artifact identity, typed VERIFIED truth conditions, evidence upload/failure states, and telemetry-only command boundary. Review the existing source directly; no repeated speculative architecture reviews.
3. Collect all P0/P1 findings and release-correctness P2 findings in one findings batch with file/line reproduction. Fix them together with failing-before/passing-after regression tests. Request **one targeted re-review only of changed security-critical paths and regression coverage**. Reopen the wider review only if the fixes modify trust boundaries or reveal a new P0/P1 vulnerability.
4. Execute deterministic release/verifier tests and workflow/Bash syntax after each relevant source change; **run the full 19 C++ + 11 bounded-log suite and lint once at the final implementation commit** (rerun affected checks only if those files subsequently change). Do not rebuild development images, run SITL, or touch hardware for workflow-only changes. Current baseline already passed 48 focused tests and YAML/Bash checks.
5. If `actionlint` cannot be obtained from a validated/pinned source, record a specific Actions-aware-validation blocker; **do not repeatedly download unverified binaries**. Hosted validation belongs to a separately authorized push/PR gate. Do not imply local YAML parsing is an actionlint pass.
6. GHCR existence/visibility and authenticated write access must be positively established; a private repository does not prove package access. An ambiguous 404 is BLOCKED. No initial publication, tag overwrite, workflow dispatch, PR, merge, or branch push without explicit user authorization.
7. Update one independent-review ledger with findings/test evidence, make **one consolidated local remediation commit**, verify clean tree, and report either `LOCAL READY FOR USER-AUTHORIZED PR` or `BLOCKED` with exact unmet gates. Never invent reviewer approval or a registry digest.
- Never silently relax the private-package preflight to make initial GHCR
  publication work. Preserve a manual owner-authorization gate.
