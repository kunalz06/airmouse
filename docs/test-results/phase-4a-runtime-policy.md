# Phase 4A runtime image size and hygiene policy

The 2026-10-09 inspected image `nidar-runtime:phase-4a-local` was reported by `docker image inspect` as **173,576,024 bytes** (uncompressed Docker image size; `docker images` displayed 37.9 MB under its display convention). The enforcement budget is **220,000,000 bytes**, about 27% headroom to accommodate small distro/security dependency changes without obscuring large toolchain or simulation leaks.

The executable policy is `tests/integration/test_runtime_image_policy.sh IMAGE_REF` and rejects an image above this limit, a non-ARM64 image, root runtime identity, known development tools, populated source/build/cache directories and apt package-list caches. `tests/integration/test_runtime_arm64_artifact.sh` separately audits exported root filesystem for ELF architecture, MAVSDK libraries and missing toolchains; the two tests are complementary.

Image size here is **not** an OCI archive compressed size and **not** a registry distribution size. Any later budget increase requires measured justification and review. Verification on the exact Phase 4A final commit is recorded in the CI job; this policy itself is not a substitute for the CI gate.
