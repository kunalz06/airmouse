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

## Interfaces and data model

`include/nidar/vehicle/vehicle_types.hpp` owns value types only. It defines
strong enums for connection state, flight mode, vehicle-command result, and
telemetry validity; all temporal values use `std::chrono::steady_clock`.
`TelemetrySnapshot` is immutable after construction and records its observation
time, individual-field validity, armed state, flight mode, and battery data.
No field without a validity flag is interpreted as current vehicle state.

`include/nidar/vehicle/ivehicle.hpp` is the stable dependency boundary. Its
Phase 3A operations are `connect`, `disconnect`, `connection_status`,
`telemetry_snapshot`, and the command-shaped methods needed to prove the
temporary safety policy. Each operation uses a typed result rather than
exceptions for expected transport or PX4 failures. Timeouts are explicit
`std::chrono` arguments; neither interface nor callers use magic delays.

`MockVehicle` is a deterministic test implementation with no MAVSDK
dependency. Tests configure its discovery delay, connection state, telemetry
publication time, command result, and disconnect/reconnect events. It has no
background busy loop and uses bounded state kept under test control.

`MavsdkVehicle` is the sole MAVSDK-specific implementation in
`src/vehicle/`. It owns its MAVSDK connection handle and subscriptions through
RAII, maps MAVSDK outcomes to NIDAR types, and publishes a synchronized
immutable snapshot. No other production source directory may include MAVSDK
headers. An automated source-boundary test enforces that rule.

## Lifecycle and failure semantics

`connect(url, discovery_timeout)` first validates and adds the configured
MAVSDK transport, then waits only until the supplied deadline for PX4 system
discovery. A transport that opens but discovers no PX4 vehicle returns a
typed connection-timeout result. A malformed or unavailable transport returns
its own typed failure immediately.

On MAVSDK disconnect, the adapter enters `Disconnected`, invalidates every
telemetry field, and resolves pending connection work with a typed failure.
It does not silently retry. A caller explicitly invokes a new bounded
`connect()` to reconnect. `disconnect()` is idempotent and completes callback
unsubscription and connection removal before returning.

Telemetry freshness is calculated from the snapshot observation time and the
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

## SITL topology and application usage

Phase 3A reuses the Phase 2 PX4 X500 container and its upstream onboard
MAVLink link. The NIDAR process binds only the loopback endpoint
`udpin://127.0.0.1:14540`; PX4's standard SITL onboard link sends to that
consumer endpoint. QGroundControl remains on its separate documented endpoint
(`14550`), and Phase 2's passive smoke listener remains on `14560`.

The `nidar-flight` application gains an explicit simulation mode that accepts
the endpoint and a bounded discovery deadline. It prints only connection and
telemetry readiness diagnostics, exits nonzero on a typed failure, and
performs a clean disconnect. A bounded integration script starts X500 SITL,
runs this application, verifies PX4 discovery plus valid telemetry, and then
stops only the containers/processes it created. It sends no MAVSDK action,
mission, parameter, or setpoint call.

## Verification

Unit tests must cover:

- successful state transitions and idempotent disconnect;
- no-PX4 timeout and delayed discovery within/after the deadline;
- disconnect and explicit reconnect;
- fresh, stale, invalid, and unavailable telemetry;
- typed local-policy rejection for every Phase 3B command entry point;
- MockVehicle determinism and bounded behavior.

Integration and SITL tests must cover:

- CMake links the pinned MAVSDK package inside the Ubuntu 24.04 dev image;
- an unavailable local endpoint reports a bounded failure;
- X500 SITL discovery and valid telemetry at `127.0.0.1:14540`;
- application clean shutdown and no lingering Phase 3A container/process;
- source scan showing MAVSDK headers/usages exist only in the vehicle adapter.

Every claim requires fresh command output, exit status, failure count, and
recorded evidence under `docs/test-results/`. An independent review must
assess the adapter boundary, thread/lifetime safety, timeout behavior,
telemetry freshness, command-policy enforcement, SITL evidence, and changes
to pinned dependency provenance. No unresolved Critical or Important finding
is allowed at Phase 3A completion.

## Phase 3A exit criteria

Phase 3A is complete only when the MAVSDK dependency is pinned and verified,
`IVehicle`, `MockVehicle`, and `MavsdkVehicle` exist, MAVSDK remains isolated
to the vehicle adapter, telemetry and connection-failure cases are tested,
the NIDAR application communicates with X500 SITL without command traffic,
and the independent review has no unresolved Critical or Important finding.

Phase 3B cannot begin automatically: it requires its own approved design and
implementation plan for active command paths and their flight-affecting SITL
verification.

## References

- NIDAR master plan: `docs/MASTER_PLAN.md`, sections 11, 12, 29, and 45.
- MAVSDK C++ connection guide:
  <https://mavsdk.mavlink.io/main/en/cpp/guide/connections.html>
- MAVSDK C++ `Mavsdk` API reference:
  <https://mavsdk.mavlink.io/main/en/cpp/api_reference/classmavsdk_1_1_mavsdk.html>
- MAVSDK v3.17.2 release assets:
  <https://github.com/mavlink/MAVSDK/releases/tag/v3.17.2>
