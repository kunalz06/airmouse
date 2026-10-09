# Stationary sensor geometry qualification — 2026-10-09

**Branch:** `feature/sim-mtf01p-rplidar` (separate from Phase 4A). **Host:** Ubuntu 26 / Docker; pinned PX4 v1.17.0 X500 Gazebo simulation image, reused without rebuilding.

## Checks

- Passive `scripts/sitl-sensors.sh --qualify`: **passed**, exit code 0, temporary simulation container cleaned up.
- PX4 `sensor_optical_flow` and `distance_sensor`: actual uORB samples received; flow timestamp increased on repeated reads; integration interval and quality bounded; flow vectors finite.
- PX4 GPS-denied configuration: `SYS_HAS_GPS=0`, `SIM_GPS_USED=0`, `EKF2_GPS_CTRL=0`; PX4 remained **Disarmed**.
- Downward sensor returned `0.1762 m` with PX4-reported valid 0.02–12 m limits and orientation 25 (downward).
- Static front target in Gazebo at world x=2.0 m: **720** 360-degree scan rays, forward return median `1.631 m` (expected approximately 1.63 m due to scanner/target offset), **21/21** valid front-sector rays and **0** valid rear-sector rays.
- Result sample:

```text
PX4 uORB sensor_optical_flow publication received
PX4 uORB distance_sensor publication received
RPLIDAR Gazebo LaserScan publication received
{"disarmed": true, "gps_disabled": true, "px4": {"flow_quality": 0, "integration_us": 20000, "range_m": 0.1762}, "rplidar": {"front_median_m": 1.631, "front_valid_rays": 21, "rear_valid_rays": 0}}
Stationary sensor geometry and GPS-denial qualification passed
Note: neither moving-flight flow quality nor EKF2 flight readiness was qualified
GPS-denied MTF-01P-equivalent optical flow/range and RPLIDAR scan smoke passed
CLEANUP_OK
```

## Unit, negative and lint checks

`tests/sitl/test_sensor_qualification.py`: **11 of 11 passed**, including expected rejection of bad optical-flow quality, non-finite flow/range values, wrong range orientation/envelope, truncated or invalid 2D scans, wrong bearing, missing front obstacle, false rear obstacle, and invalid geometric distance. SDF contract test and Bash syntax and ShellCheck passed.

## Limitations / blockers

The observed optical-flow quality was **0** while stationary; do not infer moving-flight estimation performance. These Gazebo components are proxies, not calibrated device emulators. No EKF2 moving-target/innovation/flow-fusion stress testing, sensor dropouts, real hardware protocols, calibration, or flight testing occurred. Specific Slamtec scanner SKU is still unknown. The Phase 4A runtime branch and hardware-control policies are unaffected.
