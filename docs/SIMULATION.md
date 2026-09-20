# Phase 2 simulation

The Phase 2 simulator uses the pinned `nidar-px4-sim:v1.17.0-x500` image,
PX4 v1.17.0, Gazebo Harmonic, and the standard `gz_x500` vehicle.

## MAVLink topology

| Purpose | PX4 localhost source | Host consumer bind | Ownership |
|---|---:|---:|---|
| QGroundControl observation | UDP 14551 | UDP 14550 | QGroundControl owns 14550 |
| Passive SITL smoke | UDP 14561 | UDP 14560 | `sitl-smoke.py` owns 14560 |

`simulation/scripts/px4-rc.mavlink` is a read-only PX4 v1.17.0 startup
overlay. It publishes the two localhost-only observer streams above. The
smoke listener sends no MAVLink frames, requests no streams, and cannot alter
parameters or vehicle state.

## Headless smoke test

Run this from the repository root:

```bash
scripts/sitl-headless.sh
```

The script refuses occupied ports or an existing named container, waits at
most 90 seconds by default, writes console output to
`simulation/output/phase-2/`, and removes only the containers it starts. Set
`NIDAR_SITL_TIMEOUT_SECONDS` to another positive bounded value when needed.

## Local GUI and QGroundControl

In one terminal, start Gazebo:

```bash
scripts/sitl-gui.sh
```

In another terminal, start the host-installed QGroundControl application:

```bash
/opt/qgroundcontrol/QGroundControl.AppImage
```

QGroundControl receives the PX4 observer stream on UDP 14550. The GUI script
requires a local `DISPLAY`, `xauth`, and `/tmp/.X11-unix`. It creates a
temporary Xauthority file containing only the active display cookie, mounts
that file and `/tmp/.X11-unix` read-only, and removes the temporary file at
shutdown. It does not use `xhost +`, `--privileged`, or host IPC.

These procedures are for simulation observation. They do not arm the vehicle,
send MAVLink commands, modify PX4 parameters, or replace PX4 safety checks.
