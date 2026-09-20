# Phase 3A Vehicle Telemetry Design

## Purpose

Establish NIDAR's first production vehicle boundary: a C++20 MAVSDK adapter
that can discover the PX4 X500 SITL vehicle, publish bounded and fresh
telemetry, and fail safely under connection and telemetry faults. Phase 3A
does not allow NIDAR to send an active flight command to PX4.

## Scope and safety boundary

PX4 remains the sole owner of stabilization, EKF/state estimation, arming and
pre-arm checks, flight-mode management, Offboard-loss response, and all
low-level flight control. NIDAR uses MAVSDK only behind the vehicle adapter;
mission or future navigation code must never include or call MAVSDK.

Phase 3A delivers these capabilities:

- bounded connection, disconnection, discovery, and explicit reconnection;
- connection status and immutable telemetry snapshots;
- typed telemetry freshness and validity reporting;
- deterministic handling of unavailable PX4, delayed discovery, disconnect,
  reconnect, and stale telemetry;
- typed, locally enforced rejection of active vehicle commands.

The following are deliberately deferred to Phase 3B: forwarding arm, disarm,
takeoff, land, hold, Offboard start/stop, position targets, and velocity
targets through MAVSDK; their PX4 acceptance/rejection behavior; and every
flight-affecting SITL test. Phase 3A must not arm, change flight mode, upload
a mission, write parameters, request a command acknowledgement, or transmit a
setpoint to PX4.

Phase 3A may emit the normal MAVSDK/MAVLink protocol traffic required for
connection, discovery, and companion-computer identification, but it must not
instantiate or use MAVSDK command plugins such as Action, Offboard, Mission,
or Param for active vehicle control.

## Selected dependency and build boundary

Phase 3A pins MAVSDK C++ release `v3.17.2` from the upstream release assets.
The Ubuntu 24.04 amd64 development image installs the exact release package
with its published SHA-256, then CMake locates it with `find_package(MAVSDK
REQUIRED)`. The pin, source URL, asset name, SHA-256, architecture, and
verification date are recorded in `config/versions.lock`.

This phase builds and executes the adapter inside the existing pinned Ubuntu
24.04 development container. Raspberry Pi linux/arm64 dependency packaging
belongs to Phase 4, so Phase 3A does not select an unverified arm64 Ubuntu
artifact or expand the runtime image.

The MAVSDK instance must be constructed with an explicit
`ComponentType::CompanionComputer` configuration. It must not identify the
NIDAR process as a ground station. MAVLink forwarding remains disabled unless
a later approved design explicitly requires it.

## Interfaces and data model

`include/nidar/vehicle/vehicle_types.hpp` owns value types only. It defines
strong enums for connection state, flight mode, vehicle-command result, and
telemetry validity; all monotonic freshness timestamps use
`std::chrono::steady_clock`. `TelemetrySnapshot` is immutable after
construction and records snapshot assembly time, armed state, flight mode,
battery data, field-level validity, and a field-level last-update time for
each independently updated telemetry value. A single snapshot timestamp must
not make all fields appear fresh: a newly updated field must not refresh an
unrelated field. No field without valid field-level status and acceptable
field-level age is interpreted as current vehicle state.

`include/nidar/vehicle/ivehicle.hpp` is the stable dependency boundary. Its
Phase 3A operations are `connect`, `disconnect`, `connection_status`,
`telemetry_snapshot`, and the command-shaped methods needed to prove the
temporary safety policy. Each operation uses a typed result rather than
exceptions for expected transport or PX4 failures. Timeouts are explicit
`std::chrono` arguments; neither interface nor callers use magic delays.
The interface must not expose MAVSDK/MAVLink types, MAVSDK plugin handles, or
SDK-specific callback types.

`MockVehicle` is a deterministic test implementation with no MAVSDK
dependency. Tests configure its discovery delay, connection state, per-field
telemetry update times, command result, and disconnect/reconnect events. It
has no background busy loop and uses bounded state kept under test control.

