# Sensor simulation — MTF-01P + Slamtec RPLIDAR 2D

## Scope and safety

This simulation branch supplies three Gazebo sensors on the stock PX4 v1.17.0 X500 quadcopter:

| Physical component | Simulated data path | Consumer |
| --- | --- | --- |
| MicoAir MTF-01P optical-flow camera | PX4 Gazebo optical-flow sensor plugin, 42° horizontal FOV, nominal 100 Hz | PX4 `sensor_optical_flow` |
| MicoAir MTF-01P downward laser ToF range | Downward, one-ray Gazebo LiDAR, 0.02–12 m, nominal 100 Hz | PX4 `distance_sensor` |
| Slamtec RPLIDAR 2D (exact submodel not yet specified) | Generic 360° Gazebo `gpu_lidar` sensor, **provisional** 720 rays, 0.15–12 m, 10 Hz | Gazebo Transport; future Raspberry Pi SLAM adapter |

The MTF-01P nominal FOV, maximum range, output rate and dead zone follow the [MicoAir MTF-01P manufacturer's specifications](https://micoair.com/optical_range_sensor_mtf-01p/). The **standalone physical MTF-01P** outputs UART packets; this simulation does not emulate its UART/MAVLink/MicoLink protocol, transmission jitter, lens/illumination limits, calibration, mounting rotation, optical-flow confidence curve, ground-texture failures or production noise distribution. Those require separate tests before actual deployment.

The exact RPLIDAR SKU (A1, A2, C1, S2, etc.) has **not** been supplied. The generic 2D model does not represent a specific Slamtec protocol or scan timing, intensity/reflectivity profile, power/motor mechanics, or beam geometry. Real RPLIDAR specifications differ substantially by model: see the [Slamtec LiDAR lineup](https://www.slamtec.com/en/lidar). Set rate, number of rays, min/max range, mount transform and weight **only after** identifying the actual SKU; do not claim the current model is calibrated.

**SITL remains disarmed.** PX4's pinned `4021_gz_x500_flow` airframe turns simulated GPS off. The companion application and ARM64 runtime code are not changed, and all active vehicle commands remain disabled. The 2D RPLIDAR is explicitly Pi-side mapping input, **not** injected as an EKF altitude or local-position measurement.

## Launch and tests

Prerequisites: the previously built image `nidar-px4-sim:v1.17.0-x500`, Docker, and the pinned PX4 simulation files. Do **not** rebuild the ~10 GB simulator image for this sensor fixture.

From the repository worktree:

```bash
python3 tests/sitl/test_sensor_models.py
scripts/sitl-sensors.sh --smoke
```

The smoke command starts a clean headless Gazebo + PX4 session, verifies all sensor topics, checks actual PX4 `sensor_optical_flow` and `distance_sensor` uORB publications, confirms an actual RPLIDAR LaserScan message and shuts down the temporary container. It rejects missing topics, absent samples, and missing Gazebo model assets. Logs are at `simulation/output/sensors/px4-gazebo.log` outside image layers.

For interactive inspection, run `scripts/sitl-sensors.sh --run` in a terminal and use `docker exec nidar-sim-mtf01p-rplidar ...` for diagnosis. Press Ctrl+C to stop; do not run concurrently with other SITL sessions using the same Gazebo/UDP ports.

**Important:** The generic `gz topic -e` client may not render PX4's custom `px4.msgs.OpticalFlow` protobuf despite the plugin publishing valid uORB. Verify flow using PX4's `px4-listener sensor_optical_flow`, not by treating the absence of `gz topic -e` text as missing flow. When the drone is stationary on the ground, `quality: 0` and zero flow can be expected; this smoke test does not prove high-quality optical flow during flight.

## Passive stationary sensor qualification (implemented)

Run the existing fixture without any motor/flight command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/sitl -p 'test_sensor_qualification.py' -v
scripts/sitl-sensors.sh --qualify
```

The `--qualify` mode first runs the existing sensor smoke checks, then invokes `tests/sitl/qualify_sensor_data.py`. It verifies fresh PX4 optical-flow timestamps, finite two-axis flow, bounded integration time/quality (0–255), valid downward range with the configured 0.02–12 m envelope and downward mounting orientation, `SYS_HAS_GPS=0`, `SIM_GPS_USED=0`, `EKF2_GPS_CTRL=0`, and PX4 **Disarmed** before and after the check. No PX4 setpoint, arm or flight-mode command is sent.

It then creates one **static** geometry target in the temporary Gazebo world using `simulation/scenarios/rplidar_front_target.sdf`: a 0.5 x 1.2 x 0.7 m box centered 2 m in front of the X500. The scanner sits 0.12 m forward of the quadcopter origin. The 720-ray 360° Gazebo scan must report the obstacle in the forward sector at approximately 1.63 m, have the correct scan frame and declared range bounds, and remain clear at the rear. The test exits nonzero on missing/invalid measurements and automatically stops its temporary Docker container.

**Scope:** This proves a static geometry/telemetry data path, not actual Slamtec RPLIDAR driver compatibility, EKF2 fusion under motion, environmental resilience, optical-flow accuracy, or flight control authority. Stationary optical-flow quality can be zero and is intentionally not treated as a flight-quality pass. The RPLIDAR range, scan density and rate remain provisional until the specific Slamtec model is supplied.

## Next qualification gates

Before using sensor fusion to authorize GPS-denied flight, test controlled simulated movement, estimator optical-flow and range-aid configuration, flow quality versus height/texture/light, sensor dropouts, stale timeouts, mounting axis signs, EKF2 local position and range innovations, and recovery behaviors. Every test must remain under simulation safety policy. Later verify the real MTF-01P `Mavlink_px4` serial configuration and the actual RPLIDAR driver through a propulsion-safe bench test. Nothing in this branch authorizes hardware connection or active flight.
