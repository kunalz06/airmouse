#!/usr/bin/env python3
"""Offline negative/positive fixtures for passive PX4/Gazebo sensor qualification."""
import math
import unittest

from qualify_sensor_data import (
    parse_scan,
    validate_obstacle_scan,
    validate_px4_sensor,
)

FLOW = """TOPIC: sensor_optical_flow
 sensor_optical_flow
 timestamp: 1000000 (0.02 seconds ago)
 pixel_flow: [0.00000, -0.012]
 integration_timespan_us: 20000
 quality: 120
"""
RANGE = """TOPIC: distance_sensor
 distance_sensor
 min_distance: 0.02000
 max_distance: 12.00000
 current_distance: 0.17620
 orientation: 25
"""
SCAN = """frame: "rplidar_link"
angle_min: -3.141592653589793
angle_max: 3.141592653589793
range_min: 0.15
range_max: 12
count: 720
"""


def sample_scan(front=1.63, rear=math.inf):
    vals = [math.inf] * 720
    for i in range(350, 371):
        vals[i] = front
    vals[0] = rear
    return SCAN + "".join(f"ranges: {x}\n" for x in vals)


class SensorValidationTests(unittest.TestCase):
    def test_valid_px4_reports(self):
        report = validate_px4_sensor(FLOW, RANGE)
        self.assertEqual(report["flow_quality"], 120)
        self.assertEqual(report["integration_us"], 20000)
        self.assertAlmostEqual(report["range_m"], 0.1762)

    def test_reject_wrong_range_orientation(self):
        with self.assertRaisesRegex(AssertionError, "down-facing"):
            validate_px4_sensor(FLOW, RANGE.replace("orientation: 25", "orientation: 0"))

    def test_reject_wrong_range_envelope(self):
        with self.assertRaisesRegex(AssertionError, "envelope mismatch"):
            validate_px4_sensor(FLOW, RANGE.replace("max_distance: 12", "max_distance: 100"))

    def test_reject_nonfinite_flow_or_range(self):
        with self.assertRaisesRegex(AssertionError, "2-axis"):
            validate_px4_sensor(FLOW.replace("-0.012", "nan"), RANGE)
        with self.assertRaisesRegex(AssertionError, "not finite"):
            validate_px4_sensor(FLOW, RANGE.replace("0.17620", "nan"))

    def test_reject_bad_quality(self):
        with self.assertRaisesRegex(AssertionError, "quality"):
            validate_px4_sensor(FLOW.replace("quality: 120", "quality: 300"), RANGE)

    def test_good_front_obstacle(self):
        report = validate_obstacle_scan(parse_scan(sample_scan()))
        self.assertEqual(report["front_valid_rays"], 21)
        self.assertEqual(report["rear_valid_rays"], 0)
        self.assertAlmostEqual(report["front_median_m"], 1.63)

    def test_reject_empty_or_truncated_scan(self):
        with self.assertRaisesRegex(AssertionError, "truncated"):
            parse_scan(SCAN + "ranges: 1.63\n")
        with self.assertRaisesRegex(AssertionError, "wrong RPLIDAR frame"):
            parse_scan(sample_scan().replace('frame: "rplidar_link"', 'frame: "wrong"'))

    def test_reject_out_of_range_scan(self):
        with self.assertRaisesRegex(AssertionError, "declared limits"):
            parse_scan(sample_scan(front=15.0))

    def test_reject_unexpected_scan_direction(self):
        with self.assertRaisesRegex(AssertionError, "360 degree"):
            parse_scan(sample_scan().replace("angle_min: -3.141592653589793", "angle_min: -1.57"))

    def test_reject_obstacle_missing_or_wrong_distance(self):
        empty = SCAN + ("ranges: inf\n" * 720)
        with self.assertRaisesRegex(AssertionError, "missing"):
            validate_obstacle_scan(parse_scan(empty))
        with self.assertRaisesRegex(AssertionError, "range incorrect"):
            validate_obstacle_scan(parse_scan(sample_scan(front=8.0)))

    def test_reject_obstacle_behind_vehicle(self):
        with self.assertRaisesRegex(AssertionError, "rear sector"):
            values = [math.inf] * 720
            for i in list(range(0, 12)) + list(range(350, 371)):
                values[i] = 1.63
            validate_obstacle_scan(parse_scan(SCAN + "".join(f"ranges: {v}\n" for v in values)))


if __name__ == "__main__":
    unittest.main()
