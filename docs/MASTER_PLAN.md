# CODEX MASTER PLAN — NIDAR PRODUCTION DRONE SOFTWARE

## 1. PROJECT STATE

Treat this repository as a completely new project.

Assume:

- no previous source files;
- no previous repository structure;
- no previous build system;
- no previous Docker configuration;
- no previous CI configuration;
- no previous PX4 integration code;
- no previous Raspberry Pi deployment scripts;
- no previous simulation setup;
- no previous documentation.

Create every required project file from this master plan.

Do not search for or depend on earlier project versions.

---

# 2. TARGET SYSTEM

Use the following fixed system baseline unless an explicit technical blocker is proven with evidence.

```text
Development Host: Ubuntu 26.04
Development Language: C++20
Build System: CMake + Ninja
Flight Controller: CUAV X7+
Autopilot Firmware: PX4
Companion Computer: Raspberry Pi 5
Vehicle Interface: MAVSDK / MAVLink
Simulation: PX4 SITL + Gazebo
Production Packaging: Docker
Production Architecture: linux/arm64
Initial Navigation State Source: PX4 EKF2
Initial GPS-Denied Sensors: MTF-01P optical flow + range
Later Mapping: Slamtec 2D LiDAR
Later Perception: Camera + OpenCV/YOLO
```

Keep ROS 2 out of the initial flight-critical path.

If ROS 2 becomes necessary for SLAM or perception, isolate it in a separate process/container and use Ubuntu 24.04 + ROS 2 Jazzy unless current verified upstream support requires a different version.

---

# 3. HOST / CONTAINER POLICY

Use Ubuntu 26.04 only as the native host operating system.

Do not install the PX4 development toolchain directly into Ubuntu 26.04 while PX4 does not officially support Ubuntu 26.04.

Use Ubuntu 24.04 containers for:

- C++ development environment;
- PX4 build environment;
- PX4 SITL;
- Gazebo;
- ROS 2 Jazzy if later required.

Keep the host limited to:

```text
Git
Git LFS
Docker Engine
Docker Buildx
Docker Compose plugin
Codex
editor
SSH
QGroundControl
USB/serial utilities
GPU drivers
basic diagnostics
```

Use native Linux access for:

```text
/dev/ttyACM*
/dev/ttyUSB*
/dev/video*
/dev/dri
```

Do not introduce WSL, Windows-specific paths, usbipd, PowerShell launch scripts, Docker Desktop dependencies, or Windows serial-device mapping.

---

# 4. PROJECT PRIORITIES

Apply this priority order:

```text
1. Correctness
2. Flight safety
3. Deterministic behavior
4. Verification
5. Maintainability
6. Testability
7. Reproducibility
8. Performance
9. Token efficiency
10. Development speed
```

Never improve token usage or development speed by removing required verification.

---

# 5. CODEX OPERATING RULES

Codex must:

1. Read this file before any project planning, coding, review, build, or infrastructure change.
2. Treat this file as the project execution authority.
3. Create the project from zero.
4. Keep the repository as the source of truth.
5. Keep task scope small and independently verifiable.
6. Inspect relevant files before modifying them.
7. Reuse existing interfaces after they are created.
8. Avoid duplicate implementations.
9. Avoid speculative abstractions.
10. Prefer mature libraries over custom implementations.
11. Verify version-sensitive APIs against official documentation.
12. Never invent an API when official documentation is available.
13. Never bypass PX4 safety checks to make a test pass.
14. Never claim a feature works without fresh verification evidence.
15. Never mark a task complete only because code was generated.
16. Keep simulation and hardware on the same application code path wherever practical.
17. Keep flight parameters in validated configuration files.
18. Record architectural decisions in the repository.
19. Record algorithm sources and assumptions in the repository.
20. Keep Docker/build disk usage within the limits in this file.
21. Stop unsafe automatic cleanup before deleting persistent volumes or required artifacts.
22. Keep logs, datasets, model weights, PX4 logs, and recordings outside Docker image layers.
23. Use one write-capable implementation agent per overlapping subsystem at a time.
24. Use parallel subagents primarily for read-only exploration, verification, and independent review.
25. Use the least expensive model that can reliably complete the task.

---

# 6. SAFETY OWNERSHIP

PX4 must own:

```text
attitude control
angular-rate control
motor control
EKF/state estimation
arming checks
pre-arm checks
land detection
low-level position/velocity control
flight-mode management
flight-controller failsafes
Offboard-loss response
core vehicle stabilization
```

The Raspberry Pi application must own:

```text
mission orchestration
high-level navigation
competition logic
mission-level health monitoring
mission timeout handling
LiDAR/SLAM integration
vision integration
structured logging
mission recovery orchestration
command/setpoint generation through PX4-approved interfaces
```

Do not implement a competing low-level flight controller on the Raspberry Pi.

Do not implement a second vehicle state estimator on the Raspberry Pi for the initial system.

If the Raspberry Pi application crashes, hangs, loses MAVLink, loses Offboard control, or powers off, PX4 must retain an independently configured safe response.

---

# 7. REQUIRED REPOSITORY STRUCTURE

Create this repository structure first.

