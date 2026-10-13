#!/usr/bin/env python3
"""Static safety contract for the manual Phase 4B GHCR release workflow."""
from pathlib import Path
import re
import subprocess
import unittest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/release-runtime-arm64.yml"
BUILD = ROOT / "scripts/build-runtime-arm64.sh"
BUILD_WORKFLOW = ROOT / ".github/workflows/build-test.yml"
BOOTSTRAP_WORKFLOW = ROOT / ".github/workflows/bootstrap-private-ghcr.yml"
DEPLOYMENT = ROOT / "docs/DEPLOYMENT.md"
TASKS = ROOT / "docs/TASKS.md"
PROGRESS = ROOT / "docs/PROGRESS.md"


class ReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()

    def test_arm64_pr_build_uses_exact_checked_out_head_as_provenance(self):
        workflow = yaml.load(BUILD_WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        steps = workflow["jobs"]["arm64-runtime"]["steps"]
        by_name = {step.get("name"): step for step in steps}
        source_expr = "${{ github.event.pull_request.head.sha || github.sha }}"
        checkout = next(step for step in steps if "uses" in step and "checkout" in step["uses"])
        self.assertEqual(checkout["with"]["ref"], source_expr)
        self.assertIn('git rev-parse HEAD', by_name["Capture unique CI build identity once"]["run"])
        for name in ("Build, load, and export the same linux/arm64 runtime once",
                     "Record immutable manifest from the single build output"):
            with self.subTest(name=name):
                script = by_name[name]["run"]
                self.assertIn("GITHUB_SHA='" + source_expr + "'", script)

    def test_manual_main_only_and_least_privilege_permissions(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("\n  push:", self.text)
        self.assertIn("refs/heads/main", self.text)
        self.assertRegex(self.text, r"permissions:\n\s+contents: read\n\s+actions: read\n\s+packages: write")
        self.assertNotIn("contents: write", self.text)

    def test_identity_and_ci_preflight_are_fail_closed(self):
        for required in ("git status --porcelain", "git rev-parse HEAD", "git ls-remote origin refs/heads/main",
                         "verify-runtime-release.py verify-ci", "GITHUB_SHA", "GITHUB_REF"):
            self.assertIn(required, self.text)
        self.assertIn("concurrency:", self.text)
        self.assertIn("github.sha", self.text)

    def test_pinned_actions_and_skopeo_transport_are_immutable(self):
        actions = re.findall(r"uses:\s+[^\s@]+@([^\s#]+)", self.text)
        self.assertGreaterEqual(len(actions), 3)
        for revision in actions:
            self.assertRegex(revision, r"^[0-9a-f]{40}$")
        self.assertRegex(self.text, r"quay\.io/skopeo/stable@sha256:[0-9a-f]{64}")
        self.assertNotRegex(self.text, r":latest(?:\s|$)")
        self.assertIn("--preserve-digests", self.text)
        self.assertIn("--digestfile", self.text)
        self.assertIn("--override-os linux", self.text)
        self.assertIn("--override-arch arm64", self.text)

    def test_verifies_once_before_publication_and_never_runs_dev_cli_test(self):
        copy_offset = self.text.index("skopeo copy")
        for required in ("scripts/build-runtime-arm64.sh --load", "test_runtime_arm64_artifact.sh",
                         "test_runtime_arm64_execution.sh", "test_runtime_image_policy.sh",
                         "verify-runtime-apt-closure.py", "record-runtime-manifest.py",
                         "test_mavsdk_boundary.sh"):
            self.assertLess(self.text.index(required), copy_offset, required)
        self.assertNotIn("test_nidar_flight_cli.sh", self.text)
        self.assertIn("--image-ref nidar-runtime:phase-4b-release", self.text)
        self.assertIn("--output build/release/nidar-runtime-arm64.oci.tar", self.text)
        self.assertIn("--load", BUILD.read_text())

    def test_protects_immutable_tag_and_reverifies_digest_pulled_private_image(self):
        self.assertGreaterEqual(self.text.count("skopeo inspect"), 2)
        self.assertIn("docker login ghcr.io --username", self.text)
        self.assertIn("--password-stdin", self.text)
        self.assertIn("docker pull \"${registry_reference}\"", self.text)
        pull_offset = self.text.index("docker pull \"${registry_reference}\"")
        self.assertLess(self.text.index("skopeo copy"), pull_offset)
        for required in ("test_runtime_arm64_artifact.sh \"${registry_reference}\"",
                         "test_runtime_arm64_execution.sh \"${registry_reference}\"",
                         "test_runtime_image_policy.sh \"${registry_reference}\""):
            self.assertGreater(self.text.index(required), pull_offset)

    def test_privacy_is_checked_before_any_registry_write(self):
        copy_offset = self.text.index("skopeo copy")
        privacy_offset = self.text.index("scripts/verify-runtime-release.py check-package")
        self.assertLess(privacy_offset, copy_offset)
        self.assertNotIn("visibility=public", self.text)
        self.assertIn("/user/packages/container/nidar-runtime", self.text)
        self.assertIn("a 404 is ambiguous", self.text.lower())

    def test_existing_tag_is_only_accepted_after_idempotent_evidence_verification(self):
        self.assertIn("verify-existing-release", self.text)
        self.assertIn("idempotent verified release", self.text)
        self.assertIn("phase-4b-existing-release-evidence.json", self.text)
        self.assertIn("phase-4b-prior-release-record.json", self.text)
        self.assertIn("/artifacts", self.text)
        self.assertIn('for prior_run_id in "${prior_run_ids[@]}"', self.text)
        self.assertNotIn('test "${#prior_run_ids[@]}" = 1', self.text)

    def test_registry_credentials_are_isolated_and_never_expanded_in_command_arguments(self):
        self.assertIn("DOCKER_CONFIG=\"$(mktemp -d)\"", self.text)
        self.assertRegex(self.text, r"curl(?:\s+--\S+)*\s+--config \"\$github_api_config\"")
        self.assertNotRegex(self.text, r'--header "Authorization: Bearer \$\{?GITHUB_TOKEN\}?"')

    def test_failure_record_captures_identity_nulls_stage_and_test_results(self):
        verifier = (ROOT / "scripts/verify-runtime-release.py").read_text()
        for required in ("failure_stage", "local_manifest_digest", "local_config_digest",
                         "oci_archive_sha256", "workflow_run_id", "test_results",
                         "current_retry_verification", "original_release_evidence"):
            self.assertIn(required, verifier)
        self.assertIn("finalize-workflow", self.text)
        self.assertIn("NIDAR_PRIOR_STEPS_SUCCESS", self.text)
        self.assertIn("job.status == 'success'", self.text)
        self.assertIn("phase-4b-postpull-tests-passed", self.text)
        self.assertLess(self.text.index("printf '%s\\n' preflight > build/release/phase-4b-stage"),
                        self.text.index('test -z "$(git status --porcelain)"'))
        for required in ("phase-4b-apt-closure-passed", "phase-4b-runtime-manifest-passed"):
            self.assertIn(required, self.text)

    def test_failure_evidence_always_uploads_without_releasing_secrets_or_public_visibility(self):
        self.assertRegex(self.text, r"if:\s+always\(\)")
        self.assertIn("actions/upload-artifact@", self.text)
        self.assertIn("retention-days: 90", self.text)
        self.assertIn("phase-4b-runtime-release-diagnostics", self.text)
        self.assertIn("phase-4b-provisional-record.json", self.text)
        self.assertNotIn("visibility=public", self.text)
        self.assertNotIn("packages: read", self.text)

    def test_embedded_bash_scripts_have_valid_syntax(self):
        lines = self.text.splitlines()
        blocks = []
        for i, line in enumerate(lines):
            if line != "        run: |":
                continue
            body = []
            for subsequent in lines[i + 1:]:
                if subsequent.strip() and not subsequent.startswith("          "):
                    break
                body.append(subsequent[10:] if subsequent.startswith("          ") else "")
            blocks.append("\n".join(body) + "\n")
        self.assertGreaterEqual(len(blocks), 7)
        for index, block in enumerate(blocks):
            with self.subTest(step=index):
                result = subprocess.run(["bash", "-n"], input=block, text=True,
                                        capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_does_not_follow_authenticated_redirects_to_untrusted_hosts(self):
        self.assertNotIn('--location --config "$github_api_config"', self.text)
        self.assertIn("untrusted signed artifact download endpoint", self.text)
        self.assertIn('--config "$signed_url_config"', self.text)
        self.assertIn('unexpected Actions API pagination host/path', self.text)

    def test_finalizer_is_only_authority_for_verified_release(self):
        workflow = yaml.load(self.text, Loader=yaml.BaseLoader)
        steps = workflow["jobs"]["release"]["steps"]
        names = [step.get("name", "") for step in steps]
        provisional = names.index("Prepare provisional status and failure evidence")
        diagnostics = names.index("Upload Phase 4B diagnostic evidence")
        final_record = names.index("Generate final release record")
        final_upload = names.index("Upload Phase 4B release evidence")
        approval = names.index("Confirm evidence upload before release summary")
        self.assertLess(provisional, diagnostics)
        self.assertLess(diagnostics, final_record)
        self.assertLess(final_record, final_upload)
        self.assertLess(final_upload, approval)
        self.assertEqual(steps[provisional]["if"], "always()")
        self.assertEqual(steps[diagnostics]["if"], "always()")
        self.assertEqual(steps[final_record]["if"], "success()")
        self.assertEqual(steps[final_upload]["if"], "success()")
        self.assertEqual(steps[approval]["if"], "always()")
        self.assertIn("steps.final_evidence.outcome == 'success'", steps[approval]["env"]["NIDAR_FINAL_UPLOAD_SUCCESS"])
        self.assertIn('--evidence-upload-success false', steps[provisional]["run"])
        self.assertIn('--evidence-upload-success true', steps[final_record]["run"])
        self.assertNotIn("GITHUB_STEP_SUMMARY", steps[final_record]["run"])
        self.assertIn("GITHUB_STEP_SUMMARY", steps[approval]["run"])
        failure_branch = steps[approval]["run"].split("else\n", 1)[1]
        self.assertLess(failure_branch.index("rm -f build/release/phase-4b-release-record.json"),
                        failure_branch.index("cat build/release/phase-4b-release-record.json"))

    def test_uploaded_release_evidence_excludes_raw_api_responses(self):
        workflow = yaml.load(self.text, Loader=yaml.BaseLoader)
        steps = workflow["jobs"]["release"]["steps"]
        upload = next(step for step in steps if step.get("name") == "Upload Phase 4B release evidence")
        paths = upload["with"]["path"].splitlines()
        self.assertIn("build/release/phase-4b-release-record.json", paths)
        self.assertNotIn("build/release/phase-4b-*.json", paths)
        for raw in ("phase-4b-package.json", "phase-4b-prior-artifact.json",
                    "phase-4b-prior-attempt.json", "phase-4b-existing-release-runs.json"):
            self.assertFalse(any(path.endswith(raw) for path in paths), raw)

    def test_release_documentation_requires_actual_workflow_evidence_and_private_pull_authentication(self):
        deployment = DEPLOYMENT.read_text()
        tasks = TASKS.read_text()
        progress = PROGRESS.read_text()
        for required in ("release-runtime-arm64", "GitHub Actions artifact", "private", "authenticated",
                         "telemetry-only", "no hardware", "VERIFIED", "UNVERIFIED", "BLOCKED"):
            self.assertIn(required, deployment)
        self.assertIn("Phase 4B", tasks)
        self.assertIn("release workflow", progress)
        self.assertIn("separate authorized documentation", " ".join(deployment.split()))
        self.assertNotRegex(deployment + tasks + progress,
                            r"ghcr\.io/kunalz06/nidar-runtime@sha256:[0-9a-f]{64}")


class GatePreparationTests(unittest.TestCase):
    def test_build_test_lints_checked_out_pr_head_with_pinned_actionlint(self):
        workflow = yaml.load(BUILD_WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        jobs = workflow["jobs"]
        self.assertIn("workflow-lint", jobs)
        lint = jobs["workflow-lint"]
        self.assertEqual(lint["permissions"], {"contents": "read"})
        steps = lint["steps"]
        checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["ref"], "${{ github.event.pull_request.head.sha || github.sha }}")
        run = "\n".join(step.get("run", "") for step in steps)
        self.assertIn('test "$(git rev-parse HEAD)" = "$NIDAR_SOURCE_SHA"', run)
        self.assertIn("rhysd/actionlint@sha256:9d36088643581e728c969f35141f88139fec77280b2be23c1f66f8e40e1025e7", run)
        self.assertIn("--network=none", run)
        self.assertIn("--read-only", run)
        self.assertIn("--cap-drop=ALL", run)
        self.assertIn(":/repo:ro", run)
        for job_name in ("amd64", "sitl", "arm64-runtime"):
            checkout = next(step for step in jobs[job_name]["steps"]
                            if step.get("uses", "").startswith("actions/checkout@"))
            self.assertEqual(checkout["with"]["ref"], "${{ github.event.pull_request.head.sha || github.sha }}")

    def test_bootstrap_is_manual_confirmed_and_cannot_create_runtime_tag(self):
        self.assertTrue(BOOTSTRAP_WORKFLOW.exists(), "manual GHCR bootstrap workflow is missing")
        workflow = yaml.load(BOOTSTRAP_WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read", "packages": "write"})
        self.assertEqual(workflow["concurrency"]["cancel-in-progress"], "false")
        dispatch = workflow["on"]["workflow_dispatch"]
        self.assertEqual(dispatch["inputs"]["confirm_private_package_bootstrap"]["required"], "true")
        job = workflow["jobs"]["bootstrap"]
        self.assertIn("refs/heads/main", job["if"])
        self.assertIn("workflow_dispatch", job["if"])
        run = "\n".join(step.get("run", "") for step in job["steps"])
        self.assertIn("owner verifies the package is absent", dispatch["inputs"]["confirm_private_package_bootstrap"]["description"])
        self.assertNotIn("or inaccessible", dispatch["inputs"]["confirm_private_package_bootstrap"]["description"])
        self.assertIn("BOOTSTRAP_PRIVATE_NIDAR_RUNTIME", run)
        self.assertIn("bootstrap-sentinel-", run)
        self.assertNotIn(":sha-${", run)
        self.assertIn("FROM scratch", run)
        self.assertIn("org.opencontainers.image.source=https://github.com/kunalz06/airmouse", run)
        self.assertIn("scripts/verify-runtime-release.py check-package", run)
        self.assertGreaterEqual(run.count("scripts/verify-runtime-release.py check-package"), 2)
        self.assertLess(run.index("scripts/verify-runtime-release.py check-package"), run.index("docker push"))
        self.assertIn("owner must establish private package access manually", run)
        self.assertIn("verify-bootstrap-remote", run)
        self.assertIn("sentinel_reference", run)
        self.assertLess(run.index("verify-bootstrap-remote"), run.index("BOOTSTRAP_PACKAGE_READY"))
        self.assertIn("/user/packages/container/nidar-runtime", run)
        self.assertIn("--password-stdin", run)
        upload = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@"))
        self.assertEqual(upload["if"], "always()")
        self.assertEqual(upload["with"]["path"], "build/bootstrap/evidence.json")
        self.assertNotIn("package.json", upload["with"]["path"])


if __name__ == "__main__":
    unittest.main()