`MavsdkVehicle` is the sole MAVSDK-specific implementation in
`src/vehicle/`. It owns its MAVSDK connection handle, selected PX4 system,
Telemetry plugin, connection-state subscriptions, telemetry subscriptions, and
subscription handles through deterministic lifetime management. It maps MAVSDK
outcomes to NIDAR types and publishes a synchronized immutable snapshot. No
other production source directory may include MAVSDK headers. An automated
source-boundary test enforces that rule.

## MAVSDK identity and system selection

The adapter explicitly configures MAVSDK as a companion computer and discovers
an autopilot system rather than accepting the first arbitrary MAVLink system.
For the Phase 3A PX4 SITL baseline, success requires a MAVSDK `System` with an
autopilot component, still connected when accepted, and identified as PX4.
An arbitrary MAVLink system or non-PX4 autopilot cannot satisfy Phase 3A PX4
discovery. The selected identity remains stable for one connection; an
explicit reconnect discovers a new system rather than reusing stale state.

## Lifecycle and failure semantics

`connect(url, discovery_timeout)` first validates and adds the configured
MAVSDK transport, retaining its removable connection handle, then waits only
until the supplied deadline for PX4-autopilot discovery. A malformed URL or a
transport that cannot be created/bound returns a typed transport failure
immediately. A valid UDP listener that binds successfully but receives no
qualifying PX4 autopilot before the deadline returns a typed discovery timeout,
not a transport-open failure.

On MAVSDK disconnect, the adapter enters `Disconnected`, invalidates every
telemetry field, and resolves pending connection work with a typed failure.
It does not silently retry. A caller explicitly invokes a new bounded
`connect()` to reconnect. `disconnect()` is idempotent. Before returning it
prevents new callback publication into adapter state, unsubscribes each owned
MAVSDK/System/Telemetry subscription, removes its owned connection handle,
invalidates telemetry, releases selected system/plugin state, and leaves a
deterministic `Disconnected` state. No callback may capture an object that can
end before the callback is made safe.

The adapter does not hold its mutex while invoking blocking SDK operations,
waiting for discovery, invoking user callbacks, or tearing down an SDK object
that can synchronously trigger a callback. Its documented locking/state
serialization prevents deadlock and use-after-free. Repeated `connect()` /
`disconnect()` cycles cannot accumulate subscriptions, telemetry updates,
connection handles, threads, or resources.

Telemetry freshness is calculated from every field's last-update time and the
caller-provided maximum age. Missing data and data older than that limit are
reported as unavailable/stale, never returned as usable state. The adapter
uses no global mutable state, unbounded queue, sleep-polling loop, implicit
unit conversion, or swallowed callback error.

Every active-command method in Phase 3A returns
`VehicleCommandResult::RejectedByPhasePolicy` before calling MAVSDK. This is a
complete and intentional local policy, not a fake success or a deferred
implementation: it prevents command traffic from reaching PX4 until Phase 3B
has separately designed, implemented, SITL-tested, and reviewed each command
path.

An automated source-level boundary check verifies that active-command MAVSDK
plugins are not used by Phase 3A production adapter code.

## SITL topology and application usage

Phase 3A reuses the Phase 2 PX4 X500 container and its upstream onboard
MAVLink link. The NIDAR process binds only the loopback endpoint
`udpin://127.0.0.1:14540`; PX4's standard SITL onboard link sends to that
consumer endpoint. QGroundControl remains on its separate documented endpoint
(`14550`), and Phase 2's passive smoke listener remains on `14560`.

The Phase 3A integration script verifies that `14540` is available before
starting NIDAR and reports a clear bind failure if another local process owns
it. It preserves the existing QGroundControl and passive-listener ownership
and does not change Phase 2's passive smoke-test contract.

The `nidar-flight` application gains an explicit simulation mode that accepts
the endpoint and a bounded discovery deadline. It prints only connection and
telemetry readiness diagnostics, exits nonzero on a typed failure, and
performs a clean disconnect. A bounded integration script starts X500 SITL,
runs this application, verifies PX4 autopilot discovery plus valid, fresh
telemetry, and then stops only the containers/processes it created. It sends
no MAVSDK action, mission, parameter, or setpoint call.

## Verification

Unit tests must cover:

- successful state transitions and idempotent disconnect;
- no-PX4 discovery timeout and delayed discovery within/after the deadline;
- malformed/unbindable transport versus a successfully bound listener with no
  discovered vehicle;