```text
nidar-drone/
│
├── AGENTS.md
├── README.md
├── CMakeLists.txt
├── CMakePresets.json
├── LICENSE
├── .gitignore
├── .dockerignore
│
├── .codex/
│   ├── config.toml
│   └── agents/
│       ├── architect.toml
│       ├── explorer.toml
│       ├── implementer.toml
│       ├── test-engineer.toml
│       ├── reviewer.toml
│       ├── safety-reviewer.toml
│       ├── debugger.toml
│       └── mechanical-worker.toml
│
├── apps/
│   └── nidar-flight/
│
├── include/
│   └── nidar/
│
├── src/
│   ├── vehicle/
│   ├── mission/
│   ├── safety/
│   ├── navigation/
│   ├── health/
│   ├── config/
│   ├── logging/
│   ├── sensors/
│   └── perception/
│
├── config/
│   ├── base.yaml
│   ├── simulation.yaml
│   ├── hardware.yaml
│   ├── competition.yaml
│   └── versions.lock
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── sitl/
│   ├── fault_injection/
│   └── fixtures/
│
├── simulation/
│   ├── worlds/
│   ├── models/
│   ├── scenarios/
│   └── scripts/
│
├── docker/
│   ├── dev/
│   │   └── Dockerfile
│   ├── sim/
│   │   └── Dockerfile
│   └── runtime/
│       └── Dockerfile
│
├── deployment/
│   ├── compose.pi.yaml
│   ├── systemd/
│   └── scripts/
│
├── scripts/
│   ├── bootstrap.sh
│   ├── configure.sh
│   ├── build.sh
│   ├── test.sh
│   ├── sitl.sh
│   ├── deploy-pi.sh
│   ├── docker-disk-report.sh
│   └── docker-gc.sh
│
├── docs/
│   ├── MASTER_PLAN.md
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── INTERFACES.md
│   ├── SAFETY.md
│   ├── TESTING.md
│   ├── DEPLOYMENT.md
│   ├── HARDWARE.md
│   ├── CONFIGURATION.md
│   ├── ALGORITHMS.md
│   ├── REFERENCES.md
│   ├── PROGRESS.md
│   ├── adr/
│   ├── plans/
│   └── test-results/
│
└── .github/
    └── workflows/
        ├── build-test.yml
        ├── sitl.yml
        └── release.yml
```

Copy this master plan into:

```text
docs/MASTER_PLAN.md
```

Keep the repository-root copy and `docs/MASTER_PLAN.md` synchronized if both are retained.

---

# 8. `AGENTS.md`

Create a concise `AGENTS.md`.

Use only project-critical recurring instructions.

Include:

```markdown
# NIDAR Codex Instructions

Read `docs/MASTER_PLAN.md` before planning, coding, reviewing, or changing infrastructure.

Mandatory rules:

1. Treat the repository as the source of truth.
2. Follow the architecture and model-routing rules in the master plan.
3. Do not call MAVSDK outside the vehicle adapter.
4. Do not bypass PX4 safety checks.
5. Flight-affecting code requires automated tests, SITL, and independent review.
6. Do not claim success without fresh verification evidence.
7. Use subagents only according to the master plan.
8. Do not run overlapping write agents on the same subsystem.
9. Enforce Docker/build disk limits.
10. Do not leave placeholder production implementations.
```

Do not duplicate the full master plan inside `AGENTS.md`.

---

# 9. REQUIRED SOFTWARE

## 9.1 Ubuntu 26 host

Install or verify:

```text
git
git-lfs
curl
wget
ca-certificates
gnupg
openssh-client
rsync
xauth
usbutils
pciutils
jq
yq
tmux
docker-ce
docker-ce-cli
containerd.io
docker-buildx-plugin
docker-compose-plugin
QGroundControl
Codex
```

Optional diagnostic tools:

```text
htop
iotop
strace
lsof
tree
```

Verify required groups before adding the user:

```text
docker
dialout
video
render
```

Do not assume groups exist.

---

## 9.2 Development container

Use Ubuntu 24.04.

Install:

```text
GCC
Clang
CMake
Ninja
ccache
GDB
clang-format
clang-tidy
AddressSanitizer
UndefinedBehaviorSanitizer
ThreadSanitizer where compatible
GoogleTest or Catch2
MAVSDK
yaml-cpp
spdlog or equivalent
ShellCheck
Python 3 for tooling
```

Add Eigen only when required by a documented mathematical implementation.

---

## 9.3 Simulation environment

Use:

```text
PX4-Autopilot
PX4 SITL
PX4-supported Gazebo
MAVLink
QGroundControl
```

Pin the PX4 version.

Pin the Gazebo/PX4 simulation environment.

Store all pinned versions in:

```text
config/versions.lock
```

Do not use unpinned `latest` dependencies for competition releases.

---

## 9.4 Raspberry Pi runtime

Install only required runtime components.

Do not install:

```text
Gazebo
PX4 source development toolchain
C++ compiler
IDE
CI tools
large dev packages
```

---

# 10. C++ RULES

Use C++20.

Require:

```text
RAII
const correctness
strong enums
std::chrono for time
explicit unit naming/types
clear ownership
bounded data structures
explicit error paths
deterministic shutdown
```

Avoid:

```text
raw new/delete
hidden global mutable state
unbounded queues
busy loops
sleep-based synchronization
unchecked optionals
silent exception swallowing
magic timing constants
implicit coordinate-frame conversion
implicit unit conversion
```

Prefer:

```text
value semantics
immutable snapshots
message passing
small focused classes
narrow interfaces
```

---

# 11. CORE SOFTWARE INTERFACES

Create and stabilize these interfaces before higher-level mission code depends on them.

```text
IVehicle
INavigation
IRangeSensor
IOpticalFlow
ILidar
ICamera
IHealthSource
ILogger
IClock
```

No mission module may call MAVSDK directly.

Only the vehicle adapter may contain MAVSDK-specific logic.

Required initial vehicle implementation:

```text
MavsdkVehicle
```

Required test implementation:

```text
MockVehicle
```

---

# 12. INITIAL VEHICLE CAPABILITIES

`IVehicle` must support only required capabilities.

Include:

```text
connect
disconnect
connectionStatus
arm
disarm
takeoff
land
hold
startOffboard
stopOffboard
setPositionTarget
setVelocityTarget
flightMode
armedState
batteryState
telemetrySnapshot
estimatorStatus
localPositionValidity
```

