#!/usr/bin/env python3
"""Deterministic checks for Phase 4B release evidence validation."""
import importlib.util
from pathlib import Path
import unittest
import json
import tempfile


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify-runtime-release.py"
spec = importlib.util.spec_from_file_location("nidar_runtime_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


SHA = "a" * 40
MANIFEST = "sha256:" + "b" * 64
CONFIG = "sha256:" + "c" * 64
LAYER = "sha256:" + "d" * 64


def successful_run(run_id=101):
    return {
        "id": run_id,
        "name": "build-test",
        "head_sha": SHA,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
    }


def successful_jobs():
    return {
        "jobs": [
            {"name": "amd64", "status": "completed", "conclusion": "success"},
            {"name": "sitl", "status": "completed", "conclusion": "success"},
            {"name": "arm64-runtime", "status": "completed", "conclusion": "success"},
        ]
    }


def candidate():
    return {
        "manifest_digest": MANIFEST,
        "config_digest": CONFIG,
        "layers": [LAYER],
        "media_type": "application/vnd.oci.image.manifest.v1+json",
        "platform": {"os": "linux", "architecture": "arm64"},
        "labels": {
            "org.opencontainers.image.revision": SHA,
            "org.opencontainers.image.source": "https://github.com/kunalz06/airmouse",
            "org.opencontainers.image.base.digest": "sha256:" + "0" * 64,
            "io.nidar.mavsdk.version": "3.17.2",
            "io.nidar.mavsdk.source-commit": "e" * 40,
            "io.nidar.target.architecture": "linux/arm64",
        },
    }


def release_record(status="VERIFIED"):
    return {
        "status": status, "source_git_commit": SHA, "source_repository": "kunalz06/airmouse",
        "workflow_run_id": 700, "workflow_run_attempt": 2,
        "release_timestamp": "2026-10-13T10:11:12Z",
        "source_timestamp": "2026-10-13T10:10:10Z", "build_timestamp": "2026-10-13T10:11:11Z",
        "platform": {"os": "linux", "architecture": "arm64"},
        "local_manifest_digest": MANIFEST, "local_config_digest": CONFIG,
        "oci_archive_sha256": "sha256:" + "e" * 64,
        "lock_sha256": "sha256:" + "f" * 64,
        "registry_manifest_digest": MANIFEST,
        "observed_registry_digest": MANIFEST,
        "registry_visibility": "private",
        "registry_reference": f"ghcr.io/kunalz06/nidar-runtime@{MANIFEST}",
        "failure_stage": None, "failure_reason": None,
        "idempotent": False,
        "closure_checks": {name: True for name in module.REQUIRED_CLOSURE_CHECKS},
        "test_results": {name: True for name in module.REQUIRED_TEST_CHECKS},
        "registry_image_identity": candidate(),
        "original_release_evidence": None,
        "current_retry_verification": None,
    }


def prior_artifact():
    return {
        "id": 987, "name": "phase-4b-runtime-release-evidence",
        "digest": "sha256:" + "f" * 64,
        "workflow_run": {"id": 700, "head_sha": SHA},
        "created_at": "2026-10-13T10:11:40Z",
    }


def prior_attempt():
    return {
        "id": 700, "run_attempt": 2,
        "head_sha": SHA, "event": "workflow_dispatch",
        "status": "completed", "conclusion": "success",
        "run_started_at": "2026-10-13T10:11:00Z",
        "updated_at": "2026-10-13T10:11:59Z",
    }


def prior_release_run():
    run = successful_run()
    run.update({"name": "release-runtime-arm64", "event": "workflow_dispatch",
                "id": 700, "run_attempt": 2})
    return run


def private_package():
    return {
        "id": 40201, "name": "nidar-runtime", "package_type": "container",
        "visibility": "private", "owner": {"login": "kunalz06"},
        "repository": {"name": "airmouse", "full_name": "kunalz06/airmouse",
                       "private": True, "owner": {"login": "kunalz06"}},
    }


class BootstrapRemoteTests(unittest.TestCase):
    TAG = f"ghcr.io/kunalz06/nidar-runtime:bootstrap-sentinel-123-1-{SHA}"

    @staticmethod
    def inspection():
        return {
            "Name": "ghcr.io/kunalz06/nidar-runtime", "Digest": MANIFEST,
            "Os": "linux", "Architecture": "amd64",
            "Labels": {
                "org.opencontainers.image.source": "https://github.com/kunalz06/airmouse",
                "org.opencontainers.image.revision": SHA,
                "io.nidar.artifact.kind": "bootstrap-sentinel",
            },
        }

    def test_ready_requires_same_digest_and_exact_remote_labels(self):
        self.assertTrue(hasattr(module, "verify_bootstrap_remote"), "bootstrap remote verifier is missing")
        result = module.verify_bootstrap_remote(self.inspection(), self.inspection(), SHA, self.TAG)
        self.assertEqual(result["sentinel_reference"], f"ghcr.io/kunalz06/nidar-runtime@{MANIFEST}")

    def test_hidden_or_inaccessible_404_never_proves_absence(self):
        for body in ({"message": "Not Found"},
                     {"message": "Resource not accessible by integration"},
                     private_package()):
            with self.subTest(body=body.get("message", "private metadata")):
                with self.assertRaisesRegex(ValueError, "ambiguous"):
                    module.classify_package(404, body)

    def test_rejects_mismatched_digest_source_kind_or_architecture(self):
        self.assertTrue(hasattr(module, "verify_bootstrap_remote"), "bootstrap remote verifier is missing")
        mutations = (
            ("digest", "Digest", "sha256:" + "f" * 64),
            ("source", "org.opencontainers.image.source", "https://github.com/other/repo"),
            ("revision", "org.opencontainers.image.revision", "f" * 40),
            ("kind", "io.nidar.artifact.kind", "runtime"),
            ("architecture", "Architecture", "arm64"),
        )
        for name, field, value in mutations:
            with self.subTest(name=name):
                remote = self.inspection()
                if field in remote["Labels"]:
                    remote["Labels"][field] = value
                else:
                    remote[field] = value
                with self.assertRaises(ValueError):
                    module.verify_bootstrap_remote(self.inspection(), remote, SHA, self.TAG)


class ExactShaCiEvidenceTests(unittest.TestCase):
    def test_accepts_exact_successful_main_push_across_paginated_runs(self):
        result = module.validate_ci_evidence(
            [{"workflow_runs": [{"id": 99, "name": "build-test", "head_sha": "f" * 40}]},
             {"workflow_runs": [successful_run()]}],
            {101: successful_jobs()}, SHA, SHA,
        )
        self.assertEqual(result["run_id"], 101)
        self.assertEqual(result["run_attempt"], 1)

    def test_rejects_missing_required_job(self):
        jobs = successful_jobs()
        jobs["jobs"].pop()
        with self.assertRaisesRegex(ValueError, "missing successful required jobs"):
            module.validate_ci_evidence([{"workflow_runs": [successful_run()]}], {101: jobs}, SHA, SHA)

    def test_rejects_failed_required_job(self):
        jobs = successful_jobs()
        jobs["jobs"][1]["conclusion"] = "failure"
        with self.assertRaisesRegex(ValueError, "missing successful required jobs"):
            module.validate_ci_evidence([{"workflow_runs": [successful_run()]}], {101: jobs}, SHA, SHA)

    def test_rejects_wrong_event_ref_and_source_identity(self):
        for field, value in (("event", "pull_request"), ("head_branch", "phase-4b-image-release"),
                             ("head_sha", "f" * 40)):
            run = successful_run()
            run[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "no successful exact-SHA main push build-test run"):
                    module.validate_ci_evidence([{"workflow_runs": [run]}], {101: successful_jobs()}, SHA, SHA)

    def test_rejects_stale_main_and_ambiguous_successes(self):
        with self.assertRaisesRegex(ValueError, "current main SHA"):
            module.validate_ci_evidence([{"workflow_runs": [successful_run()]}], {101: successful_jobs()}, SHA, "f" * 40)
        second = successful_run(102)
        with self.assertRaisesRegex(ValueError, "ambiguous successful"):
            module.validate_ci_evidence(
                [{"workflow_runs": [successful_run(), second]}],
                {101: successful_jobs(), 102: successful_jobs()}, SHA, SHA,
            )


class RemoteIdentityTests(unittest.TestCase):
    def test_accepts_exact_arm64_digest_preserving_identity(self):
        self.assertEqual(module.verify_remote_identity(candidate(), candidate()), MANIFEST)

    def test_rejects_changed_manifest_config_layer_or_media_type(self):
        for field, value in (("manifest_digest", "sha256:" + "f" * 64),
                             ("config_digest", "sha256:" + "f" * 64),
                             ("layers", ["sha256:" + "f" * 64]),
                             ("media_type", "application/vnd.docker.distribution.manifest.v2+json")):
            remote = candidate()
            remote[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    module.verify_remote_identity(candidate(), remote)

    def test_rejects_changed_provenance_or_wrong_platform(self):
        remote = candidate()
        remote["labels"]["org.opencontainers.image.revision"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "provenance"):
            module.verify_remote_identity(candidate(), remote)

    def test_rejects_missing_or_wrong_source_repository_label(self):
        for value in (None, "https://github.com/other/repo", "http://github.com/kunalz06/airmouse"):
            image = candidate()
            if value is None:
                del image["labels"]["org.opencontainers.image.source"]
            else:
                image["labels"]["org.opencontainers.image.source"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    module.verify_remote_identity(image, image)


class ExistingReleaseTests(unittest.TestCase):
    def test_accepts_only_provenance_matching_successful_prior_release(self):
        run = prior_release_run()
        prior = release_record()
        self.assertEqual(module.verify_existing_release(
            candidate(), [run], SHA, prior, prior_artifact(), prior_attempt()
        )["registry_manifest_digest"], MANIFEST)

    def test_rejects_existing_tag_without_prior_success_or_matching_source(self):
        with self.assertRaisesRegex(ValueError, "run/attempt not proven successful"):
            module.verify_existing_release(candidate(), [], SHA, release_record(), prior_artifact(), prior_attempt())
        remote = candidate()
        remote["labels"]["org.opencontainers.image.revision"] = "f" * 40
        run = prior_release_run()
        with self.assertRaisesRegex(ValueError, "source provenance"):
            module.verify_existing_release(remote, [run], SHA, release_record(), prior_artifact(), prior_attempt())
        remote = candidate()
        del remote["labels"]["io.nidar.mavsdk.version"]
        with self.assertRaisesRegex(ValueError, "provenance label .* missing"):
            module.verify_existing_release(remote, [run], SHA, release_record(), prior_artifact(), prior_attempt())
        remote = candidate()
        remote["platform"] = {"os": "linux", "architecture": "amd64"}
        with self.assertRaisesRegex(ValueError, "platform"):
            module.verify_remote_identity(candidate(), remote)

    def test_rejects_existing_tag_when_prior_verified_record_has_a_different_digest(self):
        run = prior_release_run()
        prior = release_record()
        prior["workflow_run_id"] = 700
        prior["registry_manifest_digest"] = "sha256:" + "9" * 64
        prior["registry_reference"] = f"ghcr.io/kunalz06/nidar-runtime@{prior['registry_manifest_digest']}"
        with self.assertRaisesRegex(ValueError, "registry image identity does not match digest"):
            module.verify_existing_release(candidate(), [run], SHA, prior, prior_artifact(), prior_attempt())


class ReleaseRecordTests(unittest.TestCase):
    def test_verified_record_requires_canonical_digest_reference(self):
        record = module.make_release_record(release_record())
        self.assertEqual(record["status"], "VERIFIED")
        self.assertEqual(record["registry_reference"].split("@", 1)[1], MANIFEST)

    def test_non_verified_records_forbid_canonical_reference(self):
        raw = release_record("BLOCKED")
        raw.update({"registry_reference": "ghcr.io/x@y", "failure_stage": "preflight"})
        with self.assertRaisesRegex(ValueError, "cannot have a usable registry reference"):
            module.make_release_record(raw)

    def test_verified_record_requires_complete_release_identity_and_test_evidence(self):
        raw = release_record()
        del raw["workflow_run_id"]
        with self.assertRaisesRegex(ValueError, "workflow_run_id"):
            module.make_release_record(raw)

    def test_failure_record_requires_explicit_null_identity_fields_and_failure_stage(self):
        raw = release_record("UNVERIFIED")
        raw.update({"registry_reference": None, "failure_stage": "post-push-remote-verification"})
        del raw["local_manifest_digest"]
        with self.assertRaisesRegex(ValueError, "explicit null"):
            module.make_release_record(raw)

    def test_idempotent_verified_record_keeps_unbuilt_local_identity_fields_null(self):
        raw = release_record()
        raw.update({"idempotent": True, "local_manifest_digest": None,
                    "local_config_digest": None, "oci_archive_sha256": None})
        raw["original_release_evidence"] = {
            "workflow_run_id": 700, "workflow_run_attempt": 2,
            "artifact_id": 987, "artifact_digest": "sha256:" + "f" * 64,
        }
        raw["current_retry_verification"] = {name: True for name in module.REQUIRED_RETRY_CHECKS}
        self.assertTrue(module.make_release_record(raw)["idempotent"])



class FailClosedPolicyTests(unittest.TestCase):
    def test_every_mandatory_original_test_and_closure_requires_boolean_true(self):
        for group, names in (("test_results", module.REQUIRED_TEST_CHECKS),
                             ("closure_checks", module.REQUIRED_CLOSURE_CHECKS)):
            for name in names:
                for value in (False, None, "true", 1):
                    with self.subTest(group=group, check=name, value=value):
                        rec = release_record()
                        rec[group][name] = value
                        with self.assertRaisesRegex(ValueError, "boolean true"):
                            module.make_release_record(rec)
                with self.subTest(group=group, check=name, value="missing"):
                    rec = release_record()
                    del rec[group][name]
                    with self.assertRaisesRegex(ValueError, "boolean true"):
                        module.make_release_record(rec)

    def test_retry_rejects_failed_original_release_gates(self):
        run = prior_release_run()
        for name in module.REQUIRED_TEST_CHECKS:
            rec = release_record()
            rec["test_results"][name] = False
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "boolean true"):
                    module.verify_existing_release(candidate(), [run], SHA, rec,
                                                   prior_artifact(), prior_attempt())

    def test_retry_requires_exact_run_attempt_artifact_and_identity(self):
        run = prior_release_run()
        variants = [
            ("run_attempt", lambda run, artifact, attempt, rec: run.update(run_attempt=3)),
            ("attempt", lambda run, artifact, attempt, rec: attempt.update(run_attempt=3)),
            ("artifact_run_id", lambda run, artifact, attempt, rec: artifact["workflow_run"].update(id=123)),
            ("artifact_sha", lambda run, artifact, attempt, rec: artifact["workflow_run"].update(head_sha="f" * 40)),
            ("artifact_digest", lambda run, artifact, attempt, rec: artifact.update(digest="sha256:invalid")),
            ("artifact_time", lambda run, artifact, attempt, rec: artifact.update(created_at="2026-10-13T11:11:40Z")),
            ("different_config", lambda run, artifact, attempt, rec: rec.update(local_config_digest="sha256:"+"9"*64)),
        ]
        for name, mutate in variants:
            with self.subTest(name=name):
                r = dict(run)
                art = prior_artifact()
                attempt = prior_attempt()
                rec = release_record()
                mutate(r, art, attempt, rec)
                with self.assertRaises(ValueError):
                    module.verify_existing_release(candidate(), [r], SHA, rec, art, attempt)

    def test_package_auth_and_visibility_fail_closed(self):
        self.assertEqual(module.classify_package(200, private_package()), "private")
        for status, data in ((200, {"visibility":"public"}), (200, {}),
                             (404, {}), (401, {}), (403, {}), (429, {}),
                             (500, {})):
            with self.subTest(status=status, body=data):
                with self.assertRaises(ValueError):
                    module.classify_package(status, data)

    def test_package_response_requires_exact_owner_identity_and_private_repository_link(self):
        for field, replacement in (
            ("name", "other-runtime"), ("name", None), ("package_type", "docker"),
            ("package_type", None), ("owner", None), ("owner", {"login": "other"}),
            ("repository", None), ("repository", {"full_name": "other/repo"}),
            ("repository", {"name": "airmouse", "full_name": "kunalz06/airmouse",
                             "private": False, "owner": {"login": "kunalz06"}}),
            ("repository", {"name": "airmouse", "full_name": "kunalz06/airmouse",
                             "private": True, "owner": {"login": "other"}}),
        ):
            with self.subTest(field=field, replacement=replacement):
                package = private_package()
                package[field] = replacement
                with self.assertRaises(ValueError):
                    module.classify_package(200, package)

    def test_package_query_never_equates_ambiguous_404_with_first_publication(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            module.classify_package(404, {"message": "Not Found"})

    def test_registry_tag_absence_requires_private_access_and_unambiguous_missing_manifest(self):
        self.assertEqual(module.classify_tag_result(False, "manifest unknown", "private"), "absent")
        self.assertEqual(module.classify_tag_result(True, "", "private"), "existing")
        for exists, text, visibility in ((False, "name unknown", "private"),
                                         (False, "unauthorized manifest unknown", "private"),
                                         (False, "TLS network failure", "private"),
                                         (False, "manifest unknown", "public")):
            with self.subTest(exists=exists, text=text, visibility=visibility):
                with self.assertRaises(ValueError):
                    module.classify_tag_result(exists, text, visibility)


class FinalWorkflowEvidenceTests(unittest.TestCase):
    def make_dir(self, d):
        def put(name, data):
            (d / ("phase-4b-" + name)).write_text(data if isinstance(data, str) else json.dumps(data))
        put("release-context.json", {"release_timestamp":"2026-10-13T10:11:12Z",
                                      "source_timestamp":"2026-10-13T10:10:10Z"})
        put("build.timestamp", "2026-10-13T10:11:11Z")
        put("lock.digest", "sha256:"+"f"*64)
        put("archive.digest", "sha256:"+"e"*64)
        put("registry-visibility", "private")
        put("candidate.json", candidate())
        put("remote.json", candidate())
        put("remote-verification.json", {"registry_manifest_digest":MANIFEST})
        put("publication-attempted", "")
        put("postpull-tests-passed", "")
        put("apt-closure-passed", "")
        put("runtime-manifest-passed", "")
        for name in module.REQUIRED_TEST_CHECKS:
            put("check-"+name, "")
        return put

    def test_entire_original_release_must_have_all_true_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            self.make_dir(d)
            record, ok = module.create_workflow_record(d, SHA, 701, 1, True, True)
            self.assertTrue(ok)
            self.assertEqual(record["status"], "VERIFIED")
            (d / "phase-4b-check-command_boundary").unlink()
            record, ok = module.create_workflow_record(d, SHA, 701, 1, True, True)
            self.assertFalse(ok)
            self.assertEqual(record["status"], "UNVERIFIED")
            self.assertIsNone(record["registry_reference"])

    def test_postpull_marker_alone_cannot_override_prior_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            self.make_dir(d)
            record, ok = module.create_workflow_record(d, SHA, 701, 1, False, True)
            self.assertFalse(ok)
            self.assertEqual(record["status"], "UNVERIFIED")
            self.assertIsNone(record["registry_reference"])

    def test_missing_privacy_and_malformed_remote_block_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            self.make_dir(d)
            (d / "phase-4b-remote.json").write_text("{broken")
            record, ok = module.create_workflow_record(d, SHA, 701, 1, True, True)
            self.assertFalse(ok)
            self.assertEqual(record["failure_stage"], "final-record-validation")
            self.assertEqual(record["status"], "UNVERIFIED")

    def test_idempotent_release_separates_original_evidence_from_current_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            put = self.make_dir(d)
            (d / "phase-4b-publication-attempted").unlink()
            original = release_record()
            evidence = module.verify_existing_release(candidate(), [prior_release_run()],
                SHA, original, prior_artifact(), prior_attempt())
            put("prior-release-record.json", original)
            put("existing-remote.json", candidate())
            put("idempotent-verification.json", evidence)
            record, ok = module.create_workflow_record(d, SHA, 701, 1, True, True)
            self.assertTrue(ok)
            self.assertTrue(record["idempotent"])
            self.assertIsNone(record["local_manifest_digest"])
            self.assertIsNotNone(record["original_release_evidence"])
            self.assertTrue(all(record["current_retry_verification"].values()))
            (d / "phase-4b-check-digest_pull_execution").unlink()
            record, ok = module.create_workflow_record(d, SHA, 701, 1, True, True)
            self.assertFalse(ok)
            self.assertEqual(record["status"], "BLOCKED")

    def test_failed_or_pending_evidence_upload_cannot_issue_verified_record(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            self.make_dir(d)
            record, ok = module.create_workflow_record(d, SHA, 701, 1, True, False)
            self.assertFalse(ok)
            self.assertEqual(record["status"], "UNVERIFIED")
            self.assertIsNone(record["registry_reference"])
            self.assertEqual(record["failure_stage"], "evidence-upload")

if __name__ == "__main__":
    unittest.main()