- rejection of a discovered MAVLink system that does not contain the expected
  connected PX4 autopilot;
- disconnect and explicit reconnect;
- repeated connect/disconnect cycles without duplicate state/subscriptions;
- fresh, stale, invalid, and unavailable telemetry;
- independent per-field freshness, including proof that updating one field
  does not refresh another, and invalidation of every field after disconnect;
- typed local-policy rejection for every Phase 3B command entry point;
- MockVehicle determinism and bounded behavior.

Integration and SITL tests must cover:

- CMake links the pinned MAVSDK package inside the Ubuntu 24.04 dev image;
- runtime version/pin evidence where practical;
- MAVSDK configured as `CompanionComputer`, with forwarding disabled;
- unavailable/occupied local bind endpoint reports a bounded transport failure;
- valid listener with no PX4 autopilot reports a bounded discovery timeout;
- X500 SITL discovery of a connected PX4 autopilot and valid/fresh telemetry
  at `127.0.0.1:14540`;
- application clean shutdown and no lingering Phase 3A container/process;
- repeated startup/shutdown does not leave the endpoint occupied;
- source scan showing MAVSDK headers/usages exist only in the vehicle adapter;
- source-level check showing active-command MAVSDK plugins are absent from
  Phase 3A production code.

Thread/lifetime verification exercises teardown while telemetry is active and
uses available compatible sanitizers to detect use-after-free, data race,
deadlock, or callback-after-destruction defects. If a sanitizer cannot run in
the selected dependency/runtime environment, evidence records the limitation
and the strongest executable replacement test.

Every claim requires fresh command output, exit status, failure count, and
recorded evidence under `docs/test-results/`. Independent review assesses the
adapter boundary, companion-computer identity, PX4 autopilot selection,
thread/lifetime safety, timeout classification, field-level freshness,
disconnect invalidation, command-policy enforcement, SITL evidence, and
pinned dependency provenance. No unresolved Critical or Important finding is
allowed at Phase 3A completion.

## Required Phase 3A evidence

Store fresh evidence under `docs/test-results/` for the MAVSDK pin/checksum,
CMake/build, unit tests, static analysis/sanitizers, source-boundary checks,
SITL integration, disconnect/reconnect, repeated lifecycle, runtime version,
and independent review. SITL evidence records the PX4 identity, MAVSDK pin and
component identity, endpoint, discovery deadline, discovered system identity,
validated telemetry fields and freshness criteria, disconnect result, and
final exit status.

## Phase 3A exit criteria

Phase 3A is complete only when the MAVSDK dependency is pinned and verified;
MAVSDK is configured as a companion computer; `IVehicle`, `MockVehicle`, and
`MavsdkVehicle` exist; MAVSDK remains isolated to the vehicle adapter; no
active-command MAVSDK plugin/path is used; PX4 selection is explicit;
telemetry has field-level validity/freshness; connection/failure/timeout and
repeated lifecycle behavior are tested; teardown while telemetry is active is
verified; NIDAR communicates with X500 SITL without active command traffic;
and independent review has no unresolved Critical or Important finding.

Phase 3B cannot begin automatically: it requires its own approved design and
implementation plan for active command paths and their flight-affecting SITL
verification.

## References

- NIDAR master plan: `docs/MASTER_PLAN.md`, sections 11, 12, 29, and 45.
- MAVSDK C++ connection guide:
  <https://mavsdk.mavlink.io/main/en/cpp/guide/connections.html>
- MAVSDK C++ `Mavsdk` API reference:
  <https://mavsdk.mavlink.io/main/en/cpp/api_reference/classmavsdk_1_1_mavsdk.html>
- MAVSDK C++ `System` API reference:
  <https://mavsdk.mavlink.io/main/en/cpp/api_reference/classmavsdk_1_1_system.html>
- MAVSDK C++ `Telemetry` API reference:
  <https://mavsdk.mavlink.io/main/en/cpp/api_reference/classmavsdk_1_1_telemetry.html>
- MAVSDK v3.17.2 release assets:
  <https://github.com/mavlink/MAVSDK/releases/tag/v3.17.2>