Every external command must support:

```text
timeout
rejection
connection loss
stale state
shutdown
```

---

# 13. MISSION STATE MACHINE

Use an explicit deterministic state machine.

Initial states:

```text
BOOT
INITIALIZING
PREFLIGHT
READY
ARMING
TAKEOFF
MISSION
RECOVERY
LANDING
DISARM
COMPLETE
SAFE
EMERGENCY
```

For every transition define:

```text
allowed source state
guard condition
entry action
exit condition
timeout
failure action
event code
```

Do not allow arbitrary state transitions.

Create automated tests for every legal and illegal transition.

---

# 14. HEALTH MODEL

Use explicit system-health levels.

```text
SYSTEM_OK
SYSTEM_DEGRADED
SYSTEM_UNSAFE
SYSTEM_EMERGENCY
```

At minimum monitor:

```text
PX4 heartbeat
telemetry age
armed state
flight mode
estimator health
local-position validity
range freshness
optical-flow validity
optical-flow quality
battery
mission timeout
internal loop health
disk availability
critical process health
```

A stale measurement must never be treated as current.

---

# 15. TIME POLICY

Every state/sensor object that can become stale must track time.

Track:

```text
measurement timestamp
arrival timestamp where relevant
freshness threshold
timeout
```

Use `std::chrono`.

Do not compare timestamps from incompatible clocks without explicit conversion.

---

# 16. COORDINATE-FRAME POLICY

Document every spatial quantity.

Allowed frame names must be explicit.

At minimum distinguish:

```text
NED
ENU
body frame
camera frame
LiDAR frame
sensor frame
```

Document sensor mounting transforms.

Do not infer coordinate frame from context.

Create tests for:

```text
axis direction
sign
rotation
frame conversion
unit conversion
```

---

# 17. CONFIGURATION POLICY

Create:

```text
config/base.yaml
config/simulation.yaml
config/hardware.yaml
config/competition.yaml
```

Do not hard-code operational flight values in source code when they are configuration.

Validate configuration at startup.

Critical configuration errors must prevent transition to `READY`.

Validate:

```text
type
range
units
required fields
cross-field consistency
version/schema
```

---

# 18. LOGGING POLICY

Use structured logging.

Every important event must contain:

```text
timestamp
severity
module
mission state
event code
message
relevant values
```

Do not use uncontrolled `std::cout` in production code.

Persist logs outside the runtime container.

Bound log retention by:

```text
size
age
or mission count
```

Do not silently delete unarchived flight evidence.

---

# 19. ALGORITHM POLICY

No nontrivial algorithm is production-ready until its contract and verification are recorded.

For every nontrivial algorithm, update:

```text
docs/ALGORITHMS.md
```

Record:

```text
name
purpose
inputs
outputs
units
coordinate frames
sample/update rate
preconditions
invariants
numerical limits
failure conditions
latency target
complexity target
source/reference
version assumptions
```

Use this implementation priority:

```text
1. PX4-provided implementation
2. mature maintained library
3. authoritative/reference implementation
4. custom implementation only when necessary
```

Do not reimplement PX4 EKF2 on the Raspberry Pi.

Do not write a custom SLAM implementation unless existing mature solutions are proven inadequate.

Do not add a complex planner until a simpler planner is proven insufficient.

---

# 20. ALGORITHM VERIFICATION

For mathematical or algorithmic code, require:

```text
contract
reference
unit tests
boundary tests
property/invariant tests
independent comparison where practical
integration test
SITL validation where flight relevant
fault test where safety relevant
```

Test:

```text
zero input
nominal input
minimum expected input
maximum expected input
saturation
invalid input
NaN
Inf
divide-by-zero path
overflow where applicable
floating-point tolerance
```

Use double precision by default for project-side mathematical computation unless profiling proves a lower precision is required and accuracy remains acceptable.

---

# 21. BASELINE ALGORITHM CHOICES

## State estimation

Use:

```text
PX4 EKF2
MTF-01P optical flow
MTF-01P range
```

The Pi consumes PX4 state and health information.

---

## Mission control

Use the explicit state machine defined in this file.

---

## Initial navigation

Start with:

```text
bounded position/velocity target generation
mission/geofence bounds
altitude bounds
yaw policy
goal tolerance
timeout
stale-state rejection
```

Do not introduce complex planning before baseline navigation is validated.

---

## LiDAR planning

When LiDAR mapping is integrated:

Use a mature occupancy representation.

Use A* when static-map global planning is sufficient.

Use D* Lite or another incremental replanner only if frequent replanning requirements are demonstrated.

Keep local collision/safety constraints independent of the global planner.

---

## SLAM

Use a maintained SLAM implementation compatible with the selected LiDAR and ROS 2 environment.

Run SLAM outside the core flight supervisor.

SLAM failure must not terminate the mission/safety process.

---

## Vision

Use versioned model assets.

Record:

```text
model hash
input resolution
normalization
confidence threshold
NMS parameters
class mapping
latency target
```

Do not silently replace model weights between releases.

---

# 22. MODEL / SUBAGENT POLICY

Use explicit agent roles.

Do not allow agents to inherit unspecified expensive models when a cheaper explicit model is sufficient.

---

## Main controller

Default:

```text
Model: GPT-5.6 Sol
Reasoning: medium
```

Use `high` for:

```text
phase planning
multi-module integration
difficult debugging
safety-affecting implementation
```

---

## Architect

```text
Model: GPT-6 Astra
Reasoning: high
Sandbox: read-only
```

Use for:

```text
architecture changes
algorithm selection with major trade-offs
safety-boundary changes
cross-subsystem design
final release architecture review
```

Do not use for routine implementation.

