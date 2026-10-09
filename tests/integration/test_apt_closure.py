#!/usr/bin/env python3
"""Offline regression tests for exact APT package-closure format."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify-runtime-apt-closure.py"
spec = importlib.util.spec_from_file_location("nidar_apt_closure", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verify = module.validate_inventory


class AptClosureTests(unittest.TestCase):
    def setUp(self):
        self.valid = (
            b"ca-certificates\t20240203\tall\n"
            b"libgcc-s1:arm64\t14.2.0-4ubuntu2\tarm64\n"
            b"libstdc++6:arm64\t14.2.0-4ubuntu2\tarm64\n"
        )

    def test_exact_package_version_architecture(self):
        result = verify(self.valid, "runtime")
        self.assertEqual(result["package_count"], 3)
        self.assertEqual(result["sha256"], "sha256:" + hashlib.sha256(self.valid).hexdigest())

    def test_reject_unsorted(self):
        with self.assertRaisesRegex(ValueError, "not byte-sorted"):
            verify(b"z\t1\tarm64\na\t2\tarm64\n", "app-build")

    def test_reject_duplicates(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            verify(b"a\t1\tarm64\na\t2\tarm64\n", "runtime")

    def test_reject_missing_versions(self):
        with self.assertRaisesRegex(ValueError, "invalid package"):
            verify(b"broken\t\tarm64\n", "mavsdk-build")

    def test_reject_arch_mismatch(self):
        with self.assertRaisesRegex(ValueError, "invalid package"):
            verify(b"libstdc++6\t1\tamd64\n", "runtime")

    def test_reject_unterminated(self):
        with self.assertRaisesRegex(ValueError, "unterminated"):
            verify(self.valid.rstrip(b"\n"), "runtime")

    def test_reject_empty(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            verify(b"", "runtime")


if __name__ == "__main__":
    unittest.main()
