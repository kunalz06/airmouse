# Local sensor simulation verification

Test system: Ubuntu 26 host; pinned Ubuntu 24.04 PX4 v1.17.0 / Gazebo Harmonic simulator Docker image; branch `feature/sim-mtf01p-rplidar`.

A custom X500 model was mounted read-only into the existing PX4 Gazebo image and started headless with `PX4_SYS_AUTOSTART=4021` and `PX4_SIM_MODEL=gz_x500_mtf01p_rplidar`. This deliberately avoids modifications to the simulator image.

**Live observation:** PX4's `px4-listener sensor_optical_flow` produced `pixel_flow`, `integration_timespan_us` and `quality` fields; `px4-listener distance_sensor` produced fresh `current_distance`; Gazebo's `/world/default/model/x500_mtf01p_rplidar_0/link/rplidar_link/sensor/rplidar_2d/scan` delivered 360° scan messages.

The first optical-flow test using `gz topic -e` showed no printable PX4 custom-protobuf message. The same behavior was reproduced against the stock `x500_flow` model. PX4's native uORB listener on the stock model returned sensor-flow telemetry, demonstrating the `gz topic` text display was not a valid acceptance criterion. The actual automated smoke now checks PX4 uORB flow instead.

The resulting `scripts/sitl-sensors.sh --smoke` printed:

```text
PX4 uORB sensor_optical_flow publication received
PX4 uORB distance_sensor publication received
RPLIDAR Gazebo LaserScan publication received
GPS-denied MTF-01P-equivalent optical flow/range and RPLIDAR scan smoke passed
```

This establishes telemetry and simulator integration, **not** dynamic flow-quality, actual RPLIDAR model matching, EKF fusion validity, or flight readiness.

## Reliability correction

A follow-up smoke initially found the flow topic advertised before the first uORB publication (`never published`). That test **failed** and exposed a startup race. The launcher was changed to wait for actual PX4 flow and range publications with bounded retries, rather than passing from topic advertisement alone. The corrected end-to-end smoke **passed** (exit 0, 17.43 s). Static SDF contracts and ShellCheck passed. Flight-quality flow was not measured and no arm/takeoff command was issued.

## Final local smoke and cleanup

After adding bounded startup sampling and waiting for the Docker `--rm` process to exit on shutdown, the clean rerun passed with **exit code 0** in 17.06 seconds:

```text
PX4 uORB sensor_optical_flow publication received
PX4 uORB distance_sensor publication received
RPLIDAR Gazebo LaserScan publication received
GPS-denied MTF-01P-equivalent optical flow/range and RPLIDAR scan smoke passed
TEMP CONTAINER CLEANED
```

Static SDF contract check: passed. ShellCheck and Bash syntax: passed. This is local simulation verification; hosted CI, dynamic motion/quality tests, LiDAR exact-SKU calibration, PX4 estimator fusion qualification and flight hardware tests are not covered.