---

## Explorer

```text
Model: GPT-5.6 Terra
Reasoning: medium
Sandbox: read-only
```

Use for:

```text
file discovery
symbol discovery
dependency inspection
code-path mapping
existing implementation discovery
```

Return concise findings only.

---

## Implementer

Default:

```text
Model: GPT-5.6 Sol
Reasoning: medium
Sandbox: workspace-write
```

Use for:

```text
C++
MAVSDK
mission logic
navigation
concurrency
hardware integration
nontrivial infrastructure
```

Use Terra instead for fully specified low-risk implementation.

---

## Test engineer

```text
Model: GPT-5.6 Terra
Reasoning: high
Sandbox: workspace-write
```

Use for:

```text
unit tests
boundary tests
fault injection
regression tests
fixtures
scenario generation
```

Do not allow the test agent to redesign production architecture.

---

## Reviewer

```text
Model: GPT-5.6 Sol
Reasoning: high
Sandbox: read-only
```

Review in this priority:

```text
correctness
safety
undefined behavior
concurrency
stale data
validation
resource leaks
error handling
test gaps
maintainability
```

Do not spend review effort on formatting already enforced by tools.

---

## Safety reviewer

```text
Model: GPT-6 Astra
Reasoning: high or xhigh
Sandbox: read-only
```

Use for:

```text
arming
takeoff
landing
Offboard behavior
failsafes
estimator-validity decisions
recovery
emergency transitions
final competition release
```

---

## Debugger

```text
Model: GPT-5.6 Sol
Reasoning: high
Sandbox: workspace-write
```

Escalate to Astra only when:

```text
two evidence-based attempts fail
root cause crosses architectural boundaries
root cause crosses safety boundaries
SITL and hardware disagree without explanation
estimator behavior remains ambiguous
```

Do not repeat the same fix without new evidence.

---

## Mechanical worker

```text
Model: GPT-5.6 Luna
Reasoning: low or medium
Sandbox: workspace-write
```

Use only for:

```text
mechanical renaming
formatting cleanup
documentation synchronization
repetitive configuration additions
fixture generation
one-file low-risk edits with complete specification
```

Never assign flight-critical logic to Luna.

---

# 23. PROJECT-SCOPED AGENT CONFIGURATION

Create:

```text
.codex/config.toml
```

Use conservative concurrency.

Set:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 4
default_subagent_model = "gpt-5.6-terra"
default_subagent_reasoning_effort = "medium"
```

Create explicit agent files under:

```text
.codex/agents/
```

Specify each agent's model and reasoning level.

Do not spawn an agent only because capacity is available.

Normally use:

```text
1 controller
1 implementer
0–2 read-only helpers
1 reviewer after implementation
```

Do not run multiple overlapping write agents.

---

# 24. TOKEN-EFFICIENCY POLICY

Optimize total verified output per token.

Do not optimize individual call length at the expense of retries.

---

## Task briefs

Create task briefs under:

```text
docs/plans/tasks/
```

Each task brief must contain only:

```text
goal
scope
files
interfaces
constraints
test requirements
acceptance criteria
commands
```

Target normal task-brief length:

```text
500–1500 words
```

Do not send a worker the entire project history.

Do not paste prior conversations.

---

## Agent input

Provide only:

```text
task brief path
relevant interface definitions
relevant global constraints
relevant previous finding
required files/symbols
```

---

## Agent output

Require only:

```text
STATUS
FILES CHANGED
TEST COMMANDS
TEST RESULTS
COMMIT
CONCERNS
```

Keep normal report output concise.

Write long logs to files.

---

## Parallel work

Parallelize:

```text
read-only exploration
documentation verification
log analysis
independent reviews
test-result analysis
```

Serialize:

```text
overlapping code changes
architecture and implementation of the same module
mission-state modifications
CMake-wide refactors
Docker-wide refactors
```

---

## Batch mechanical work

Batch same-shape low-risk changes into one task.

Do not create one agent per trivial file edit.

---

## Search policy

Use:

```text
rg
git grep
find
cmake target inspection
symbol references
```

before reading large files.

Read only relevant ranges when possible.

---

# 25. PROGRESS LEDGER

Maintain:

```text
docs/PROGRESS.md
```

Record:

```text
current phase
current task
completed task IDs
commit hashes
test evidence locations
open findings
architectural rulings
failed approaches
hardware blockers
next task
```

Use this ledger after context compaction.

Do not redispatch already completed tasks without evidence of regression.

---

# 26. TASK EXECUTION LOOP

For every task:

```text
Task brief
  ↓
Explorer if needed
  ↓
Failing test or explicit acceptance evidence
  ↓
Implementer
  ↓
Build
  ↓
Targeted tests
  ↓
Independent reviewer
  ↓
Fix + scoped re-review if required
  ↓
Commit
  ↓
