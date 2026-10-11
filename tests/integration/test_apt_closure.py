#!/usr/bin/env python3
"""Offline regression tests for exact APT package-closure format."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify-runtime-apt-closure.py"
spec = importlib.util.spec_from_file_location("nidar_apt_closure", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verify = module.validate_inventory
lock_metadata = module.lock_metadata
validate_lock = module.validate_lock
verify_snapshot_sources = module.verify_snapshot_sources
load_policy = module.load_policy
snapshot_sources = module.snapshot_sources

REPO = SCRIPT.parent.parent


class AptClosureTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(REPO)
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

    def test_reject_altered_snapshot_metadata(self):
        inventory = verify(self.valid, "runtime")
        lock = lock_metadata({stage: inventory for stage in module.STAGES}, self.policy)
        lock["snapshot"]["url"] = "https://snapshot.ubuntu.com/ubuntu/20261002T000000Z"
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for stage in module.STAGES:
                (directory / f"{stage}-packages.tsv").write_bytes(self.valid)
            with self.assertRaisesRegex(ValueError, "snapshot"):
                validate_lock(lock, directory, self.policy)

    def test_accept_exact_snapshot_and_closure(self):
        inventories = {stage: verify(self.valid, stage) for stage in module.STAGES}
        lock = lock_metadata(inventories, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for stage in module.STAGES:
                (directory / f"{stage}-packages.tsv").write_bytes(self.valid)
            self.assertEqual(validate_lock(lock, directory, self.policy), inventories)

    def test_reject_tampered_closure(self):
        inventory = verify(self.valid, "runtime")
        lock = lock_metadata({stage: inventory for stage in module.STAGES}, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for stage in module.STAGES:
                (directory / f"{stage}-packages.tsv").write_bytes(self.valid)
            # The manifest's hash no longer matches the exact committed TSV.
            (directory / "runtime-packages.tsv").write_bytes(
                self.valid.replace(b"20240203", b"20240204")
            )
            with self.assertRaisesRegex(ValueError, "differs"):
                validate_lock(lock, directory, self.policy)

    def test_accept_exact_deb822_snapshot_sources(self):
        self.assertIsNone(verify_snapshot_sources(snapshot_sources(self.policy), self.policy))

    def test_reject_live_or_changed_snapshot_sources(self):
        live = snapshot_sources(self.policy).replace(
            self.policy["url"].encode(), b"http://archive.ubuntu.com/ubuntu"
        )
        changed = snapshot_sources(self.policy).replace(
            b"20261001T000000Z", b"20261002T000000Z"
        )
        extra = snapshot_sources(self.policy) + b"Types: deb\n"
        for content in (live, changed, extra):
            with self.assertRaisesRegex(ValueError, "exact reviewed Deb822"):
                verify_snapshot_sources(content, self.policy)

    def test_inventory_dir_writes_exact_three_stage_lock_without_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "export"
            inventory_dir.mkdir()
            for stage in module.STAGES:
                (inventory_dir / f"{stage}-packages.tsv").write_bytes(self.valid)
            lock_dir = root / "closure"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--inventory-dir", str(inventory_dir),
                 "--write-lock", "--lock-dir", str(lock_dir)],
                check=True, text=True, capture_output=True,
            )
            self.assertIn("APT package-closure verification passed", result.stdout)
            lock = json.loads((root / "apt-closure.lock.json").read_text())
            self.assertEqual(set(lock["stages"]), set(module.STAGES))
            for stage in module.STAGES:
                self.assertEqual((lock_dir / f"{stage}-packages.tsv").read_bytes(), self.valid)

    def test_inventory_dir_fail_closed_for_incomplete_or_extra_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory_dir = Path(tmp)
            (inventory_dir / "runtime-packages.tsv").write_bytes(self.valid)
            (inventory_dir / "unexpected.txt").write_text("not an inventory\n")
            with self.assertRaisesRegex(ValueError, "exactly the three stage closures"):
                module.collect_from_inventory_dir(inventory_dir)

    def test_write_lock_requires_an_explicit_inventory_or_image_source(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--write-lock"],
            text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --image-ref or --inventory-dir", result.stderr)

    def test_production_builder_rejects_bootstrap_switch(self):
        result = subprocess.run(
            [str(REPO / "scripts/build-runtime-arm64.sh"), "--bootstrap-apt-closure"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)

    def test_final_runtime_target_has_locked_mode_guard(self):
        runtime = (REPO / "docker/runtime/Dockerfile").read_text()
        final_stage = runtime.split("FROM runtime-apt AS runtime", 1)[1]
        self.assertIn('test "${NIDAR_APT_LOCK_MODE}" = "locked"', final_stage)
        self.assertIn('test "${NIDAR_APT_BASELINE_GENERATION}" = "0"', final_stage)

    def test_repository_policy_rejects_versions_lock_mutations(self):
        files = (
            "config/versions.lock", "config/apt-closure.lock.json",
            "docker/runtime/Dockerfile", "docker/apt/nidar-snapshot.sources",
            "docker/apt/nidar-snapshot-ca-certificates.crt", "docker/apt/install-locked.sh",
        )
        replacements = {
            "URL": ("ubuntu_24_04_apt_snapshot_url = \"https://snapshot.ubuntu.com/ubuntu/20261001T000000Z\"",
                    "ubuntu_24_04_apt_snapshot_url = \"https://snapshot.ubuntu.com/ubuntu/20261002T000000Z\""),
            "suites": ("ubuntu_24_04_apt_snapshot_suites = \"noble,noble-updates,noble-security,noble-backports\"",
                       "ubuntu_24_04_apt_snapshot_suites = \"noble,noble-updates\""),
            "signed-by": ("ubuntu_24_04_apt_snapshot_signed_by = \"/usr/share/keyrings/ubuntu-archive-keyring.gpg\"",
                          "ubuntu_24_04_apt_snapshot_signed_by = \"/tmp/not-ubuntu.gpg\""),
            "CA hash": ("ubuntu_24_04_apt_bootstrap_bundle_sha256 = \"22b557a27055b33606b6559f37703928d3e4ad79f110b407d04986e1843543d1\"",
                        "ubuntu_24_04_apt_bootstrap_bundle_sha256 = \"00b557a27055b33606b6559f37703928d3e4ad79f110b407d04986e1843543d1\""),
            "lock path": ("ubuntu_24_04_arm64_apt_closure_lock = \"config/apt-closure.lock.json\"",
                          "ubuntu_24_04_arm64_apt_closure_lock = \"config/other-closure.lock.json\""),
            "schema": ("ubuntu_24_04_arm64_apt_closure_schema = \"nidar-phase-4a-apt-closure-v2\"",
                       "ubuntu_24_04_arm64_apt_closure_schema = \"nidar-phase-4a-apt-closure-v3\""),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in files:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO / relative, destination)
            shutil.copytree(REPO / "config/apt-closure", root / "config/apt-closure")
            versions = root / "config/versions.lock"
            original = versions.read_text()
            for name, (old, new) in replacements.items():
                self.assertIn(old, original, name)
                versions.write_text(original.replace(old, new, 1))
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--check-repository", "--repo", str(root)],
                    text=True, capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("APT closure verification failed", result.stderr, name)
                versions.write_text(original)


if __name__ == "__main__":
    unittest.main()
