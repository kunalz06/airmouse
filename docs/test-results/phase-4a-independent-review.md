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
