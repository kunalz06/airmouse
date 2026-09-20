# Phase 2 local GUI and QGroundControl evidence

- Timestamp: 2026-09-20T10:33:30+05:30
- Gazebo command: `scripts/sitl-gui.sh`
- QGroundControl command: `/opt/qgroundcontrol/QGroundControl.AppImage`
- Image: `nidar-px4-sim:v1.17.0-x500`
- Vehicle: `gz_x500`

## Result

The Gazebo GUI startup launched the X500 SITL model. PX4 logged the two
localhost observer links, including UDP `14551 -> 14550` for QGroundControl.
QGroundControl started on the host and its runtime log identified the PX4
vehicle by resolving PX4 flight modes (`Takeoff` and `Mission`).

## Local display access

The GUI session used `DISPLAY=:0`, a private temporary Xauthority file created
with `xauth nlist`, a read-only mount of that file at `/tmp/.Xauthority`, and
a read-only `/tmp/.X11-unix` mount. The simulator used host networking only;
it did not use `--privileged`, host IPC, or `xhost +`.

## Shutdown

The test stopped the named `nidar-sitl-gui` container and the QGroundControl
process started for this verification. The launcher's trap removed its
temporary Xauthority file. A subsequent container check found no Phase 2
simulation container.
