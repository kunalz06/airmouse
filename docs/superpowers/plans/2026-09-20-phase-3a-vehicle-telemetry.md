# Phase 3A Vehicle Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Deliver a pinned MAVSDK C++ vehicle adapter that discovers PX4 X500 SITL, exposes fresh telemetry, and never transmits active flight commands.

**Architecture:** MAVSDK-free \`IVehicle\` contracts and deterministic \`MockVehicle\` are public. \`MavsdkVehicle\` is the only MAVSDK implementation and owns all SDK objects/handles through RAII. The application connects to X500 SITL only at loopback UDP 14540.

**Tech Stack:** C++20, CMake/Ninja, GoogleTest, MAVSDK v3.17.2, Docker Ubuntu 24.04, PX4 v1.17.0 X500 SITL, Bash.

**Spec:** \`docs/superpowers/specs/2026-09-20-phase-3a-vehicle-telemetry-design.md\`

## Global Constraints

- Pin \`libmavsdk-dev_3.17.2_ubuntu24.04_amd64.deb\` SHA-256 \`9a8c0e960b6cda8f1b09d522a3fd7ea214808ebca922c7ad482d1194243f8cc5\` from MAVSDK v3.17.2.
- Install/use MAVSDK only in pinned Ubuntu 24.04 amd64 development; defer arm64 packaging to Phase 4.
- Use \`ComponentType::CompanionComputer\` and \`ForwardingOption::ForwardingOff\`.
- Keep MAVSDK headers only in \`src/vehicle/\` implementation; public interfaces expose no MAVSDK/MAVLink types.
- Select only a connected PX4 system: \`has_autopilot()\` and \`autopilot_type() == mavsdk::Autopilot::Px4\`.
- Use \`steady_clock\`, field-level validity, and per-field last-update times.
- Do not instantiate Action, Offboard, Mission, or Param; active commands return \`RejectedByPhasePolicy\`.
- Use \`udpin://127.0.0.1:14540\`; preserve QGroundControl 14550 and passive smoke 14560.
- All deadlines are bounded. No busy loops, sleep polling, global mutable state, or destructive Docker cleanup.

## Review Focus

- Bound-but-silent UDP returns \`DiscoveryTimeout\`, not transport failure (Task 3).
- Battery updates do not refresh armed/mode timestamps (Task 2).
- Teardown during telemetry cannot create use-after-free, deadlock, or duplicate subscriptions (Task 3).
- Occupied 14540 fails before startup and preserves Phase 2 endpoints (Task 5).
- MAVSDK outside the adapter or active-command plugins fail source-boundary validation (Task 5).

---

### Task 1: Pin MAVSDK and create the vehicle build target

**Files:** Modify \`docker/dev/Dockerfile\`, \`docker/runtime/Dockerfile\`, \`config/versions.lock\`, \`CMakeLists.txt\`; create \`tests/integration/test_mavsdk_dependency.sh\`.

**Interfaces:** Produces \`nidar_vehicle\` linked \`PRIVATE MAVSDK::mavsdk\`; runtime remains MAVSDK-free in Phase 3A.

- [ ] **Step 1: Write the failing dependency test**

~~~bash
docker run --rm nidar-dev bash -lc 'dpkg-query -W -f="$Version" libmavsdk-dev | grep -Fx 3.17.2'
~~~

- [ ] **Step 2: Run it to verify it fails**

Run: \`tests/integration/test_mavsdk_dependency.sh\`

Expected: nonzero because \`nidar-dev\` lacks \`libmavsdk-dev\`.

- [ ] **Step 3: Add checksum-verified package download and CMake wiring**

~~~dockerfile
RUN curl --fail --location --retry 3 -o /tmp/mavsdk.deb https://github.com/mavlink/MAVSDK/releases/download/v3.17.2/libmavsdk-dev_3.17.2_ubuntu24.04_amd64.deb \
 && echo '9a8c0e960b6cda8f1b09d522a3fd7ea214808ebca922c7ad482d1194243f8cc5  /tmp/mavsdk.deb' | sha256sum --check --strict \
 && apt-get update && apt-get install -y --no-install-recommends /tmp/mavsdk.deb && rm -rf /var/lib/apt/lists/* /tmp/mavsdk.deb
~~~

~~~cmake
find_package(MAVSDK 3.17.2 REQUIRED)
add_library(nidar_vehicle src/vehicle/mock_vehicle.cpp src/vehicle/mavsdk_vehicle.cpp)
target_include_directories(nidar_vehicle PUBLIC include)
target_link_libraries(nidar_vehicle PRIVATE MAVSDK::mavsdk)
~~~

Record asset URL, checksum, version, amd64 architecture, and verification date in \`config/versions.lock\`; retain a runtime-Dockerfile comment that MAVSDK packaging begins in Phase 4.

- [ ] **Step 4: Rebuild and verify**

Run: \`docker build -t nidar-dev -f docker/dev/Dockerfile . && tests/integration/test_mavsdk_dependency.sh && ./scripts/configure.sh\`

Expected: checksum verified, package version 3.17.2, and CMake finds MAVSDK.

- [ ] **Step 5: Commit**

~~~bash
git add docker/dev/Dockerfile docker/runtime/Dockerfile config/versions.lock CMakeLists.txt tests/integration/test_mavsdk_dependency.sh
git commit -m "build: pin MAVSDK vehicle dependency"
~~~

### Task 2: Define vehicle contracts and deterministic mock behavior

**Files:** Create \`include/nidar/vehicle/vehicle_types.hpp\`, \`include/nidar/vehicle/ivehicle.hpp\`, \`include/nidar/vehicle/mock_vehicle.hpp\`, \`src/vehicle/mock_vehicle.cpp\`, \`tests/unit/vehicle_types_test.cpp\`, \`tests/unit/mock_vehicle_test.cpp\`; modify \`CMakeLists.txt\`.

**Interfaces:** \`TelemetryField<T>{value, validity, last_update}\`; immutable \`TelemetrySnapshot\`; \`IVehicle::connect\`, \`disconnect\`, \`connection_status\`, \`telemetry_snapshot\`, and Phase 3B command entry points; deterministic mock publication/lifecycle controls.

- [ ] **Step 1: Write the failing contract tests**

~~~cpp
TEST(TelemetrySnapshot, BatteryDoesNotRefreshArmed) {
  MockVehicle vehicle;
  vehicle.publish_armed(true, SteadyTimePoint{} + 1s);
  vehicle.publish_battery(BatteryState{.voltage_volts = 15.2F}, SteadyTimePoint{} + 2s);
  EXPECT_EQ(vehicle.telemetry_snapshot().armed.last_update, SteadyTimePoint{} + 1s);
}
TEST(MockVehicle, RejectsActiveCommands) {
  EXPECT_EQ(MockVehicle{}.arm(), VehicleCommandResult::RejectedByPhasePolicy);
}
~~~

- [ ] **Step 2: Run it to verify failure**

Run: \`./scripts/configure.sh && ./scripts/build.sh\`

Expected: compile failure because contracts do not exist.

- [ ] **Step 3: Implement minimal types and mock**

~~~cpp
template <typename T> struct TelemetryField {
  T value{}; TelemetryValidity validity{TelemetryValidity::Unavailable}; SteadyTimePoint last_update{};
};
struct TelemetrySnapshot {
  SteadyTimePoint assembled_at{}; TelemetryField<bool> armed{};
  TelemetryField<FlightMode> flight_mode{}; TelemetryField<BatteryState> battery{};
};
~~~

Update exactly one field per publication; invalidate every field on disconnect; make disconnect idempotent; return typed results and \`RejectedByPhasePolicy\` for every active command.

- [ ] **Step 4: Run focused tests**

Run: \`./scripts/configure.sh && ./scripts/build.sh && ctest --test-dir build/dev --output-on-failure -R '(VehicleTypes|MockVehicle)'\`

Expected: state, no-PX4, delayed connection, disconnect/reconnect, stale/unavailable field, and repeated lifecycle tests pass.

- [ ] **Step 5: Commit**

~~~bash
git add include/nidar/vehicle src/vehicle/mock_vehicle.cpp tests/unit/vehicle_types_test.cpp tests/unit/mock_vehicle_test.cpp CMakeLists.txt
git commit -m "feat: add vehicle contracts and deterministic mock"
~~~

### Task 3: Implement RAII MAVSDK discovery and telemetry

**Files:** Create \`include/nidar/vehicle/mavsdk_vehicle.hpp\`, \`src/vehicle/mavsdk_vehicle.cpp\`, \`tests/unit/mavsdk_vehicle_test.cpp\`; modify \`CMakeLists.txt\`, \`CMakePresets.json\`.

**Interfaces:** \`MavsdkVehicle final : public IVehicle\`; \`connect()\` returns \`TransportFailure\`, \`DiscoveryTimeout\`, or \`Connected\`; \`disconnect()\` removes exactly its owned connection and leaves \`Disconnected\`.

- [ ] **Step 1: Write failing adapter tests**

~~~cpp
TEST(MavsdkVehicle, EmptyListenerIsDiscoveryTimeout) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:14540", 50ms), VehicleConnectionResult::DiscoveryTimeout);
}
TEST(MavsdkVehicle, DisconnectInvalidatesAllFields) {
  auto vehicle = ConnectedVehicleForTest{};
  vehicle.disconnect();
  EXPECT_EQ(vehicle.telemetry_snapshot().battery.validity, TelemetryValidity::Unavailable);
}
~~~

- [ ] **Step 2: Run to verify failure**

Run: \`./scripts/configure.sh && ./scripts/build.sh\`

Expected: compile failure because \`MavsdkVehicle\` is absent.

- [ ] **Step 3: Implement configuration, filtering, callbacks, and teardown**

~~~cpp
auto configuration = mavsdk::Mavsdk::Configuration{mavsdk::ComponentType::CompanionComputer};
mavsdk_ = std::make_unique<mavsdk::Mavsdk>(configuration);
const auto [result, handle] = mavsdk_->add_any_connection_with_handle(endpoint, mavsdk::ForwardingOption::ForwardingOff);
~~~

Select only \`system->has_autopilot() && system->is_connected() && system->autopilot_type() == mavsdk::Autopilot::Px4\`. Subscribe only to armed, flight mode, and battery. Under a short mutex update the matching field/time. On teardown mark callback state inactive, unsubscribe telemetry/system callbacks, remove \`handle\`, reset plugin/system, then destroy MAVSDK. Do not call SDK methods or wait while holding the mutex.

- [ ] **Step 4: Verify tests and sanitizers**

Run: \`./scripts/configure.sh && ./scripts/build.sh && ctest --test-dir build/dev --output-on-failure -R MavsdkVehicle\`

Then configure ASan/UBSan and run repeated connect/disconnect while telemetry callbacks are active.

Expected: transport/discovery distinctions, PX4 filtering, per-field freshness, callback teardown, and command rejection pass without sanitizer findings; record any unavailable sanitizer and strongest replacement test.

- [ ] **Step 5: Commit**

~~~bash
git add include/nidar/vehicle/mavsdk_vehicle.hpp src/vehicle/mavsdk_vehicle.cpp tests/unit/mavsdk_vehicle_test.cpp CMakeLists.txt CMakePresets.json
git commit -m "feat: add MAVSDK telemetry vehicle adapter"
~~~

### Task 4: Add bounded simulation-mode application behavior

**Files:** Modify \`apps/nidar-flight/main.cpp\`, \`CMakeLists.txt\`; create \`tests/integration/test_nidar_flight_cli.sh\`.

**Interfaces:** \`nidar-flight --sim --endpoint udpin://127.0.0.1:14540 --discovery-timeout-ms 15000 --telemetry-max-age-ms 1000\`; exit zero only for discovered PX4 plus fresh fields; always disconnect.

- [ ] **Step 1: Write the failing CLI test**

~~~bash
if build/dev/nidar-flight --sim --endpoint not-a-url --discovery-timeout-ms 10; then exit 1; fi
build/dev/nidar-flight --help | grep -Fx -- '--sim'
~~~

- [ ] **Step 2: Run to verify failure**

Run: \`tests/integration/test_nidar_flight_cli.sh\`

Expected: failure because the application has no CLI.

- [ ] **Step 3: Implement strict input validation and safe diagnostics**

~~~cpp
struct SimulationOptions {
  std::string endpoint;
  std::chrono::milliseconds discovery_timeout;
  std::chrono::milliseconds telemetry_max_age;
};
~~~

Require positive millisecond values. Print MAVSDK version, \`CompanionComputer\`, selected PX4 system ID, and validated field ages only after success. Reject malformed, stale, and unavailable states; never call an active command.

- [ ] **Step 4: Run CLI verification**

Run: \`./scripts/configure.sh && ./scripts/build.sh && tests/integration/test_nidar_flight_cli.sh\`

Expected: malformed input fails fast and help output is stable.

- [ ] **Step 5: Commit**

~~~bash
git add apps/nidar-flight/main.cpp tests/integration/test_nidar_flight_cli.sh CMakeLists.txt
git commit -m "feat: add bounded SITL telemetry application mode"
~~~

### Task 5: Enforce source boundary and verify X500 SITL

**Files:** Create \`tests/integration/test_mavsdk_boundary.sh\`, \`tests/sitl/test_vehicle_sitl.sh\`, \`scripts/sitl-vehicle.sh\`; modify \`.github/workflows/build-test.yml\`, \`docs/SIMULATION.md\`.

**Interfaces:** Source test permits MAVSDK only in \`src/vehicle/\` and rejects Action/Offboard/Mission/Param. \`sitl-vehicle.sh\` owns only its named Phase 3A containers and checks 14540 before start.

- [ ] **Step 1: Write failing boundary/port tests**

~~~bash
rg -n '#include <mavsdk/' --glob '!src/vehicle/**' apps include src && exit 1 || true
rg -n 'mavsdk/(action|offboard|mission|param)' apps include src && exit 1 || true
~~~

Hold UDP 14540 in a background Python socket, invoke \`scripts/sitl-vehicle.sh\`, and assert nonzero with a clear ownership error and no Phase 2 container replacement.

- [ ] **Step 2: Run to verify failure**

Run: \`tests/integration/test_mavsdk_boundary.sh && tests/sitl/test_vehicle_sitl.sh --occupied-port\`

Expected: launcher is absent and the test fails.

- [ ] **Step 3: Implement lifecycle-safe SITL launcher**

~~~bash
docker run --name nidar-sitl-vehicle --network host --init -v "$project_root:/workspace:ro" -w /workspace nidar-dev build/dev/nidar-flight --sim --endpoint udpin://127.0.0.1:14540 --discovery-timeout-ms 30000 --telemetry-max-age-ms 1000
~~~

Start the existing X500 image in a unique container, record logs under ignored \`simulation/output/phase-3a/\`, use a finite deadline, and trap-remove only names created here. Add bounded CI after the Phase 2 image build. Do not alter Phase 2 ports, GUI behavior, or passive smoke behavior.

- [ ] **Step 4: Run local SITL verification**

Run: \`tests/integration/test_mavsdk_boundary.sh && tests/sitl/test_vehicle_sitl.sh --occupied-port && NIDAR_SITL_TIMEOUT_SECONDS=90 scripts/sitl-vehicle.sh\`

Expected: boundary passes, occupied port fails safely, X500 discovery/fresh telemetry pass, and no Phase 3A container remains.

- [ ] **Step 5: Commit**

~~~bash
git add tests/integration/test_mavsdk_boundary.sh tests/sitl/test_vehicle_sitl.sh scripts/sitl-vehicle.sh .github/workflows/build-test.yml docs/SIMULATION.md
git commit -m "test: verify Phase 3A vehicle SITL boundary"
~~~

### Task 6: Record evidence, independent review, and closeout

**Files:** Modify \`docs/REFERENCES.md\`, \`docs/PROGRESS.md\`, \`docs/TASKS.md\`; create \`docs/test-results/phase-3a-mavsdk-build.txt\`, \`docs/test-results/phase-3a-vehicle-sitl.txt\`, \`docs/test-results/phase-3a-sanitizers.txt\`, \`docs/test-results/phase-3a-independent-review.md\`, \`docs/PHASE_3A_UPDATE.md\`.

**Interfaces:** Records only verified Phase 3A evidence; leaves Phase 3B not started and separately gated.

- [ ] **Step 1: Write the empty closeout checklist**

~~~markdown
- [ ] pin/checksum and runtime version recorded
- [ ] unit, integration, SITL, and sanitizer outputs recorded
- [ ] identity, PX4 selection, freshness, and no-command boundary verified
- [ ] review has no unresolved Critical/Important finding
~~~

- [ ] **Step 2: Prove evidence does not pre-exist**

Run: \`test ! -e docs/test-results/phase-3a-vehicle-sitl.txt\`

Expected: zero before verification runs.

- [ ] **Step 3: Run evidence commands and review final diff**

~~~bash
./scripts/configure.sh && ./scripts/build.sh && ./scripts/test.sh
tests/integration/test_mavsdk_dependency.sh
tests/integration/test_mavsdk_boundary.sh
NIDAR_SITL_TIMEOUT_SECONDS=90 scripts/sitl-vehicle.sh
scripts/docker-disk-report.sh
git diff --check
~~~

Record commands, exit codes, failure counts, endpoint, image/package identities, cleanup result, disk report, and sanitizer outcome. Independently review the diff against the spec; resolve or adjudicate every Critical/Important finding before ledger updates.

- [ ] **Step 4: Update documents and re-run final gate**

Run: \`./scripts/configure.sh && ./scripts/build.sh && ./scripts/test.sh && tests/integration/test_mavsdk_boundary.sh && git diff --check\`

Expected: fresh evidence supports every checked Phase 3A criterion; Phase 3B remains gated on its own approved design and plan.

- [ ] **Step 5: Commit**

~~~bash
git add docs/REFERENCES.md docs/PROGRESS.md docs/TASKS.md docs/test-results/phase-3a-* docs/PHASE_3A_UPDATE.md
git commit -m "docs: record Phase 3A vehicle telemetry verification"
~~~