Ledger update
```

A flight-affecting task additionally requires:

```text
integration test
SITL
relevant fault injection
independent review
ARM64 package/build check
```

---

# 27. REVIEW FINDINGS

Classify findings as:

```text
Critical
Important
Minor
```

Critical and Important findings must be:

```text
fixed
or
explicitly adjudicated with recorded reasoning
```

Do not silently ignore them.

Use the original implementer for initial fixes.

Escalate model capability only after evidence shows the current agent is stuck.

---

# 28. VERIFICATION POLICY

Before any success claim:

1. Identify the command/test proving the claim.
2. Run it.
3. Read the relevant output.
4. Verify exit code.
5. Verify failure count.
6. Record evidence.
7. Only then make the claim.

Agent self-report is not verification.

The controller must inspect:

```text
diff
test evidence
build evidence
review result
```

Do not say:

```text
done
fixed
working
tests pass
build succeeds
production ready
```

without fresh evidence.

---

# 29. TEST STRATEGY

## Unit tests

Require unit tests for:

```text
state transitions
configuration validation
health rules
timeouts
coordinate transforms
navigation constraints
algorithm boundaries
```

---

## Integration tests

Require integration tests for:

```text
MAVSDK adapter
PX4 telemetry
reconnect
sensor adapters
configuration loading
IPC between isolated services
```

---

## SITL tests

Require SITL for every flight-affecting behavior.

At minimum verify:

```text
PX4 starts
vehicle discovered
telemetry valid
preflight behavior
command acceptance/rejection
mission behavior
safe shutdown
```

---

## Fault injection

Automate:

```text
MAVLink loss
PX4 restart
Offboard loss
stale telemetry
estimator unhealthy
local position invalid
range stale
optical flow invalid
sensor disconnect
mission timeout
application crash
configuration corruption
command rejection
```

---

## Hardware bench

Before powered flight:

```text
props removed
FC/Pi startup order
serial reconnect
mode handling
estimator status
sensor health
app restart
Pi restart
PX4 restart
logging
```

---

# 30. DOCKER IMAGE POLICY

Maintain only these core images initially.

```text
nidar-dev
nidar-sim
nidar-runtime
```

Do not create separate images for every test type.

Add perception-specific images only when process isolation requires them.

---

## `nidar-dev`

```text
Architecture: linux/amd64
Base userspace: Ubuntu 24.04
Purpose:
- C++ build
- tests
- static analysis
- debugging
```

---

## `nidar-sim`

```text
Architecture: linux/amd64
Base userspace: Ubuntu 24.04
Purpose:
- PX4 SITL
- Gazebo
- simulation scenarios
```

---

## `nidar-runtime`

```text
Architecture: linux/arm64
Purpose:
- Raspberry Pi production runtime
```

Keep runtime image minimal.

---

# 31. DOCKERFILE POLICY

Every Dockerfile must:

1. pin critical versions;
2. avoid `latest` in competition releases;
3. use multi-stage builds where useful;
4. use `--no-install-recommends` where appropriate;
5. remove apt lists in the same layer;
6. keep compilers out of runtime images;
7. avoid copying unnecessary files;
8. use `.dockerignore`;
9. keep logs out of image layers;
10. keep datasets out of image layers;
11. keep PX4 logs out of image layers;
12. keep recorded video out of image layers;
13. keep model weights separate unless the runtime target explicitly requires them;
14. avoid duplicate bases when one shared base suffices.

Use this apt pattern:

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends <packages> \
 && rm -rf /var/lib/apt/lists/*
```

---

# 32. `.dockerignore`

Create at minimum:

```text
.git
.github
build
build-*
cmake-build-*
logs
*.log
coverage
.cache
.ccache
.superpowers
.vscode
.idea
docs/test-results
simulation/output
datasets
recordings
core
core.*
*.bag
*.db3
*.ulg
```

Include large model assets only for Docker targets that require them.

---

# 33. DOCKER DISK LIMITS

Enforce default soft limits:

```text
BuildKit cache:        <= 10 GB
ccache:                <= 5 GB
Docker total target:   <= 30 GB during normal development
Minimum free space:    >= 25 GB
```

Inspect actual disk capacity before enforcing the defaults.

If the machine cannot satisfy these limits, record a revised explicit budget in:

```text
docs/CONFIGURATION.md
```

Do not silently exceed the budget.

---

# 34. DOCKER DISK MONITORING

Create:

```text
scripts/docker-disk-report.sh
```

It must report:

```bash
docker system df -v
docker buildx du
df -h /
du -sh build* .cache .ccache 2>/dev/null || true
```

Run it:

```text
after environment bootstrap
after large dependency changes
after simulation image changes
before release
when free-space threshold is crossed
```

---

# 35. DOCKER GARBAGE COLLECTION

Create:

```text
scripts/docker-gc.sh
```

Allow automatic cleanup of:

```text
stopped temporary containers
dangling images
old unused build cache
temporary test containers
```

Use bounded BuildKit cleanup:

```bash
docker buildx prune \
  --filter "until=168h" \
  --max-used-space 10gb \
  -f
```

Use safe dangling cleanup:

```bash
docker container prune --filter "until=72h" -f
docker image prune -f
```

Do not automatically run:

```bash
docker system prune -a --volumes
```

Do not automatically prune named volumes.

Do not remove:

```text
current runtime release
previous known-good release
required PX4 image
required Gazebo image
current development image
unarchived flight logs
required model weights
persistent project volumes
```

Require explicit human approval before deleting named persistent volumes.

---

# 36. MULTI-ARCHITECTURE BUILD POLICY

During normal development:

```text
build/load linux/amd64 only
```

At CI/PR gates:

```text
verify linux/amd64
verify linux/arm64 build/package
```

At release:

```text
produce linux/arm64 runtime artifact
```

Do not load amd64 and arm64 image copies locally after every edit.

Prefer direct export/push for ARM64 release artifacts.

Use cross-platform emulation only when required.

---

# 37. BUILDX POLICY

Use one project Buildx builder:

```text
nidar-builder
```

Do not create a new builder for each session or agent.

Keep BuildKit cache bounded.

---

# 38. CCACHE POLICY

Configure:

```text
CCACHE_MAXSIZE=5G
CCACHE_COMPRESS=true
```

Do not allow unbounded compiler cache growth.

---

# 39. BUILD DIRECTORY POLICY

Use only:

```text
build/dev
build/test
build/release
```

Do not create ad hoc directories such as:

```text
build2
build-old
build-new
build-final
build-final2
```

Use CMake presets.

Delete obsolete build trees after toolchain changes invalidate them.

---

# 40. LARGE DATA POLICY

Keep these outside Docker image layers:

