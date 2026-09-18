# NIDAR Phase 0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish `/home/kunal/Desktop/airmouse` as the NIDAR repository with the required host tooling, governed documentation, agent configuration, and Docker disk controls.

**Architecture:** Ubuntu 26.04 remains a lean host. Future C++ and PX4 development stays in pinned Ubuntu 24.04 containers. Phase 0 creates no PX4 checkout, Docker image, flight logic, simulator, or ROS 2 process.

**Tech Stack:** Ubuntu 26.04, Git, Git LFS, Docker Engine CE, Buildx, Compose, QGroundControl x86_64 AppImage, Bash, TOML, YAML, Markdown.

**Spec:** `/home/kunal/Desktop/airmouse/CODEX_MASTER_PLAN_NIDAR.md` (Sections 2–9, 22–25, 30–35, and 42)

## Global Constraints

- The repository root is `/home/kunal/Desktop/airmouse`.
- Use C++20/CMake/Ninja only in Ubuntu 24.04 containers; do not install the PX4 development toolchain on Ubuntu 26.04.
- Use Docker Engine CE instead of Snap Docker or Docker Desktop.
- Install QGroundControl as the official x86_64 AppImage with its documented Ubuntu dependencies.
- Preserve and add the active user to `docker`, `dialout`, `video`, and `render` groups.
- Use initial soft limits: BuildKit <= 10 GB; ccache <= 5 GB; Docker total <= 30 GB; free disk >= 25 GB.
- Never run `docker system prune -a --volumes` or delete named volumes automatically.
- Do not select or fetch PX4, Gazebo, MAVSDK, ROS 2, or application dependencies in Phase 0.

---

## File Structure

- `AGENTS.md`: recurring project-critical worker rules.
- `.codex/config.toml` and `.codex/agents/*.toml`: conservative role routing.
- `docs/*.md`: master plan, contracts, safety/verification policy, configuration, and progress ledger.
- `config/versions.lock`: observed Phase-0 versions and future dependency selection policy.
- `.gitignore` / `.dockerignore`: generated data and Docker-image exclusions.
- `scripts/docker-disk-report.sh`: read-only capacity report.
- `scripts/docker-gc.sh`: bounded cleanup excluding named volumes.

### Task 1: Capture the host baseline and install Phase-0 host tools

**Files:**
- Create: `docs/test-results/phase-0-host-baseline.txt`
- Create: `docs/test-results/phase-0-host-install.txt`
- Modify: `docs/CONFIGURATION.md`

**Interfaces:**
- Consumes: `/etc/os-release`, disk/group/package state, and official Docker/QGroundControl guides.
- Produces: evidence for host version, architecture, disk, groups, tooling, Docker health, and QGroundControl location.

- [ ] **Step 1: Capture the baseline before changing packages**

```bash
mkdir -p docs/test-results
{
  date --iso-8601=seconds
  uname -m
  . /etc/os-release && printf '%s %s\n' "$PRETTY_NAME" "$VERSION_ID"
  df -h /
  getent group docker dialout video render
  id -nG
  snap list docker 2>/dev/null || true
  dpkg-query -W -f='${Package} ${Version}\n' docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>/dev/null || true
} | tee docs/test-results/phase-0-host-baseline.txt
```

Expected: Ubuntu 26.04, x86_64, all required groups, and at least 25 GB free space are recorded.

- [ ] **Step 2: Replace only confirmed conflicting Docker packages and Snap Docker**

```bash
sudo apt-get remove -y docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc || true
sudo snap remove docker
```

Expected: no conflicting Docker implementation remains. Do not remove Docker data, images, volumes, or networks.

