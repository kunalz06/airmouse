# Phase 4A ARM64 Production Runtime Implementation Plan

> **For Codex:** Execute this plan task-by-task. Read `AGENTS.md` and `docs/MASTER_PLAN.md` first. Use subagents only according to the repository model-routing rules. Do not start Phase 4B hardware transport work or Phase 3B active vehicle commands from this plan.

**Goal:** Produce a reproducible, minimal, verified `linux/arm64` NIDAR runtime image suitable for Raspberry Pi 5 deployment while preserving the Phase 3A telemetry-only safety boundary.

**Starting point:** `main` after Phase 3A merge commit `f4be76290e23a1d38c41d5209ed7680cf1f662ae`.

**Primary output:** An immutable `linux/arm64` runtime image containing the release-mode `nidar-flight` binary and only required runtime dependencies, identified by digest and build provenance.

**Out of scope:** Raspberry Pi host provisioning, CUAV X7+ UART/TELEM wiring, real hardware telemetry, estimator qualification, arm/disarm/takeoff/land/hold, Offboard, setpoints, mission logic, navigation, and any powered-flight behavior.

## Global Constraints

- Preserve all Phase 3A vehicle-layer behavior and tests.
- Active command-shaped `IVehicle` methods must continue to return `RejectedByPhasePolicy`.
- Do not add MAVSDK Action, Offboard, Mission, MissionRaw, or Param command plugins.
- MAVSDK remains isolated to the vehicle adapter.
- PX4 remains the sole owner of stabilization, EKF/state estimation, arming checks, flight modes, and failsafes.
- Target runtime architecture is `linux/arm64`.
- Raspberry Pi 5 is a runtime target, not a development machine.
- The runtime image must not contain Gazebo, PX4 source/build tools, compilers, CMake, Ninja, test frameworks, CI tools, or an IDE.
- Do not silently substitute an unverified MAVSDK ARM64 package.
- Verify every version-sensitive MAVSDK build decision against official upstream documentation/source.
- Keep all builds bounded and enforce repository Docker disk limits.
- Do not use mutable `latest` tags as release identity.
- Do not perform destructive Docker cleanup or delete persistent volumes.
- No Phase 4A claim is complete without fresh CI evidence from the exact final commit.

## Model Routing

Use the repository model policy.

- Architecture/package selection: GPT-5.6 Sol, high reasoning.
- Routine Docker/CMake implementation: GPT-5.6 Sol or Terra where fully specified.
- Tests/fixtures: GPT-5.6 Terra, high reasoning.
- Final review: GPT-5.6 Sol, high reasoning.
- Escalate to GPT-6 Astra only if the ARM64 MAVSDK packaging decision changes a major architecture/safety boundary.

## Branch and Change Policy

Create and work on:

```text
phase-4a-arm64-runtime
```

Do not implement directly on `main`.

Before modifying files:

1. fetch latest `main`;
2. verify Phase 3A is present;
3. verify working tree is clean;
4. branch from the latest `main`;
5. inspect the current runtime Dockerfile, CMake files, version lock, CI workflow, deployment docs, and Phase 3A evidence.

Keep commits small and independently verifiable.

---

## Task 1 — Resolve and pin the ARM64 MAVSDK packaging path

**Purpose:** Select a reproducible ARM64 MAVSDK path with evidence before changing the runtime image.

**Inspect:**

- `config/versions.lock`
- `docker/runtime/Dockerfile`
- `docker/dev/Dockerfile`
- `CMakeLists.txt`
- official MAVSDK v3.17.2 release/source/build documentation.

### Required decision order

1. Check whether MAVSDK v3.17.2 now has an official Ubuntu 24.04 ARM64 artifact compatible with this project.
2. If no suitable official artifact exists, prefer building MAVSDK from the exact pinned v3.17.2 source/tag commit:
   `9e3ca17faa84aa868caea10a3bbdab7e53810ced`.
