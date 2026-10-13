# NIDAR Phase Task Ledger

Update this file at the completion, blockage, or formal authorization of every project phase. `docs/PROGRESS.md` remains the detailed evidence ledger; this file is the concise phase checklist.

| Phase | Status | Evidence / Commit | Next action |
|---|---|---|---|
| Phase 0 — Project Foundation | Complete | `bf5950c`; `docs/test-results/phase-0-architecture-review.md` | Follow the approved plans. |
| Phase 1 — Build and Toolchain | Complete | Phase 1 build/test and disk evidence | Preserve regression gates. |
| Phase 2 — PX4 SITL / Gazebo | Complete | Phase 2 SITL, GUI/QGroundControl, image, and disk evidence | Preserve SITL regression gates. |
| Phase 3A — Vehicle Telemetry | Complete | `6a4c1107`; GitHub Actions run #76; `docs/test-results/phase-3a-*` | Active commands remain disabled. |
| Phase 3B — Active Vehicle Commands | Separate unmerged implementation / gated | `codex/phase-3b` worktree; nominal SITL recorded, fault matrix and safety review not complete | Do not merge/enable without independently approved flight safety gates. |
| Phase 4A — ARM64 Production Runtime | Complete — telemetry-only | PR #2 merged as `741cda8`; GitHub Actions #119 / `38207165859` passed AMD64, SITL and ARM64 runtime/provenance on `4328e4f`; `docs/test-results/phase-4a-*` | Preserve gates; Phase 4B remains separately authorized. |
| Phase 4B — Verified ARM64 Release + GHCR | Repository private; publication BLOCKED | Authenticated repository check confirmed `kunalz06/airmouse` private; F-4B-01/02/03 remediation in local workflow and verifier, with package state still unverified; no hosted release | Independent re-review, proven private package identity/link and workflow access, locally completed F-4B-05 actionlint validation, then separately authorized GitHub PR/CI and private GHCR bootstrap if required. A 404 never authorizes first publication; no Pi deployment. |
| Phase 4C — Pi Runtime + X7+ Telemetry | Not started / gated | — | Requires a VERIFIED Phase 4B digest; hardware telemetry-only with active commands locked. |
| Phase 5 — Mission / Safety Core | Not started | — | Prerequisites and separate plan required. |
| Phase 6 — Minimum Autonomous Mission | Not started | — | Complete Phase 5 gates first. |
| Phase 7 — Fault Injection | Not started | — | Complete Phase 6 gates first. |
| Phase 8 — GPS-Denied Qualification | Not started | — | Complete Phase 7 gates first. |
| Phase 9 — Navigation | Not started | — | Complete Phase 8 gates first. |
| Phase 10 — LiDAR / SLAM | Not started | — | Complete Phase 9 gates first. |
| Phase 11 — Vision | Not started | — | Complete Phase 10 gates first. |
| Phase 12 — Full NIDAR Mission | Not started | — | Complete Phase 11 gates first. |
| Phase 13 — Release / Competition Freeze | Not started | — | Complete Phase 12 gates first. |