- [ ] **Step 3: Install the required apt tools and Docker Engine CE**

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git git-lfs wget openssh-client rsync xauth usbutils pciutils jq yq tmux htop iotop strace lsof tree
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker,dialout,video,render "$(id -un)"
git lfs install
```

Expected: official Docker packages install; a new login is required before group access is refreshed.

- [ ] **Step 4: Install QGroundControl runtime requirements and its official AppImage**

```bash
sudo apt-get install -y libfuse2 libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor0
sudo install -d -m 0755 /opt/qgroundcontrol
sudo install -m 0755 <downloaded-QGroundControl-x86_64.AppImage> /opt/qgroundcontrol/QGroundControl.AppImage
/opt/qgroundcontrol/QGroundControl.AppImage --help
```

Expected: AppImage exists at `/opt/qgroundcontrol/QGroundControl.AppImage`; its release URL/version is recorded in configuration documentation.

- [ ] **Step 5: Verify and record installations**

```bash
{
  git --version
  git lfs --version
  docker version
  docker buildx version
  docker compose version
  docker run --rm hello-world
  test -x /opt/qgroundcontrol/QGroundControl.AppImage
} 2>&1 | tee docs/test-results/phase-0-host-install.txt
```

Expected: every command exits 0.

### Task 2: Initialize Git and create the mandated project skeleton

**Files:**
- Create: all directories and root files in master-plan Section 7.
- Create: `README.md`, `LICENSE`, `CMakeLists.txt`, `CMakePresets.json`, `.gitignore`, `.dockerignore`.

**Interfaces:**
- Consumes: master-plan Section 7.
- Produces: an initialized repository with tracked empty mandated directories.

- [ ] **Step 1: Initialize the repository**

```bash
git init
git branch -M main
git status --short
```

Expected: Git status succeeds on branch `main`.

- [ ] **Step 2: Create every required directory**

Create `.codex/agents`, `apps/nidar-flight`, `include/nidar`, every required `src`, `tests`, `simulation`, `docker`, `deployment`, `scripts`, `docs`, and `.github/workflows` directory from Section 7. Put `.gitkeep` in a directory only if it otherwise has no Phase-0 file.

- [ ] **Step 3: Add root control files**

Create an Apache-2.0 license and README that explains PX4 owns stabilization while the Pi owns high-level orchestration. Create a minimal CMake project with C++20 only and a Ninja `dev` preset. Do not add builds, dependencies, flight logic, PX4, or MAVSDK.

- [ ] **Step 4: Add exclusion files**

Put all Section 32 minimum patterns in `.dockerignore`. Put generated builds, caches, logs, datasets, recordings, secrets, and generated PX4 outputs in `.gitignore`, while keeping source, configuration, scripts, and lock files tracked.

### Task 3: Create governance documents, agent routing, and version lock

**Files:**
- Create: `AGENTS.md`, `.codex/config.toml`, `.codex/agents/{architect,explorer,implementer,test-engineer,reviewer,safety-reviewer,debugger,mechanical-worker}.toml`, `config/versions.lock`.
- Create: `docs/MASTER_PLAN.md`, `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`, `docs/SAFETY.md`, `docs/TESTING.md`, `docs/DEPLOYMENT.md`, `docs/CONFIGURATION.md`, `docs/ALGORITHMS.md`, `docs/REFERENCES.md`, `docs/PROGRESS.md`.

**Interfaces:**
- Consumes: master-plan Sections 6, 10–25, and the host evidence from Task 1.
- Produces: repository contracts and agent restrictions before application code exists.

- [ ] **Step 1: Copy the plan and prove synchronization**

```bash
cp CODEX_MASTER_PLAN_NIDAR.md docs/MASTER_PLAN.md
cmp -s CODEX_MASTER_PLAN_NIDAR.md docs/MASTER_PLAN.md
```

Expected: `cmp` exits 0.

- [ ] **Step 2: Write concise contract documents**

Document the master plan’s fixed baseline, PX4/Pi safety ownership, MAVSDK adapter restriction, future interface names, explicit time/frame/config validation rules, test strategy, Docker/deployment policy, algorithm contract rule, and reference policy. Do not claim an unimplemented interface works.

- [ ] **Step 3: Record configuration and ledger**

In `docs/CONFIGURATION.md`, capture 468 GB capacity, 408 GB free baseline, all four disk budgets, Docker apt source, QGroundControl path/version, and fresh-login requirement. Initialize `docs/PROGRESS.md` with Phase 0, evidence paths, rulings, findings, blockers, failed approaches, and next task.

- [ ] **Step 4: Configure agent routing**

Set `.codex/config.toml` exactly to:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 4
default_subagent_model = "gpt-5.6-terra"
default_subagent_reasoning_effort = "medium"
```

Give every role its master-plan model, reasoning effort, sandbox, and concise constraints. Architect/safety-reviewer/explorer/reviewer must be read-only.

- [ ] **Step 5: Lock the initial versions**

Record observed host versions and architecture in `config/versions.lock`. List PX4, Gazebo, MAVSDK, yaml-cpp, spdlog, and GoogleTest as `not-selected`; later selections must record source URL, version/commit, architecture, and verification date.

- [ ] **Step 6: Validate all documents and TOML**