3. Do not use a Debian/Ubuntu ARM64 package from another release/distribution merely because it installs.
4. Do not float to a newer MAVSDK version in Phase 4A unless the pinned release is proven unusable and the change is separately documented and reviewed.

### Required evidence

Create:

```text
docs/test-results/phase-4a-mavsdk-arm64-selection.md
```

Record:

- inspected official release URL;
- selected packaging method;
- exact version/tag/commit;
- source URL or artifact URL;
- checksum where an artifact is used;
- target architecture;
- build options required;
- runtime libraries produced;
- rejected alternatives and why;
- verification date.

### Exit criteria

- [ ] one ARM64 MAVSDK packaging path is selected;
- [ ] source/artifact provenance is exact and reproducible;
- [ ] no unverified substitute is used;
- [ ] `config/versions.lock` can represent the selected path.

Commit after this decision is documented.

---

## Task 2 — Add a reproducible ARM64 runtime build

**Purpose:** Convert `docker/runtime/Dockerfile` from the Phase 1/3 baseline into a valid Phase 4A multi-stage ARM64 build.

**Files likely modified:**

- `docker/runtime/Dockerfile`
- `.dockerignore`
- `CMakeLists.txt` only if required for clean install/runtime packaging;
- `config/versions.lock`.

**Files likely created:**

- `scripts/build-runtime-arm64.sh`
- `tests/integration/test_runtime_arm64_artifact.sh`.

### Build requirements

The builder stage may contain:

- Ubuntu 24.04;
- compiler/toolchain;
- CMake/Ninja;
- required MAVSDK build prerequisites;
- exact MAVSDK v3.17.2 source/artifact;
- NIDAR source.

The final runtime stage may contain only:

- `nidar-flight`;
- required MAVSDK/shared runtime libraries;
- required C/C++ runtime libraries;
- CA certificates only if demonstrably needed;
- minimal runtime OS dependencies.

The final runtime stage must not contain:

- compiler;
- CMake;
- Ninja;
- Git;
- GoogleTest;
- clang-format/clang-tidy;
- PX4 source;
- Gazebo;
- simulation assets;
- development headers;
- package caches;
- repository source tree.

### Architecture requirement

Build using:

```bash
docker buildx build --platform linux/arm64 ...
```

The build must produce an inspectable OCI/Docker artifact without loading redundant cross-architecture copies into the laptop Docker store unless needed for verification.

### Required verification

`tests/integration/test_runtime_arm64_artifact.sh` must verify at minimum:

- image/OCI architecture is `arm64`;
- expected OS is Ubuntu 24.04 or the explicitly approved runtime base;
- `/usr/local/bin/nidar-flight` exists and is executable;
- the executable reports ARM64/AArch64 ELF architecture;
- required dynamic libraries resolve;
- prohibited development binaries/packages are absent;
- no PX4/Gazebo source or build tree exists;
- no repository source tree is copied into the final image;
- image labels/metadata identify the NIDAR Git commit and MAVSDK version;
- image is not identified only by a mutable tag.

### Exit criteria

- [ ] ARM64 image builds reproducibly;
- [ ] architecture checks pass;
- [ ] runtime dependency checks pass;
- [ ] prohibited development content is absent;
- [ ] image metadata contains build provenance.

---

## Task 3 — Make the ARM64 artifact executable under CI emulation

**Purpose:** Prove the produced ARM64 user-space artifact can start and execute basic non-hardware behavior before it reaches a Raspberry Pi.

Use Buildx/QEMU only as required for CI verification.

### Required runtime checks

Run the ARM64 image in a bounded environment and verify:

```text
nidar-flight --help
```

returns successfully.

Also verify safe failure for a Phase 3A simulation invocation that cannot discover PX4, using a bounded timeout and no hardware devices.

The test must prove:

- process starts on ARM64;
- MAVSDK runtime libraries load;
- CLI works;
- failure remains bounded;
- active command plugins remain absent;
- no privileged container mode is required.

