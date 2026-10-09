#!/usr/bin/env python3
"""Passive SITL sensor qualification: PX4 uORB, GPS-off, disarm, and 2D scan geometry.

The vehicle is NEVER armed or commanded. A static obstacle is inserted into a
temporary Gazebo world to prove the RPLIDAR responds to geometry.
No ROS, MAVSDK command plugins, serial ports, or physical devices are used.
"""
import argparse
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO = ROOT / "simulation" / "scenarios" / "rplidar_front_target.sdf"
PX4_BIN = "/opt/PX4-Autopilot/build/px4_sitl_default/bin"
MODEL = "x500_mtf01p_rplidar_0"
SCAN_TOPIC = f"/world/default/model/{MODEL}/link/rplidar_link/sensor/rplidar_2d/scan"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def command(container: str, *args: str, timeout: float = 15.0) -> str:
    result = subprocess.run(
        ["docker", "exec", container, *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"docker exec {args[:2]} failed ({result.returncode}): "
            f"{result.stderr.strip()[:450]}"
        )
    return result.stdout


def field(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}:\s*(\S+)", text)
    require(match is not None, f"missing {name} in sensor report")
    return match.group(1)


def finite_number(text: str, name: str) -> float:
    number = float(field(text, name))
    require(math.isfinite(number), f"{name} is not finite: {number}")
    return number


def validate_px4_sensor(flow: str, distance: str) -> dict:
    require("TOPIC: sensor_optical_flow" in flow, "incorrect optical flow uORB topic")
    require("TOPIC: distance_sensor" in distance, "incorrect distance uORB topic")
    require(finite_number(flow, "timestamp") > 0, "flow timestamp not initialized")
    span = finite_number(flow, "integration_timespan_us")
    quality = finite_number(flow, "quality")
    require(0 < span < 500_000, "invalid integration interval")
    require(0 <= quality <= 255, "optical-flow quality out of 8-bit range")
    vector = re.search(r"(?m)^\s*pixel_flow:\s*\[\s*([^\]]+)\]", flow)
    require(vector is not None, "missing two-axis integrated optical flow")
    components = [float(s) for s in vector.group(1).split(",")]
    require(len(components) == 2 and all(map(math.isfinite, components)),
            "invalid 2-axis integrated flow")
    require(int(finite_number(distance, "orientation")) == 25,
            "range sensor orientation is not down-facing")
    low = finite_number(distance, "min_distance")
    high = finite_number(distance, "max_distance")
    measured = finite_number(distance, "current_distance")
    require(abs(low - 0.02) < 1e-5 and abs(high - 12.0) < 1e-4,
            f"range envelope mismatch: {low} to {high} m")
    require(low <= measured <= high, "downward distance outside simulated sensor envelope")
    return {"flow_quality": int(quality), "integration_us": int(span),
            "range_m": round(measured, 4)}


def parse_scan(text: str) -> dict:
    require(field(text, "frame") == '"rplidar_link"', "wrong RPLIDAR frame")
    count = int(field(text, "count"))
    require(count == 720, f"provisional scan count changed: {count}")
    angle_min = finite_number(text, "angle_min")
    angle_max = finite_number(text, "angle_max")
    range_min = finite_number(text, "range_min")
    range_max = finite_number(text, "range_max")
    require(abs(angle_min + math.pi) < 0.001 and abs(angle_max - math.pi) < 0.001,
            "not a 360 degree scan")
    require(abs(range_min - 0.15) < 0.001 and abs(range_max - 12.0) < 0.001,
            "RPLIDAR provisional range envelope changed")
    ranges = [float(v) for v in re.findall(r"(?m)^\s*ranges:\s*(\S+)", text)]
    require(len(ranges) == count, f"scan truncated: {len(ranges)} of {count}")
    require(all((range_min <= x <= range_max) for x in ranges if math.isfinite(x)),
            "finite scan return outside declared limits")
    require(all(not math.isnan(x) for x in ranges), "NaN scan ranges")
    return {"ranges": ranges, "count": count, "angle_min": angle_min,
            "angle_max": angle_max, "range_min": range_min, "range_max": range_max}


def validate_obstacle_scan(scan: dict) -> dict:
    # A 0.5m-deep box is centered at world x=2m; the scanner's x is +0.12m.
    # The expected front return is about 2 - 0.25 - 0.12 = 1.63m.
    ranges = scan["ranges"]
    front = [x for x in ranges[350:371] if math.isfinite(x)]
    rear = [x for x in ranges[:35] + ranges[-35:] if math.isfinite(x)]
    require(len(front) >= 12, "static target missing in the forward laser sector")
    median = statistics.median(front)
    require(1.25 < median < 2.1, f"static target range incorrect: {median:.3f} m")
    require(len(rear) < 8, "unexpected obstacle in rear sector")
    return {"front_median_m": round(median, 3),
            "front_valid_rays": len(front),
            "rear_valid_rays": len(rear)}


def px4_topic(container: str, topic: str) -> str:
    return command(container, f"{PX4_BIN}/px4-listener", topic, "1")


def require_gps_off(container: str) -> None:
    for name in ("SYS_HAS_GPS", "SIM_GPS_USED", "EKF2_GPS_CTRL"):
        report = command(container, f"{PX4_BIN}/px4-param", "show", name)
        require(re.search(rf"\b{re.escape(name)}\b.*:\s*0(?:\s|$)", report) is not None,
                f"{name} is not explicitly disabled")
    status = command(container, f"{PX4_BIN}/px4-commander", "status")
    require(re.search(r"(?m)^\s*INFO\s+\[commander\]\s+Disarmed\s*$", status) is not None,
            "PX4 is not confirmed disarmed")


def ensure_fresh_flow(container: str, first: str) -> None:
    before = int(finite_number(first, "timestamp"))
    for _ in range(12):
        time.sleep(0.25)
        new = px4_topic(container, "sensor_optical_flow")
        if int(finite_number(new, "timestamp")) > before:
            return
    raise AssertionError("optical flow publication has stopped or is stale")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", required=True)
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    args = parser.parse_args()
    require_gps_off(args.container)
    flow = px4_topic(args.container, "sensor_optical_flow")
    distance = px4_topic(args.container, "distance_sensor")
    telemetry = validate_px4_sensor(flow, distance)
    ensure_fresh_flow(args.container, flow)

    # Gazebo's own published LaserScan (not injected into the PX4 EKF).
    sdf = args.scenario.read_text()
    require("<static>true</static>" in sdf, "obstacle must be static")
    require('nidar_lidar_target' in sdf, "unexpected obstacle model name")
    req = "sdf: " + json.dumps(sdf)
    reply = command(args.container, "gz", "service",
                    "-s", "/world/default/create", "--reqtype", "gz.msgs.EntityFactory",
                    "--reptype", "gz.msgs.Boolean", "--timeout", "10000",
                    "--req", req, timeout=20)
    require(re.search(r"\bdata:\s*true\b", reply) is not None,
            "Gazebo refused static target insertion")
    scan = None
    result = None
    for _ in range(8):
        out = command(args.container, "gz", "topic", "-e", "-n", "1",
                      "-t", SCAN_TOPIC, timeout=13)
        scan = parse_scan(out)
        try:
            result = validate_obstacle_scan(scan)
            break
        except AssertionError:
            time.sleep(0.35)
    require(result is not None, "RPLIDAR did not detect the inserted static obstacle")
    require_gps_off(args.container)  # still disarmed and GPS-disabled
    print(json.dumps({"px4": telemetry, "rplidar": result,
                      "gps_disabled": True, "disarmed": True}, sort_keys=True))
    print("Stationary sensor geometry and GPS-denial qualification passed")
    print("Note: neither moving-flight flow quality nor EKF2 flight readiness was qualified")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"sensor qualification failed: {error}", file=sys.stderr)
        sys.exit(1)