```bash
cmp -s CODEX_MASTER_PLAN_NIDAR.md docs/MASTER_PLAN.md
for path in docs/REQUIREMENTS.md docs/ARCHITECTURE.md docs/INTERFACES.md docs/SAFETY.md docs/TESTING.md docs/DEPLOYMENT.md docs/CONFIGURATION.md docs/ALGORITHMS.md docs/REFERENCES.md docs/PROGRESS.md; do test -s "$path" || exit 1; done
python3 - <<'PY'
import pathlib, tomllib
for path in pathlib.Path('.codex').rglob('*.toml'):
    with path.open('rb') as handle:
        tomllib.load(handle)
PY
```

Expected: all checks exit 0.

### Task 4: Add and verify Docker disk-control scripts

**Files:**
- Create: `scripts/docker-disk-report.sh`, `scripts/docker-gc.sh`.
- Create: `docs/test-results/phase-0-disk-report.txt`, `docs/test-results/phase-0-structure.txt`.
- Modify: `docs/PROGRESS.md`.

**Interfaces:**
- Consumes: Docker, Buildx, filesystem capacity, and documented disk limits.
- Produces: safe report/cleanup mechanisms and acceptance evidence.

- [ ] **Step 1: Create the report script**

Use Bash `set -eu` and exactly these reporting commands:

```bash
docker system df -v
docker buildx du
df -h /
du -sh build* .cache .ccache 2>/dev/null || true
```

- [ ] **Step 2: Create the cleanup script**

Use Bash `set -eu`, print a warning that named volumes are never removed, and run only:

```bash
docker buildx prune --filter "until=168h" --max-used-space 10gb -f
docker container prune --filter "until=72h" -f
docker image prune -f
```

No `docker system prune`, `--volumes`, `image prune -a`, or filesystem removal command may appear.

- [ ] **Step 3: Run syntax and policy checks**

```bash
chmod 0755 scripts/docker-disk-report.sh scripts/docker-gc.sh
bash -n scripts/docker-disk-report.sh scripts/docker-gc.sh
shellcheck scripts/docker-disk-report.sh scripts/docker-gc.sh
! rg -n 'system prune|--volumes|image prune -a|rm -rf' scripts/docker-gc.sh
scripts/docker-disk-report.sh | tee docs/test-results/phase-0-disk-report.txt
```

Expected: every command exits 0.

### Task 5: Review Phase 0, preserve evidence, and commit

**Files:**
- Create: `docs/test-results/phase-0-architecture-review.md`.
- Modify: `docs/PROGRESS.md`.

**Interfaces:**
- Consumes: all Phase-0 artifacts and evidence.
- Produces: classified architecture review and exit-criteria decision.

- [ ] **Step 1: Verify the structural exit criteria**

```bash
for path in AGENTS.md README.md CMakeLists.txt CMakePresets.json LICENSE .gitignore .dockerignore .codex/config.toml config/versions.lock docs/MASTER_PLAN.md docs/PROGRESS.md scripts/docker-disk-report.sh scripts/docker-gc.sh; do test -e "$path" || { echo "missing: $path"; exit 1; }; done | tee docs/test-results/phase-0-structure.txt
git diff --check
```

- [ ] **Step 2: Conduct the architecture review**

Write the review with `Scope reviewed`, `Evidence inspected`, `Critical`, `Important`, `Minor`, and `Decision`. Check that PX4/Pi ownership, MAVSDK isolation, 24.04-container policy, disk policy, agent configuration, and master-plan synchronization match the master plan. State `none` for empty finding classes.

- [ ] **Step 3: Resolve Critical/Important findings and rerun checks**

Make only narrow fixes; record each finding’s resolution or explicit adjudication in the review and ledger. Re-run the affected command from Tasks 3–5.

- [ ] **Step 4: Record acceptance and commit the foundation**

```bash
git add -A
git commit -m "chore: establish NIDAR Phase 0 foundation"
git status --short
```

Expected: clean tree; ledger links host, disk, structure, and architecture-review evidence. Do not begin Phase 1.

## Plan Self-Review

- **Coverage:** Tasks 1–5 cover every Phase-0 action and exit criterion, including the explicit QGroundControl installation request.
- **Deferred scope:** Dockerfiles, C++ code/test, PX4, Gazebo, MAVSDK, CI, and runtime images remain Phase 1+.
- **Safety:** Docker data/volumes are preserved, cleanup is bounded, and no task controls a vehicle.
- **Consistency:** Task 1 evidence feeds Task 3; Tasks 2–4 create artifacts reviewed in Task 5.