Create or extend:

```text
tests/integration/test_runtime_arm64_execution.sh
```

### Exit criteria

- [ ] ARM64 executable starts under the selected CI emulation path;
- [ ] dynamic linking succeeds;
- [ ] bounded no-PX4 failure works;
- [ ] no active command path is enabled.

---

## Task 4 — Integrate ARM64 packaging into CI

**Purpose:** Make ARM64 runtime verification a mandatory Phase 4A PR gate without breaking the existing Phase 3A amd64/SITL gates.

**Modify:**

```text
.github/workflows/build-test.yml
```

or create a narrowly scoped workflow if separation improves build cost/runtime.

### Required CI structure

Keep the existing:

- amd64 build/test;
- dependency boundary;
- CLI verification;
- lint/static analysis;
- ASan/UBSan;
- PX4 X500 SITL;
- occupied-port negative case;
- normal vehicle SITL;
- sanitizer-instrumented vehicle SITL.

Add an ARM64 packaging job that:

1. builds the runtime artifact;
2. verifies architecture and contents;
3. runs the bounded execution test;
4. records image size/digest;
5. emits no persistent deployment action.

Set a finite job timeout.

Do not push a production image to an external registry unless repository credentials and publication policy already explicitly authorize it.

### Exit criteria

- [ ] all previous Phase 3A jobs remain green;
- [ ] ARM64 packaging job is green;
- [ ] ARM64 artifact digest is available in CI output/evidence;
- [ ] job is bounded.

---

## Task 5 — Enforce runtime image size and dependency hygiene

**Purpose:** Ensure the Pi runtime remains production-minimal.

Create:

```text
tests/integration/test_runtime_image_policy.sh
```

The policy must fail if the runtime image includes prohibited classes of tools or exceeds a documented Phase 4A image-size budget.

### Required checks

At minimum reject:

```text
gcc
g++
clang
cmake
ninja
git
gdb
gazebo
gz
PX4-Autopilot source
GoogleTest development files
MAVSDK development headers
apt package cache
compiler cache
project build directories
```

Determine a realistic maximum image-size threshold from the first clean build, document the rationale, and keep reasonable headroom. Do not invent an arbitrary extremely small threshold that encourages unsafe dependency removal.

Run:

```text
scripts/docker-disk-report.sh
```

and record the result.

### Exit criteria

- [ ] runtime image policy passes;
- [ ] size budget is documented;
- [ ] no development/simulation payload leaks into runtime;
- [ ] Docker/build cache remains within project limits.

---

## Task 6 — Add immutable artifact identity

**Purpose:** Make every Raspberry Pi deployment traceable to an exact source/build.

Add build metadata/labels sufficient to record:

```text
NIDAR git commit
build timestamp
target architecture
MAVSDK version
MAVSDK source commit
runtime base image digest
application version
```

Produce an evidence record:

```text
docs/test-results/phase-4a-runtime-manifest.txt
```

The Phase 4A artifact does not need the full Phase 13 competition release manifest, but it must be unambiguously identifiable by image digest.

### Exit criteria

- [ ] exact image digest recorded;
- [ ] source Git SHA recorded;
- [ ] MAVSDK version/source recorded;
- [ ] target architecture recorded;
- [ ] runtime base digest recorded.

---

## Task 7 — Document the future Raspberry Pi consumption contract

**Purpose:** Define what Phase 4B will receive without implementing Raspberry Pi hardware deployment yet.

Update:

- `docs/DEPLOYMENT.md`;
- `config/hardware.yaml` only for schema/documentation changes that do not guess real UART values.

Document that Phase 4B will consume:

- one verified ARM64 image by digest;
- a validated hardware configuration;
- one explicitly passed serial device;
- persistent host log storage;
- no source compilation on Pi;
- no privileged container;
- no active vehicle command permission.

Do not hard-code or claim a real UART device/baud until bench discovery verifies it.

