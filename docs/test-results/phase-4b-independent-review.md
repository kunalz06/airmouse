# Phase 4B Independent Release-Safety Review Gate

**Status:** PASSED FOR LOCAL REMEDIATION — release remains BLOCKED pending
external authorization and validation gates.

## Scope

Review the complete branch difference from the Phase 4B plan baseline,
including scripts/verify-runtime-release.py, the manual GHCR workflow,
typed original-release/retry records, credential isolation, package API
permissions, retained artifact/run/attempt binding, exact OCI identity,
and fail-closed publication-state handling.

## Local author verification (not independent review)

- 48 focused Python release, workflow and manifest tests passed on implementation baseline `8c7aa91` in the latest verification.
- 19 C++ tests passed.
- 11 bounded-log tests passed.
- Lint, MAVSDK command boundary and telemetry-only patch checks passed.
- Parsed GitHub workflow dispatch keys and checked embedded Bash syntax.
- No actual GHCR image publication, registry digest, hosted release run,
  Raspberry Pi deployment or hardware connection was performed.

## Release blockers / checks the independent reviewer must resolve

1. Confirm the private-package-aware GitHub API can query the destination
   package with the actual workflow installation token and authorized access.
   The repository is now confirmed private, but this does not establish GHCR
   package existence, package visibility, or Actions write access. An API
   404 remains ambiguous and BLOCKED; an owner-approved private GHCR
   package bootstrap may still be necessary.
2. Independently inspect actual GitHub artifact API fields (artifact digest,
   parent workflow run, timestamps) and workflow-attempt endpoint semantics.
   A missing, expired, ambiguously bound or mismatched artifact blocks retry.
3. Verify that all VERIFIED gates require Boolean true for a new release,
   and that current retry checks are never substituted for original checks.
4. Check that any failed finalization, post-push validation or artifact upload
   cannot produce a successful usable deployment reference.
5. Actions-aware validation: **PASSED locally** with official actionlint v1.7.12 in a Docker container pinned to its Linux AMD64 manifest digest, sha256:9d36088643581e728c969f35141f88139fec77280b2be23c1f66f8e40e1025e7. All workflows passed after a ShellCheck SC2155 assignment/export correction. Hosted GitHub validation remains required after an authorized PR.
6. Verify that new test fixtures match the actual GitHub/GHCR API payloads.

**Required verdict:** explicit reviewer identity/context, reviewed commit SHA,
Critical/High/Medium/Low findings with file/line locations, applied fixes,
re-run results and final re-review approval before any push or publication.

## Completed independent review and focused re-review

- **Initial implementation:** `944f590bb943c5c8d189669888e2b1cd412cc823`
- **Remediation:** `8c7aa9110be51a7516c690fc7550d612c566a78a`
- **Final focused review:** `9cf877c97bfe658871af59d8524f9262fc9f215c`
- **Reviewer context:** a separate `/root/independent_reviewer` agent with
  fresh review context; it made no production-code edits.

The initial independent review found these actionable defects, all corrected
in `8c7aa91`: F-4B-01 (P1, insufficient package identity/association
validation), F-4B-02 (P1, a failed evidence upload could follow a
trusted-looking VERIFIED record), F-4B-03 (P1, initial-private-publication
bootstrap was not correctly documented as ambiguous/blocked), F-4B-04 (P2,
obsolete public-repository claims), and F-4B-05 (P2, missing Actions-aware
validation). The first four are resolved. F-4B-05 is now resolved **locally** by running official actionlint v1.7.12 from a digest-pinned Docker image rather than the failed zero-byte binary download; ShellCheck warning SC2155 was corrected without suppression. The pinned checker passed across all workflow files. Hosted GitHub Actions validation is still a separate authorized PR gate.

The targeted fast-track review inspected the current GHCR authentication and
privacy, package/tag ambiguity and immutable retries, exact SHA/run/attempt/
artifact binding, typed VERIFIED truth conditions, evidence-failure
sequencing, and telemetry-only boundary. It found no P0, P1, or
release-correctness P2 findings. No changed-code-only re-review was needed
because that review requested no further security-critical code changes.

Fresh reviewer evidence: 48 focused Python release/workflow/manifest tests,
the MAVSDK boundary and telemetry-patch tests, and `git diff --check` passed.
The final implementation baseline also passed 19 C++ tests, 11 bounded-log
tests, and lint. No Docker build, SITL run, hardware connection, GHCR
publication, push, PR, merge, or workflow dispatch occurred.

**LOCAL REVIEW AND ACTIONLINT GATES PASSED.** Publication is still BLOCKED until (1) authenticated GHCR package visibility/ownership/repository association and workflow access are proven, or an expressly owner-authorized private bootstrap is completed; (2) a separately authorized PR provides hosted CI validation on the exact branch/merge SHA; and (3) an authorized main-branch manual release generates actual digest-qualified evidence. Runtime release evidence is produced by publication, not required before a PR. No runtime registry digest or independent approval for publication is claimed.
