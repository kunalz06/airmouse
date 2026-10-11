#!/usr/bin/env python3
"""Offline unit tests for runtime OCI/Docker creation-time provenance."""
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/record-runtime-manifest.py"
spec = importlib.util.spec_from_file_location("nidar_runtime_manifest", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeManifestTimestampTests(unittest.TestCase):
    def setUp(self):
        self.timestamp = "2026-10-11T05:03:22Z"
        self.labels = {"org.opencontainers.image.created": self.timestamp}
        self.config = {"created": self.timestamp}
        self.docker = {"Created": self.timestamp}

    def test_accepts_matching_captured_label_oci_and_docker_timestamps(self):
        result = module.validate_created_timestamps(
            self.timestamp, self.labels, self.labels, self.config, self.docker
        )
        self.assertEqual(result.isoformat(), "2026-10-11T05:03:22+00:00")

    def test_rejects_oci_config_timestamp_mismatch(self):
        config = {"created": "2026-10-11T05:03:23Z"}
        with self.assertRaisesRegex(ValueError, "OCI config.created differs"):
            module.validate_created_timestamps(
                self.timestamp, self.labels, self.labels, config, self.docker
            )

    def test_rejects_loaded_docker_timestamp_mismatch(self):
        docker = {"Created": "2026-10-11T05:03:23Z"}
        with self.assertRaisesRegex(ValueError, "loaded Docker image .Created differs"):
            module.validate_created_timestamps(
                self.timestamp, self.labels, self.labels, self.config, docker
            )

    def test_rejects_noncanonical_exporter_timestamp(self):
        docker = {"Created": "2026-10-11T05:03:22.000000000Z"}
        with self.assertRaisesRegex(ValueError, "canonical UTC"):
            module.validate_created_timestamps(
                self.timestamp, self.labels, self.labels, self.config, docker
            )


if __name__ == "__main__":
    unittest.main()