### Exit criteria

- [ ] Phase 4B input contract is explicit;
- [ ] no real hardware values are guessed;
- [ ] no Phase 3B capability is enabled.

---

## Task 8 — Fresh verification and independent review

Run the full Phase 4A gate on the exact final branch head.

Required verification:

```text
amd64 configure/build/tests
dependency/source-boundary checks
CLI checks
format/static analysis
ASan/UBSan
PX4 X500 SITL
sanitizer-instrumented X500 SITL
ARM64 runtime build
ARM64 architecture/content policy
ARM64 bounded execution
Docker disk report
git diff --check
```

Review focus:

- reproducibility of MAVSDK ARM64 packaging;
- no version drift from v3.17.2 unless separately approved;
- final image contains no development toolchain;
- dynamic library completeness;
- image provenance/digest correctness;
- no Phase 3A safety regression;
- no active command plugin/path;
- no unbounded CI/process behavior;
- no unsafe cleanup;
- no implicit hardware assumptions.

Create:

```text
docs/test-results/phase-4a-independent-review.md
```

No unresolved Critical or Important finding is permitted.

---

## Task 9 — Phase 4A closeout

Create:

```text
docs/PHASE_4A_UPDATE.md
docs/test-results/phase-4a-arm64-build.txt
docs/test-results/phase-4a-runtime-execution.txt
docs/test-results/phase-4a-runtime-policy.txt
docs/test-results/phase-4a-runtime-manifest.txt
docs/test-results/phase-4a-independent-review.md
```

Update:

```text
docs/TASKS.md
docs/PROGRESS.md
docs/REFERENCES.md
config/versions.lock
```

Record:

- exact final branch commit;
- CI workflow run ID;
- build commands;
- exit codes/failure counts;
- ARM64 artifact architecture;
- MAVSDK ARM64 provenance;
- runtime base digest;
- final image digest;
- image size;
- runtime library verification;
- prohibited-tool policy result;
- disk report;
- review findings.

Only mark Phase 4A complete when every exit criterion below is supported by fresh evidence.

---

# Phase 4A Exit Criteria

Phase 4A is complete only when all are true:

```text
MAVSDK ARM64 packaging path is explicitly verified and pinned
linux/arm64 runtime image builds reproducibly
nidar-flight is ARM64 and starts successfully
all runtime shared libraries resolve
runtime image contains no compiler/dev/simulation toolchain
runtime image size policy passes
exact image digest is recorded
Git/source/MAVSDK/base-image provenance is recorded
existing amd64 tests remain green
existing PX4 X500 SITL remains green
ASan/UBSan gates remain green
active vehicle commands remain rejected
MAVSDK remains isolated to vehicle adapter
CI ARM64 job is bounded and green
Docker disk budget remains acceptable
independent review has no unresolved Critical/Important finding
```

# Explicit Non-Goals / Stop Conditions

Stop and report rather than bypass if:

- MAVSDK v3.17.2 cannot be reproducibly built or packaged for ARM64;
- an ARM64 workaround would require an unverified binary;
- the only viable change requires upgrading MAVSDK/PX4 beyond the pinned baseline;
- the runtime needs privileged mode to start;
- Phase 3A tests regress;
- active command code becomes necessary;
- Docker disk limits cannot be maintained without destructive cleanup.

Do not proceed into Raspberry Pi/CUAV X7+ hardware bring-up from this plan.

# Handoff After Completion

After Phase 4A is complete, the next separately planned layer is **Phase 4B — Raspberry Pi Runtime Deployment**, whose first goal is to install/run the exact verified ARM64 image on the Raspberry Pi 5 and validate container/runtime health before any flight-controller connection.

Phase 4C will then cover Raspberry Pi ↔ CUAV X7+ serial MAVLink telemetry bench integration with propulsion made safe.

Phase 3B active vehicle commands remain a separate locked track throughout Phase 4A.
