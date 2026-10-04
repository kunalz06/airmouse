# Simulation

The simulator uses the pinned `nidar-px4-sim:v1.17.0-x500` image,
PX4 v1.17.0, Gazebo Harmonic, and the standard `gz_x500` vehicle.

## MAVLink topology

| Purpose | PX4 localhost source | Host consumer bind | Ownership |
|---|---:|---:|---|
| QGroundControl | UDP 14551 | UDP 14550 | QGroundControl owns 14550 |
| Passive Phase 2 smoke | UDP 14561 | UDP 14560 | `sitl-smoke.py` owns 14560 |
| NIDAR Phase 3A vehicle adapter | upstream onboard link | UDP 14540 | `MavsdkVehicle` owns 14540 |

`simulation/scripts/px4-rc.mavlink` is a read-only PX4 v1.17.0 startup
overlay. The Phase 2 smoke process itself is receive-only: it sends no MAVLink
frames, requests no streams, and issues no vehicle commands. The underlying
PX4 UDP MAVLink transport is bidirectional, so safety is enforced by the
consumer/application policy rather than by claiming the socket cannot receive
traffic.

## Phase 2 headless smoke

Run:

```bash
scripts/sitl-headless.sh
```

The listener validates a PX4 heartbeat plus `LOCAL_POSITION_NED` within a
bounded deadline and the launcher removes only the containers it created.

## Local GUI and QGroundControl

Run Gazebo:

```bash
scripts/sitl-gui.sh
```

Start the verified host QGroundControl separately. The GUI launcher uses a
private temporary Xauthority cookie, read-only X11 mounts, host networking,
and no privileged mode or host IPC.

## Phase 3A vehicle telemetry

Build the development image and application first:

```bash
docker build --platform linux/amd64 -t nidar-dev -f docker/dev/Dockerfile .
./scripts/configure.sh
./scripts/build.sh
```

Then run:

```bash
NIDAR_SITL_TIMEOUT_SECONDS=90 scripts/sitl-vehicle.sh
```

The application identifies as a MAVSDK `CompanionComputer`, disables MAVSDK
forwarding, binds only `udpin://127.0.0.1:14540`, accepts only a connected
PX4 autopilot system, and requires fresh armed, flight-mode, and battery
telemetry before success. Phase 3A instantiates no Action, Offboard, Mission,
MissionRaw, or Param plugin and all command-shaped `IVehicle` methods are
locally rejected with `RejectedByPhasePolicy`.

The integration launcher checks that UDP 14540 is free before startup, uses a
finite deadline, records logs under ignored `simulation/output/phase-3a/`,
and removes only its own named containers.
