# NIDAR Phase Task Ledger

Update this file at the completion, blockage, or formal authorization of every project phase. `docs/PROGRESS.md` remains the detailed evidence ledger; this file is the concise phase checklist.

| Phase | Status | Evidence / Commit | Next action |
|---|---|---|---|
| Phase 0 — Project Foundation | Complete | `bf5950c`; `docs/test-results/phase-0-architecture-review.md` | Begin Phase 1 only through its approved plan. |
| Phase 1 — Build and Toolchain | Complete | Phase 1 build/test and disk evidence | Do not start Phase 2 without a separate approved plan. |
| Phase 2 — PX4 SITL / Gazebo | Complete | Phase 2 SITL, GUI/QGroundControl, image, and disk evidence | Phase 3A vehicle telemetry followed through its approved plan. |
| Phase 3A — Vehicle Telemetry | Complete | `6a4c1107`; GitHub Actions run #76; `docs/test-results/phase-3a-*` | Keep active commands disabled; proceed only to separately authorized work. |
| Phase 3B — Active Vehicle Commands | Not started / gated | — | Requires a separate approved design/plan, flight-affecting SITL tests, and safety review. |
| Phase 4A — ARM64 Production Runtime | Planned / authorized | `docs/superpowers/plans/2026-10-06-phase-4a-arm64-runtime.md` | Codex executes the approved ARM64 runtime plan; do not start Pi/X7+ hardware work until its exit criteria pass. |\n| Phase 4B/C — Pi Runtime + X7+ Telemetry | Not started / gated | — | Requires Phase 4A completion; hardware bring-up remains telemetry-only with active commands locked. |
| Phase 5 — Mission / Safety Core | Not started | — | Do not start until its prerequisite phase gates pass. |
| Phase 6 — Minimum Autonomous Mission | Not started | — | Do not start until Phase 5 exit criteria pass. |
| Phase 7 — Fault Injection | Not started | — | Do not start until Phase 6 exit criteria pass. |
| Phase 8 — GPS-Denied Qualification | Not started | — | Do not start until Phase 7 exit criteria pass. |
| Phase 9 — Navigation | Not started | — | Do not start until Phase 8 exit criteria pass. |
| Phase 10 — LiDAR / SLAM | Not started | — | Do not start until Phase 9 exit criteria pass. |
| Phase 11 — Vision | Not started | — | Do not start until Phase 10 exit criteria pass. |
| Phase 12 — Full NIDAR Mission | Not started | — | Do not start until Phase 11 exit criteria pass. |
| Phase 13 — Release / Competition Freeze | Not started | — | Do not start until Phase 12 exit criteria pass. |
