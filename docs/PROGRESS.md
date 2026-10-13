# Progress Ledger

- Current phase: **Phase 4A — ARM64 Production Runtime (complete)**. Phase 3A remains complete on implementation commit `6a4c1107af32db1298b9d4b3529825221020f3d6`.
- Current task: Preserve the Phase 4A telemetry-only runtime and its AMD64, SITL and ARM64 verification gates. Phase 4B is separately authorized work.
- Completed task IDs: P0-01 through P0-06; Phase 1 toolchain; Phase 2 PX4/Gazebo SITL; Phase 3A MAVSDK vehicle telemetry; Phase 4A Tasks 1–9.
- Phase 4A local evidence: `docs/test-results/phase-4a-*`; `build/release/phase-4a-amd64-tests.log`, `build/release/phase-4a-sitl-tests.log`, `build/release/phase-4a-disk-report.txt` (local/ignored logs). The OCI manifest checked in as a snapshot is associated with pre-closeout build `ee45a6f`. The new CI job must publish per-revision OCI and APT-stage package inventories with verified build/run provenance.
- Phase 3A hosted evidence: GitHub Actions build-test run #76 (workflow run ID `37195954497`) passed on implementation commit `6a4c1107af32db1298b9d4b3529825221020f3d6`. Do not represent this as Phase 4A hosted evidence.
- Architectural rulings: PX4 owns stabilization, EKF and failsafes. MAVSDK is only the vehicle adapter. Phase 4A uses CompanionComputer identity, forwarding disabled, no enabled active commands, non-root ARM64 runtime and no UART/TELEM assumptions.
- Final hosted evidence: GitHub Actions run #119 (workflow run ID `38207165859`) passed AMD64, full PX4 X500 SITL and ARM64 runtime/provenance on exact PR head `4328e4f4798d617b99d5b95f50704e3fbab0f69b`. PR #2 merged to `main` as `741cda8c5ab40460c1df7beea47e7c57f11c9e89`.
- Review findings: the SITL container-ownership race and bounded-preflight findings were corrected before the final run. The independent Phase 4A review recorded no unresolved P0/P1 findings. No Raspberry Pi hardware work is authorized.
- Phase 3B active-command code is present on separate unmerged `codex/phase-3b` worktree; it is not part of or approved by Phase 4A.
- Next task: Phase 4B Pi runtime startup is a **separately authorized** follow-on; Phase 4C physical read-only serial telemetry comes after it.

- Closeout: runtime packaging, OCI provenance and telemetry-only boundary are verified by the final hosted run. No Phase 4B authorization.
