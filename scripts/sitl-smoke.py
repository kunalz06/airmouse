#!/usr/bin/env python3
"""Passively validate basic PX4 SITL MAVLink telemetry.

The listener opens an UDP receive endpoint only.  It sends no MAVLink frames,
requests no streams, changes no parameters, and issues no vehicle commands.
"""

from __future__ import annotations

import argparse
import sys
import time

from pymavlink import mavutil


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True, help="UDP listen port")
    parser.add_argument(
        "--timeout", type=float, required=True, help="Deadline in seconds (must be > 0)"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in the range 1..65535")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return args


def main() -> int:
    args = parse_args()
    try:
        connection = mavutil.mavlink_connection(f"udpin:0.0.0.0:{args.port}")
    except OSError as error:
        print(f"unable to bind UDP port {args.port}: {error}", file=sys.stderr)
        return 2

    deadline = time.monotonic() + args.timeout
    received_px4_heartbeat = False
    received_local_position = False

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        message = connection.recv_match(blocking=True, timeout=max(remaining, 0.01))
        if message is None:
            continue

        message_type = message.get_type()
        if message_type == "HEARTBEAT":
            received_px4_heartbeat = (
                message.autopilot == mavutil.mavlink.MAV_AUTOPILOT_PX4
            )
        elif message_type == "LOCAL_POSITION_NED":
            received_local_position = True

        if received_px4_heartbeat and received_local_position:
            print(
                "passive SITL smoke passed: received PX4 HEARTBEAT and "
                "LOCAL_POSITION_NED"
            )
            return 0

    print(
        "timed out waiting for PX4 HEARTBEAT and LOCAL_POSITION_NED",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
