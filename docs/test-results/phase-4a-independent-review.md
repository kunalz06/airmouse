# Phase 4A review gate — pending independent approval

**Status:** NOT independently approved. This document is a review queue, not a claim of completed independent safety review.

Author-side checks performed:

- ARM64 image uses MAVSDK v3.17.2 source commit `9e3ca17faa84aa868caea10a3bbdab7e53810ced`.
- New CI job retains existing amd64 and SITL job definitions, adds pinned QEMU registration and finite 110-minute job timeout.
- Final runtime is non-root and excludes compilers, PX4/Gazebo trees and MAVSDK development headers.
- Runtime CLI still exposes no active flight commands; the retained tests reject `RejectedByPhasePolicy` command paths.
- OCI manifest and config blobs are SHA-256-checked, and published provenance is compared with the exact Git HEAD.
- ARM64 image budget is enforced at 220,000,000 uncompressed bytes.
- No destructive Docker garbage collection, Pi device access or active-command permissions were added.

**Reviewer must independently validate:**

1. ARM64 build and source reproducibility, including any risks from unpinned Ubuntu `apt` package versions.
2. OCI manifest identity correctness across Docker/containerd image store variants.
3. CI workflow permissions, artifact upload scope, job timeout and effects of QEMU installation.
4. Shared library closure, OS image identity, non-root execution and development-tool exclusions.
5. Phase 3A telemetry-only command boundary and negative tests.
6. All fresh final-commit CI runs and disk evidence.

Known release-hardening follow-ups inherited from earlier phases: immutable GitHub Actions action-SHA pinning and stronger apt dependency pinning. Independent reviewer must classify severity before closeout.

**Signoff:** Pending. No independent reviewer identity or decision is fabricated.
