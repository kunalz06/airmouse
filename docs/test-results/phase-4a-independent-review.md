# Phase 4A independent review — 2026-10-09

**Reviewer:** separate read-only Codex review session, not the implementation author.
**Reviewed range:** `797dab6..ac0823c`.

## Findings and resolutions

- **Important — command-capable MAVSDK plugins:** the candidate image linked Action, Mission, MissionRaw, Offboard, Param and raw MAVLink passthrough despite a telemetry-only CLI. **Corrected, pending fresh build/review:** the Docker build now uses `ENABLED_PLUGINS=telemetry`, applies the locked `mavsdk-telemetry-only.patch` to remove upstream's unconditional passthrough plugin, and artifact verification fails on command-plugin symbols. The candidate image failed this new test.
- **Important — APT closure:** package inputs still float. An attempted Ubuntu snapshot lock did not resolve required ARM64 packages and was removed. **Open; blocks closeout** until a verified snapshot or exact package/version inventory/SBOM is implemented.
- **Important — immutable distribution:** Phase 4A has no authority to publish a deployable image. **Resolved as a scope boundary:** CI evidence is not a deployment channel; `docs/DEPLOYMENT.md` requires a future authorized release to publish a digest-qualified OCI artifact plus checksum before Phase 4B consumption.
- **Important — timestamp/run provenance:** the current OCI created label derives from commit time, not a verified wall-clock build time. **Open; blocks closeout** pending separate source timestamp, build timestamp and CI run identity.
- **Important — candidate CI:** runs `37888297626` and `37888278631` passed amd64, SITL and arm64-runtime on `ac0823c`. **Fresh CI remains required** for the corrective commit.
- **Minor — mutable actions:** checkout and upload-artifact are now SHA-pinned and recorded in `config/versions.lock` (pending fresh CI).
- **Minor — upstream MAVSDK test build:** `BUILD_TESTING=OFF` is now locked for packaging (pending fresh build).

## Positive evidence

Digest-pinned Ubuntu base, multi-stage packaging, numeric non-root user, bounded ARM64 execution, architecture/link checks, size policy, finite ARM64 CI timeout, minimal ARM64-job permissions, and OCI blob identity validation are sound. No Pi/serial/hardware work or active NIDAR command capability was added.

## Verdict

**Not approved for Phase 4A closeout.** No Critical finding was reported, but the unresolved APT closure and build/run provenance requirements are Important. The telemetry-library correction requires fresh independent review and exact-commit hosted CI.


## CI run #89 corrective follow-up — 2026-10-09

GitHub Actions run [#89](https://github.com/kunalz06/airmouse/actions/runs/37902390720) passed AMD64 and SITL, but ARM64 failed before compilation. The pin-verified MAVSDK source checkout succeeded; `git apply --check` rejected `docker/runtime/mavsdk-telemetry-only.patch` with **`error: corrupt patch at line 11`**. The earlier patch hunk's line counts did not match the actual upstream file. This is a patch-format error, not a demonstrated MAVSDK ARM64 compile/link failure.

The patch has been regenerated from the exact v3.17.2 upstream `src/mavsdk/plugins/CMakeLists.txt` (Git blob `5493e6038ad2ca2d87a2c842e423ce8115632595`). A new bounded fixture-based `git apply --check` regression test runs at the start of AMD64 and ARM64 CI, before costly toolchain/image work. It also verifies that the tested result excludes unconditional passthrough and retains the telemetry plugin loop. The **final linked binary's command capability and fresh ARM64 CI remain unverified** until the next hosted run.

**Other Important blockers unchanged:** independently verified APT closure and correct, distinct build wall-clock timestamp/CI run provenance. Do not mark Phase 4A complete based only on the patch validation.

## APT closure and CI build provenance correction — pending final verification

Following successful hosted CI [run #91](https://github.com/kunalz06/airmouse/actions/runs/37904857332) on branch commit `6d8ce8f`, the remaining Important findings have **implementation candidates**, not an approved signoff.

- **APT closure:** The pinned Ubuntu 24.04 ARM64 multi-stage build captures `dpkg-query` package name, exact installed version and architecture for the MAVSDK build, application build and final runtime. The TSV inventories are byte-sorted, and `scripts/verify-runtime-apt-closure.py` validates their structure, SHA-256 hashes, package counts, and actual runtime dpkg state; CI publishes all three TSV inventories and `summary.json`. This is an **exact observed package/version inventory**, not an immutable APT archive snapshot or downloaded package checksum. The base image is digest-pinned, but re-running apt against live repositories may yield different versions; review must assess sufficiency.
- **Provenance:** CI captures one wall-clock UTC build timestamp in `GITHUB_ENV` before building; both --load and --output use that exact timestamp. Runtime OCI labels and manifest separately record the Git checkout/merge SHA, the PR head SHA, source commit timestamp, build timestamp, GitHub Actions workflow, run ID, attempt and repository. Manifest validation compares those fields with CI environment values and independently checks wall-clock/date ordering and OCI-vs-loaded image identity.
- **Offline validation:** 7 positive/negative APT closure parser tests, shell syntax, SHA-pinned MAVSDK patch test, ShellCheck, YAML CI contract and Python syntax checks performed. Fresh ARM64 CI must prove the stage manifests are actually generated/copied and the final image/OCI provenance checks pass.
- **Still gated:** no independent final-revision approval; no merge, artifact publication to a registry, or Pi/CUAV deployment until CI is green, reviewer confirms adequacy, and the ledger is updated.

## Addendum — 2026-10-11 (implementation follow-up; not reviewer approval)

The current uncommitted Phase 4A branch addresses the three Important findings
with a follow-up implementation: ordinary runtime builds no longer expose a
bootstrap APT switch and always request locked mode; bootstrap remains isolated
to the explicit `apt-closure-export` regeneration target. APT snapshot/trust
and closure metadata are now derived from `config/versions.lock`, and the
normal runtime workflow performs one build that simultaneously loads and
exports the OCI archive while binding `SOURCE_DATE_EPOCH` to the captured UTC
build timestamp. Manifest approval now compares that timestamp with the OCI
config's real `created` value and local Docker image `.Created`, not only a
custom label.

The first generated closure is checked in (MAVSDK build 197 packages,
application build 170, runtime 94). An authorized host completed the ARM64
APT-only bootstrap; a separate locked ARM64 APT-only replay matched all three
inventories byte-for-byte. Only the runtime Dockerfile is
in this APT snapshot scope; development and simulation Dockerfiles remain
unchanged. The final hosted CI run and a fresh independent review are still
pending. This addendum records implementation status only and does not amend
the review verdict or mark Phase 4A approved or complete.
