# NIDAR Phase Task Ledger

Update this file at the completion, blockage, or formal authorization of every project phase. `docs/PROGRESS.md` remains the detailed evidence ledger; this file is the concise phase checklist.

| Phase | Status | Evidence / Commit | Next action |
|---|---|---|---|
| Phase 0 — Project Foundation | Complete | `bf5950c`; `docs/test-results/phase-0-architecture-review.md` | Follow the approved plans. |
| Phase 1 — Build and Toolchain | Complete | Phase 1 build/test and disk evidence | Preserve regression gates. |
| Phase 2 — PX4 SITL / Gazebo | Complete | Phase 2 SITL, GUI/QGroundControl, image, and disk evidence | Preserve SITL regression gates. |
| Phase 3A — Vehicle Telemetry | Complete | `6a4c1107`; GitHub Actions run #76; `docs/test-results/phase-3a-*` | Active commands remain disabled. |
| Phase 3B — Active Vehicle Commands | Separate unmerged implementation / gated | `codex/phase-3b` worktree; nominal SITL recorded, fault matrix and safety review not complete | Do not merge/enable without independently approved flight safety gates. |
| Phase 4A — ARM64 Production Runtime | In progress — candidate CI passed; safety/provenance corrections pending | `phase-4a-arm64-runtime`; GitHub Actions `37888297626`, `37888278631`; `docs/test-results/phase-4a-*` | Verify corrective commit in hosted amd64/SITL/ARM64 CI and obtain fresh independent review; resolve APT closure and build/run provenance before marking complete. |
| Phase 4B/C — Pi Runtime + X7+ Telemetry | Not started / gated | — | Requires Phase 4A completion; hardware telemetry-only with active commands locked. |
| Phase 5 — Mission / Safety Core | Not started | — | Prerequisites and separate plan required. |
| Phase 6 — Minimum Autonomous Mission | Not started | — | Complete Phase 5 gates first. |
| Phase 7 — Fault Injection | Not started | — | Complete Phase 6 gates first. |
| Phase 8 — GPS-Denied Qualification | Not started | — | Complete Phase 7 gates first. |
| Phase 9 — Navigation | Not started | — | Complete Phase 8 gates first. |
| Phase 10 — LiDAR / SLAM | Not started | — | Complete Phase 9 gates first. |
| Phase 11 — Vision | Not started | — | Complete Phase 10 gates first. |
| Phase 12 — Full NIDAR Mission | Not started | — | Complete Phase 11 gates first. |
| Phase 13 — Release / Competition Freeze | Not started | — | Complete Phase 12 gates first. |
