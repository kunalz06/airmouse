#!/usr/bin/env python3
"""Static interface checks for NIDAR's MTF-01P and provisional RPLIDAR Gazebo models.

This does not claim physical validation or substitute for the live SITL smoke test.
"""
from math import pi
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / "simulation" / "models"
def read_model(name):
    # PX4/Gazebo stock optical_flow.sdf uses a custom "gz:type" attribute
    # without an XML namespace declaration. Normalize only for ElementTree.
    source = (ROOT / name / "model.sdf").read_text()
    return ET.fromstring(source.replace("gz:type=", "gz_type="))


flow = read_model("mtf_01p_flow")
quad = read_model("x500_mtf01p_rplidar")


def require(cond, message):
    if not cond:
        raise AssertionError(message)


def value(root, path):
    el = root.find(path)
    require(el is not None and el.text is not None, f"missing {path}")
    return el.text.strip()


require(value(flow, "./model[@name='mtf_01p_flow']/link/sensor[@name='flow_camera']/update_rate") == "100", "MTF camera nominal rate")
require(value(flow, "./model/link/sensor[@name='optical_flow']/update_rate") == "100", "MTF optical-flow nominal rate")
fov = float(value(flow, "./model/link/sensor[@name='flow_camera']/camera/horizontal_fov"))
require(abs(fov - 42 * pi / 180) < 0.001, "MTF simulated FOV")

model = quad.find("./model[@name='x500_mtf01p_rplidar']")
require(model is not None, "combined model")
uris = [el.text for el in model.findall("./include/uri")]
require("x500" in uris and "model://mtf_01p_flow" in uris, "X500 + MTF")
range_sensor = model.find("./link[@name='lidar_sensor_link']/sensor[@name='lidar']")
require(range_sensor is not None and range_sensor.get("type") == "gpu_lidar", "MTF downward ToF")
require(float(value(range_sensor, "./ray/range/min")) == 0.02, "MTF ToF minimum")
require(float(value(range_sensor, "./ray/range/max")) == 12.0, "MTF ToF maximum")
require(int(value(range_sensor, "./update_rate")) == 100, "MTF nominal ToF update rate")
require(int(value(range_sensor, "./ray/scan/horizontal/samples")) == 1, "MTF ToF is not a 2D scanner")

scanner = model.find("./link[@name='rplidar_link']/sensor[@name='rplidar_2d']")
require(scanner is not None and scanner.get("type") == "gpu_lidar", "RPLIDAR Gazebo scanner")
require(int(value(scanner, "./ray/scan/horizontal/samples")) == 720, "provisional scan points")
require(abs(float(value(scanner, "./ray/scan/horizontal/min_angle")) + pi) < 1e-5, "360 scan start")
require(abs(float(value(scanner, "./ray/scan/horizontal/max_angle")) - pi) < 1e-5, "360 scan end")
require(float(value(scanner, "./ray/range/max")) == 12, "provisional scan range")
require(int(value(scanner, "./update_rate")) == 10, "provisional scan rate")
require(value(scanner, "./gz_frame_id") == "rplidar_link", "scanner frame ID")
require(model.find("./joint[@name='rplidar_joint']") is not None, "scanner fixed mounting")
print("MTF-01P/RPLIDAR static SDF contract tests passed")