```text
YOLO weights
datasets
camera recordings
ROS bags
PX4 ULog archives
SLAM maps
simulation recordings
large benchmark data
```

Version production assets by hash.

---

# 41. PX4 SOURCE POLICY

Maintain one pinned PX4 source checkout.

Do not clone PX4 separately for each agent.

Do not commit generated PX4 build outputs.

Clean obsolete PX4 build products after changing target/version.

Keep only simulation targets required by NIDAR.

---

# 42. PHASE 0 — PROJECT FOUNDATION

Primary model:

```text
GPT-5.6 Sol
```

Supporting model:

```text
GPT-5.6 Terra
```

Architecture review:

```text
GPT-6 Astra
```

Execute:

1. initialize Git repository;
2. create repository structure;
3. create `AGENTS.md`;
4. create `docs/MASTER_PLAN.md`;
5. create `docs/REQUIREMENTS.md`;
6. create `docs/ARCHITECTURE.md`;
7. create `docs/INTERFACES.md`;
8. create `docs/SAFETY.md`;
9. create `docs/TESTING.md`;
10. create `docs/DEPLOYMENT.md`;
11. create `docs/CONFIGURATION.md`;
12. create `docs/ALGORITHMS.md`;
13. create `docs/REFERENCES.md`;
14. create `docs/PROGRESS.md`;
15. create `.codex/config.toml`;
16. create all `.codex/agents/*.toml`;
17. create `config/versions.lock`;
18. create `.gitignore`;
19. create `.dockerignore`;
20. inspect host disk capacity;
21. record disk budget;
22. create Docker disk scripts.

Exit criteria:

```text
repository exists
required files exist
master plan copied
agent configuration exists
disk budget recorded
architecture reviewed
```

---

# 43. PHASE 1 — BUILD AND TOOLCHAIN

Primary:

```text
Sol + Terra
```

Execute:

1. create Ubuntu 24.04 development Dockerfile;
2. configure C++20;
3. configure CMake;
4. configure Ninja;
5. configure ccache;
6. configure test framework;
7. configure clang-format;
8. configure clang-tidy;
9. configure sanitizers;
10. create minimal executable;
11. create first unit test;
12. create `scripts/configure.sh`;
13. create `scripts/build.sh`;
14. create `scripts/test.sh`;
15. build `linux/amd64`;
16. create minimal runtime Dockerfile;
17. build/package `linux/arm64`;
18. create GitHub build/test workflow;
19. run disk report;
20. prune unnecessary temporary cache.

Exit criteria:

```text
clean amd64 build
unit test passes
static analysis works
arm64 runtime package builds
CI workflow exists
disk limits respected
```

---

# 44. PHASE 2 — PX4 SITL / GAZEBO

Primary:

```text
GPT-5.6 Sol
```

Scripts:

```text
GPT-5.6 Terra
```

Execute:

1. select and pin PX4 release/commit;
2. record PX4 version;
3. create/reuse supported PX4 development container;
4. establish PX4 SITL;
5. establish Gazebo;
6. connect host QGroundControl;
7. create headless simulation script;
8. create graphical simulation script if required;
9. establish clean startup;
10. establish clean shutdown;
11. create automated SITL smoke test;
12. record exact commands;
13. run disk report;
14. remove redundant simulation build/cache artifacts.

Exit criteria:

```text
PX4 SITL boots
Gazebo starts
vehicle is visible
QGroundControl connects
headless smoke test passes
environment is reproducible
```

---

# 45. PHASE 3 — VEHICLE LAYER

Primary:

```text
GPT-5.6 Sol
```

Tests:

```text
GPT-5.6 Terra
```

Review:

```text
GPT-5.6 Sol High
```

Execute:

1. define `IVehicle`;
2. define telemetry snapshot types;
3. define timestamp/freshness fields;
4. implement `MockVehicle`;
5. implement `MavsdkVehicle`;
6. implement connection timeout;
7. implement command timeout;
8. implement command rejection handling;
9. implement stale telemetry handling;
10. implement disconnect handling;
11. implement reconnect handling;
12. connect application to SITL;
13. test no-PX4 case;
14. test delayed connection;
15. test disconnect;
16. test reconnect;
17. test rejected command;
18. test stale telemetry;
19. independent review.

Exit criteria:

```text
mission code does not call MAVSDK directly
SITL communication works
connection/failure cases are tested
review has no unresolved Critical/Important findings
```

---

# 46. PHASE 4 — EARLY RASPBERRY PI DEPLOYMENT

Primary:

```text
Sol + Terra
```

Execute:

1. produce ARM64 runtime image;
2. prepare Pi runtime;
3. create `hardware.yaml`;
4. expose only required devices;
5. deploy exact built image;
6. connect to X7+ with props removed;
7. read heartbeat;
8. read mode;
9. read battery;
10. read estimator state;
11. test FC restart;
12. test application restart;
13. test container restart;
14. test Pi reboot;
15. verify reconnect;
16. verify persistent logs;
17. verify disk usage;
18. keep current runtime image;
19. keep previous known-good image after releases exist;
20. remove obsolete test images.

Exit criteria:

```text
same application runs in SITL and Pi
Pi communicates with real X7+
restarts are safe
logs persist
no source compilation required on Pi
```

---

# 47. PHASE 5 — MISSION / SAFETY CORE

Architecture:

```text
GPT-6 Astra
```

Implementation:

```text
GPT-5.6 Sol
```

Tests:

```text
GPT-5.6 Terra
```

Safety review:

```text
GPT-6 Astra
```

Execute:

1. formalize state graph;
2. formalize transition guards;
3. formalize transition timeouts;
4. formalize recovery behavior;
5. formalize emergency behavior;
6. implement state machine;
7. implement health model;
8. implement safety supervisor;
9. implement stale-state rejection;
10. implement deterministic shutdown;
11. unit-test every state;
12. unit-test every legal transition;
13. unit-test illegal transitions;
14. test timeout transitions;
15. test communication loss;
16. test invalid estimator state;
17. safety review.

Exit criteria:

```text
all state transitions are explicit
all safety inputs are defined
all critical transitions are tested
safety review passes
```

---

# 48. PHASE 6 — MINIMUM AUTONOMOUS MISSION

Primary:

```text
GPT-5.6 Sol
```

Safety review:

```text
GPT-6 Astra
```

Mission:

```text
PREFLIGHT
→ ARM
→ TAKEOFF
→ HOLD
→ LAND
→ DISARM
```

Execute:

1. implement preflight gate;
2. retain PX4 pre-arm checks;
3. implement arm request;
4. implement takeoff;
5. implement altitude/hold criteria;
6. implement hold timeout;
7. implement land request;
8. require landed confirmation;
9. implement disarm completion;
10. run repeated SITL;
11. inject Offboard loss;
12. inject MAVLink loss;
13. inject estimator degradation;
14. kill the application in SITL;
15. verify PX4 response;
16. perform hardware bench validation with props removed;
17. perform safety review;
18. conduct controlled minimal real flight only after all gates pass.

Exit criteria:

```text
nominal SITL passes repeatedly
defined fault behavior passes
hardware bench passes
safety review passes
```

---

# 49. PHASE 7 — FAULT INJECTION

Primary:

```text
Sol + Terra
```

Implement deterministic scenarios for:

```text
MAVLink loss
PX4 restart
Offboard loss
stale telemetry
invalid estimator
invalid local position
range stale
optical flow invalid
sensor disconnect
battery event
command rejection
mission timeout
process crash
invalid configuration
```

Every scenario must define:

```text
initial state
trigger
expected mission transition
expected PX4 behavior
expected log event
pass/fail assertion
```

Exit criteria:

```text
all identified critical faults are automated
all expected responses are explicit
```

---

# 50. PHASE 8 — MTF-01P / GPS-DENIED QUALIFICATION

Primary:

```text
GPT-5.6 Sol
```

Escalation:

```text
GPT-6 Astra
```

Execute:

1. verify MTF-01P firmware/configuration;
2. verify mounting;
3. verify orientation;
4. verify protocol;
5. verify update rate;
6. verify range validity;
7. verify optical-flow quality;
8. confirm PX4 receives valid data;
9. configure approved PX4 estimator parameters;
10. ground-motion test;
11. verify local-position validity;
12. perform controlled hover;
13. vary floor texture;
14. vary lighting;
15. vary altitude within safe limits;
16. analyze logs;
17. document operating envelope;
18. freeze approved estimator parameters.

Exit criteria:

```text
GPS-denied local state is stable within defined envelope
degradation is detectable
approved PX4 estimator configuration is versioned
```

---

# 51. PHASE 9 — NAVIGATION

Primary:

```text
GPT-5.6 Sol
```

Tests:

```text
GPT-5.6 Terra
```

Execute:

1. define `INavigation`;
2. define navigation coordinate frame;
3. define mission bounds;
4. define altitude bounds;
5. define speed limits;
6. define acceleration limits if required;
7. define yaw policy;
8. define waypoint tolerance;
9. define timeout;
10. implement bounded target generation;
11. implement stale-state rejection;
12. implement mock navigation;
13. unit-test constraints;
14. test goal reached;
15. test timeout;
16. test impossible goal;
17. test boundary violation;
18. test estimator degradation;
19. validate in SITL;
20. validate on hardware only after SITL passes.

Exit criteria:

```text
mission logic does not directly generate MAVSDK commands
navigation constraints are tested
SITL navigation passes
```

---

# 52. PHASE 10 — LIDAR / SLAM

Architecture:

```text
GPT-6 Astra
```

Implementation:

```text
GPT-5.6 Sol
```

Execute:

1. define LiDAR interface;
2. integrate Slamtec driver;
3. define timestamp/freshness rules;
4. select mature SLAM package;
5. isolate SLAM in separate process/container;
6. define narrow SLAM output contract;
7. test simulation;
8. test stale SLAM output;
9. test SLAM crash;
10. test SLAM restart;
11. measure CPU;
12. measure memory;
13. measure latency;
14. test real LiDAR mapping;
15. integrate output into navigation only after qualification.

Exit criteria:

```text
SLAM failure cannot terminate safety/mission process
SLAM resource use is bounded
output freshness is enforced
```

---

# 53. PHASE 11 — VISION

Primary:

```text
GPT-5.6 Sol
```

Mechanical/test support:

```text
Terra or Luna
```

Execute:

1. define camera interface;
2. integrate Linux camera device;
3. timestamp frames;
4. implement deterministic preprocessing;
5. load versioned model;
6. implement inference;
7. implement confidence threshold;
8. implement NMS policy;
9. define narrow detection output;
10. measure latency;
11. measure CPU/RAM/GPU;
12. test camera disconnect;
13. test frozen frames;
14. test malformed frames;
15. test inference timeout;
16. test model failure;
17. verify core safety loop remains responsive.

Exit criteria:

```text
vision failure cannot stop flight supervision
model version is fixed
latency is within defined budget
```

---

# 54. PHASE 12 — FULL NIDAR MISSION

Architecture/review:

```text
GPT-6 Astra
```

Implementation:

```text
GPT-5.6 Sol
```

Scenario generation:

```text
GPT-5.6 Terra
```

Execute:

1. map each NIDAR requirement to a mission task;
2. create requirement IDs;
3. create separate mission task modules;
4. avoid monolithic mission implementation;
5. create representative simulation scenarios;
6. run nominal mission;
7. run degraded mission;
8. randomize valid initial conditions;
9. inject sensor failures;
10. inject communication failures;
11. verify mission timing;
12. profile CPU;
13. profile RAM;
14. verify message freshness;
15. run architecture regression review;
16. build ARM64 candidate after accepted flight-affecting changes;
17. progressively validate hardware.

Exit criteria:

```text
all requirements trace to code/tests
full mission passes simulation
degraded cases pass expected behavior
hardware progression follows safety gates
```

---

# 55. PHASE 13 — RELEASE / COMPETITION FREEZE

Final reviewer:

```text
GPT-6 Astra High/XHigh
```

Implementation/release:

```text
GPT-5.6 Sol + Terra
```

Execute:

1. freeze application dependencies;
2. freeze PX4 version;
3. freeze PX4 parameters;
4. freeze sensor configuration;
5. freeze competition configuration;
6. freeze model weights;
7. freeze SLAM configuration;
8. build immutable ARM64 image;
9. record Git commit;
10. record container digest;
11. record all configuration hashes;
12. run full unit suite;
13. run integration suite;
14. run SITL suite;
15. run fault suite;
16. run release disk report;
17. perform final safety review;
18. deploy candidate;
19. perform Pi health check;
20. test rollback;
21. retain previous known-good release;
22. create final release manifest;
23. freeze competition release.

Exit criteria:

```text
release is reproducible
release is identifiable
rollback works
final safety review passes
hardware qualification evidence exists
```

---

# 56. CI POLICY

## Every pull request

Run:

```text
CMake configure
compile
unit tests
clang-format check
clang-tidy
sanitizer-compatible tests
```

## PX4-related change

Add:

```text
SITL startup
vehicle discovery
telemetry
timeout
disconnect/reconnect
```

## Flight-behavior change

Add:

```text
mission SITL
relevant fault injection
independent review
ARM64 package build
```

## Release

Add:

```text
full SITL suite
full fault suite
requirements trace
ARM64 runtime artifact
release manifest
rollback artifact
disk report
```

---

# 57. RELEASE MANIFEST

Create a machine-readable release manifest containing:

```yaml
app_version:
git_commit:
build_timestamp:
compiler:
target_arch: linux/arm64
runtime_image_digest:
px4_version:
px4_git_commit:
px4_parameter_hash:
hardware_config_hash:
competition_config_hash:
sensor_config_hash:
vision_model_hash:
slam_config_hash:
test_run_id:
```

Do not deploy an unidentified release.

---

# 58. PRODUCTION-READY DEFINITION

A feature or release is production-ready only when all applicable requirements are satisfied:

```text
clean build
no unresolved owned-code compiler warnings
unit tests passing
integration tests passing
SITL passing
fault-injection tests passing
no unresolved Critical/Important review findings
configuration validated
timeouts defined
stale-data behavior defined
shutdown tested
reconnect tested
bounded resource use
ARM64 package generated
runtime image minimized
release metadata recorded
logs bounded
rollback available
hardware qualification completed
algorithm source/contract documented
no placeholder production implementation
```

---

# 59. TOKEN-EFFICIENT DEFINITION

The workflow is token-efficient only when:

```text
controller context stays small
workers receive narrow task briefs
long logs stay in files
repository history is not repeatedly summarized
read-only tasks parallelize selectively
write tasks serialize by subsystem
Luna handles mechanical work
Terra handles routine engineering
Sol handles main engineering
Astra handles high-value reasoning only
failed attempts produce new evidence before retry
tests replace repeated prose reasoning
```

Do not classify skipped verification as token efficiency.

---

# 60. FIRST EXECUTION ORDER

Start a new project in this exact order:

```text
Phase 0
→ Phase 1
→ Phase 2
→ Phase 3
→ Phase 4
→ Phase 5
→ Phase 6
→ Phase 7
→ Phase 8
→ Phase 9
→ Phase 10
→ Phase 11
→ Phase 12
→ Phase 13
```

Do not start later phases before earlier exit criteria are satisfied unless a later phase is required to unblock the current phase.

Record every exception in:

```text
docs/PROGRESS.md
```

---

# 61. STOP CONDITIONS

Stop and require human approval before:

```text
deleting named/persistent volumes
destructive disk cleanup
changing flight-controller firmware version after qualification
changing competition-release PX4 parameters
changing frozen sensor configuration
publishing/pushing to external shared repositories when permission is not already established
performing an unsafe hardware test
performing powered flight before required gates pass
```

Stop and report a blocker when:

```text
official documentation contradicts this plan
required hardware is unavailable for the current hardware gate
a safety requirement cannot be satisfied
a task requires an unsupported dependency with no safe isolation strategy
all evidence-based debugging paths are exhausted
```

Do not silently bypass the blocker.

---

# 62. AUTHORITATIVE DOCUMENTATION POLICY

Use current official documentation for version-sensitive implementation decisions.

Prefer:

```text
PX4 official documentation
MAVSDK official documentation
Docker official documentation
OpenAI Codex official documentation
ROS 2 official documentation
library upstream documentation
primary algorithm references
```

Record relevant references and versions in:

```text
docs/REFERENCES.md
```

Do not rely on unsourced blog posts for flight-critical implementation when authoritative sources exist.

---

# 63. FINAL EXECUTION RULE

For every production change, enforce:

```text
requirement
  ↓
small task brief
  ↓
appropriate model
  ↓
implementation
  ↓
fresh verification
  ↓
independent review
  ↓
SITL if flight-affecting
  ↓
ARM64 gate
  ↓
hardware qualification when required
```

Do not generate the entire application in one uncontrolled pass.

Do not permit large unreviewed code generation.

Do not move forward on unverified assumptions.
