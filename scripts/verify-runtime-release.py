#!/usr/bin/env python3
"""Fail-closed verification for a digest-preserving Phase 4B runtime release."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


REQUIRED_JOBS = {"amd64", "sitl", "arm64-runtime"}
PROVENANCE_LABELS = {
    "org.opencontainers.image.revision",
    "org.opencontainers.image.source",
    "org.opencontainers.image.base.digest",
    "io.nidar.mavsdk.version",
    "io.nidar.mavsdk.source-commit",
    "io.nidar.target.architecture",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RELEASE_IDENTITY_FIELDS = (
    "local_manifest_digest", "local_config_digest", "oci_archive_sha256",
    "lock_sha256", "registry_manifest_digest", "observed_registry_digest",
    "registry_visibility", "registry_reference", "failure_stage", "failure_reason",
    "source_timestamp", "build_timestamp",
)


def require_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError(f"{field} must be an exact 40-character lowercase Git SHA")
    return value


def require_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise ValueError(f"{field} must be a sha256 digest")
    return value


def successful_required_jobs(payload: object) -> set[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("required workflow jobs response is invalid")
    return {
        job.get("name") for job in payload["jobs"]
        if isinstance(job, dict) and job.get("status") == "completed"
        and job.get("conclusion") == "success" and isinstance(job.get("name"), str)
    }


def validate_ci_evidence(run_pages: list[dict], jobs_by_run: dict, expected_sha: str,
                         current_main_sha: str) -> dict:
    """Return the only valid successful main push run, or raise ValueError."""
    expected_sha = require_sha(expected_sha, "expected source SHA")
    current_main_sha = require_sha(current_main_sha, "current main SHA")
    if current_main_sha != expected_sha:
        raise ValueError("current main SHA differs from expected source SHA")
    candidates = []
    for page in run_pages:
        if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
            raise ValueError("workflow-runs response is invalid")
        for run in page["workflow_runs"]:
            if not isinstance(run, dict):
                raise ValueError("workflow run is invalid")
            if (run.get("name") == "build-test" and run.get("head_sha") == expected_sha
                    and run.get("head_branch") == "main" and run.get("event") == "push"
                    and run.get("status") == "completed" and run.get("conclusion") == "success"):
                candidates.append(run)
    if not candidates:
        raise ValueError("no successful exact-SHA main push build-test run")
    if len(candidates) != 1:
        raise ValueError("ambiguous successful exact-SHA main push build-test runs")
    run = candidates[0]
    run_id = run.get("id")
    if not isinstance(run_id, int) or run_id < 1:
        raise ValueError("workflow run has invalid id")
    names = successful_required_jobs(jobs_by_run.get(run_id))
    missing = REQUIRED_JOBS - names
    if missing:
        raise ValueError(f"missing successful required jobs: {', '.join(sorted(missing))}")
    attempt = run.get("run_attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise ValueError("workflow run has invalid attempt")
    return {"run_id": run_id, "run_attempt": attempt, "source_git_commit": expected_sha}


def validate_platform(payload: dict, side: str) -> None:
    platform = payload.get("platform")
    if platform != {"os": "linux", "architecture": "arm64"}:
        raise ValueError(f"{side} platform is not linux/arm64")


def verify_remote_identity(candidate: dict, remote: dict) -> str:
    """Ensure an OCI archive transfer preserved the selected ARM64 image exactly."""
    if not isinstance(candidate, dict) or not isinstance(remote, dict):
        raise ValueError("candidate and remote identity must be objects")
    validate_platform(candidate, "candidate")
    validate_platform(remote, "remote")
    for field in ("manifest_digest", "config_digest"):
        require_digest(candidate.get(field), f"candidate {field}")
        require_digest(remote.get(field), f"remote {field}")
    for field in ("manifest_digest", "config_digest", "layers", "media_type"):
        if candidate.get(field) != remote.get(field):
            raise ValueError(f"identity differs for {field}")
    if not isinstance(candidate.get("layers"), list) or not candidate["layers"]:
        raise ValueError("candidate layers are invalid")
    for layer in candidate["layers"]:
        require_digest(layer, "candidate layer")
    candidate_labels = candidate.get("labels")
    remote_labels = remote.get("labels")
    if not isinstance(candidate_labels, dict) or not isinstance(remote_labels, dict):
        raise ValueError("provenance labels are invalid")
    for name in PROVENANCE_LABELS:
        if not isinstance(candidate_labels.get(name), str) or candidate_labels.get(name) != remote_labels.get(name):
            raise ValueError(f"provenance differs for {name}")
    require_sha(candidate_labels["org.opencontainers.image.revision"], "candidate source revision")
    if candidate_labels["org.opencontainers.image.source"] != "https://github.com/kunalz06/airmouse":
        raise ValueError("candidate source repository label is invalid")
    if candidate_labels["io.nidar.target.architecture"] != "linux/arm64":
        raise ValueError("candidate provenance target architecture is invalid")
    return candidate["manifest_digest"]


REQUIRED_CLOSURE_CHECKS = ("apt_closure", "runtime_manifest")
REQUIRED_TEST_CHECKS = (
    "telemetry_patch", "command_boundary", "arm64_artifact",
    "bounded_execution", "image_policy", "remote_identity",
    "digest_pull_artifact", "digest_pull_execution",
    "digest_pull_image_policy", "private_visibility",
)
REQUIRED_RETRY_CHECKS = (
    "digest_pull_artifact", "digest_pull_execution",
    "digest_pull_image_policy", "private_visibility",
)


def require_true_checks(value: object, names: tuple[str, ...], field: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a check results object")
    for name in names:
        if name not in value or type(value[name]) is not bool or not value[name]:
            raise ValueError(f"{field}.{name} must be boolean true")


def require_remote_identity(remote: object, source_sha: str) -> dict:
    if not isinstance(remote, dict):
        raise ValueError("registry image identity must be an object")
    validate_platform(remote, "registry")
    for field in ("manifest_digest", "config_digest"):
        require_digest(remote.get(field), f"registry {field}")
    if not isinstance(remote.get("layers"), list) or not remote["layers"]:
        raise ValueError("registry layers must be nonempty")
    for layer in remote["layers"]:
        require_digest(layer, "registry layer")
    if not isinstance(remote.get("media_type"), str) or not remote["media_type"]:
        raise ValueError("registry media_type must be nonempty")
    labels = remote.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("registry labels must be an object")
    for field in PROVENANCE_LABELS:
        if not isinstance(labels.get(field), str) or not labels[field]:
            raise ValueError(f"registry provenance label {field} missing")
    if labels["org.opencontainers.image.revision"] != source_sha:
        raise ValueError("registry source provenance differs from requested source")
    if labels["org.opencontainers.image.source"] != "https://github.com/kunalz06/airmouse":
        raise ValueError("registry source repository label is invalid")
    if labels["io.nidar.target.architecture"] != "linux/arm64":
        raise ValueError("registry target architecture does not match linux/arm64")
    if labels["io.nidar.mavsdk.version"] != "3.17.2":
        raise ValueError("registry MAVSDK version is not pinned 3.17.2")
    require_sha(labels["io.nidar.mavsdk.source-commit"], "MAVSDK source commit")
    require_digest(labels["org.opencontainers.image.base.digest"], "runtime base digest")
    return remote


def classify_package(status: int, data: object) -> str:
    """Require authenticated visibility, never mistake a hidden 404 for absence."""
    if status == 200:
        if not isinstance(data, dict) or data.get("name") != "nidar-runtime" or data.get("package_type") != "container":
            raise ValueError("GHCR package identity is not the expected container package")
        owner = data.get("owner")
        if not isinstance(owner, dict) or owner.get("login") != "kunalz06":
            raise ValueError("GHCR package owner is not kunalz06")
        repository = data.get("repository")
        if (not isinstance(repository, dict) or repository.get("name") != "airmouse" or
                repository.get("full_name") != "kunalz06/airmouse" or repository.get("private") is not True or
                not isinstance(repository.get("owner"), dict) or repository["owner"].get("login") != "kunalz06"):
            raise ValueError("GHCR package is not linked to the expected private repository")
        if data.get("visibility") != "private":
            raise ValueError("GHCR package visibility is not private")
        return "private"
    if status == 404:
        raise ValueError("GHCR package 404 is ambiguous: private package may be hidden; owner must configure explicit private package access before publishing")
    raise ValueError(f"GHCR package access not verified (HTTP {status})")


def verify_bootstrap_remote(tagged: object, by_digest: object,
                            source_sha: str, sentinel_tag: str) -> dict:
    """Bind a bootstrap sentinel to a digest and exact remote provenance."""
    source_sha = require_sha(source_sha, "bootstrap source SHA")
    if not re.fullmatch(
            rf"ghcr\.io/kunalz06/nidar-runtime:bootstrap-sentinel-[1-9][0-9]*-[1-9][0-9]*-{source_sha}",
            sentinel_tag):
        raise ValueError("bootstrap tag does not match unique source provenance")
    digest = None
    for name, inspection in (("tagged", tagged), ("digest-qualified", by_digest)):
        if not isinstance(inspection, dict):
            raise ValueError(f"{name} bootstrap inspection must be an object")
        observed = require_digest(inspection.get("Digest"), f"{name} bootstrap manifest digest")
        if digest is None:
            digest = observed
        elif observed != digest:
            raise ValueError("bootstrap tag and digest-qualified inspection differ")
        if inspection.get("Name") != "ghcr.io/kunalz06/nidar-runtime":
            raise ValueError(f"{name} bootstrap package name is invalid")
        if inspection.get("Os") != "linux" or inspection.get("Architecture") != "amd64":
            raise ValueError(f"{name} bootstrap platform is invalid")
        labels = inspection.get("Labels")
        if not isinstance(labels, dict) or (
                labels.get("org.opencontainers.image.source") != "https://github.com/kunalz06/airmouse" or
                labels.get("org.opencontainers.image.revision") != source_sha or
                labels.get("io.nidar.artifact.kind") != "bootstrap-sentinel"):
            raise ValueError(f"{name} bootstrap source or kind label is invalid")
    return {
        "sentinel_tag": sentinel_tag,
        "sentinel_reference": f"ghcr.io/kunalz06/nidar-runtime@{digest}",
        "manifest_digest": digest,
        "source_sha": source_sha,
        "labels_verified": True,
    }


def classify_tag_result(tag_exists: bool, diagnostic: str, package_visibility: str) -> str:
    if package_visibility != "private":
        raise ValueError("private GHCR package access must be proven before checking tag")
    if tag_exists:
        return "existing"
    # Skopeo's exact MANIFEST_UNKNOWN indicates missing manifest; other
    # failures, including unauthorized and name unknown, are not absence.
    if re.search(r"(?i)(unauthori[sz]ed|denied|forbidden|timeout|connection|tls|401|403|429|rate.limit|network)", diagnostic):
        raise ValueError("registry diagnostic includes authentication or transport failure")
    if re.search(r"(?i)(?:manifest unknown|manifest_unknown)", diagnostic):
        return "absent"
    raise ValueError("tag absence is unproven; registry inspection failed")


def make_release_record(raw: dict) -> dict:
    """Fail closed on the exact set of applicable release-safety gates."""
    if not isinstance(raw, dict):
        raise ValueError("release record must be an object")
    record = dict(raw)
    record["schema"] = "nidar.phase4b.runtime-release.v2"
    status = record.get("status")
    if status not in ("VERIFIED", "UNVERIFIED", "BLOCKED"):
        raise ValueError("release status must be VERIFIED, UNVERIFIED, or BLOCKED")
    source_sha = require_sha(record.get("source_git_commit"), "source_git_commit")
    if record.get("source_repository") != "kunalz06/airmouse":
        raise ValueError("release source_repository is not the authorized repo")
    for field in ("workflow_run_id", "workflow_run_attempt"):
        if type(record.get(field)) is not int or record[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    for field in ("release_timestamp",):
        if not isinstance(record.get(field), str) or not TIMESTAMP_RE.fullmatch(record[field]):
            raise ValueError(f"{field} must be canonical UTC seconds")
    if record.get("platform") != {"os": "linux", "architecture": "arm64"}:
        raise ValueError("platform must be linux/arm64")
    if type(record.get("idempotent")) is not bool:
        raise ValueError("idempotent must be a Boolean")
    for field in RELEASE_IDENTITY_FIELDS:
        if field not in record:
            raise ValueError(f"{field} requires explicit null when unavailable")
    for field in ("test_results", "closure_checks", "current_retry_verification", "original_release_evidence", "registry_image_identity"):
        if field not in record:
            raise ValueError(f"{field} requires explicit null when unavailable")
    if status == "VERIFIED":
        digest = require_digest(record.get("registry_manifest_digest"), "registry_manifest_digest")
        if record.get("registry_reference") != f"ghcr.io/kunalz06/nidar-runtime@{digest}":
            raise ValueError("VERIFIED record requires exact digest-qualified reference")
        for field in ("lock_sha256",):
            require_digest(record.get(field), field)
        if record.get("registry_visibility") != "private":
            raise ValueError("VERIFIED record requires proven private visibility")
        for field in ("source_timestamp", "build_timestamp"):
            if not isinstance(record.get(field), str) or not TIMESTAMP_RE.fullmatch(record[field]):
                raise ValueError(f"VERIFIED record requires {field}")
        from datetime import datetime
        try:
            times = [datetime.fromisoformat(record[key].replace("Z", "+00:00")) for key in
                     ("source_timestamp", "build_timestamp", "release_timestamp")]
        except ValueError as error:
            raise ValueError("release timestamps are not real UTC dates") from error
        if not (times[0] <= times[1] <= times[2]):
            raise ValueError("release timestamps are not in chronological order")
        if record.get("failure_stage") is not None or record.get("failure_reason") is not None:
            raise ValueError("VERIFIED record cannot contain failure diagnostics")
        require_remote_identity(record.get("registry_image_identity"), source_sha)
        if record["registry_image_identity"]["manifest_digest"] != digest:
            raise ValueError("VERIFIED record registry image identity does not match digest")
        require_true_checks(record.get("closure_checks"), REQUIRED_CLOSURE_CHECKS, "closure_checks")
        require_true_checks(record.get("test_results"), REQUIRED_TEST_CHECKS, "test_results")
        if record["idempotent"]:
            for field in ("local_manifest_digest", "local_config_digest", "oci_archive_sha256"):
                if record.get(field) is not None:
                    raise ValueError(f"retry must leave local unbuilt identity {field} null")
            original = record.get("original_release_evidence")
            if not isinstance(original, dict):
                raise ValueError("idempotent retry requires original release evidence")
            for field in ("workflow_run_id", "workflow_run_attempt", "artifact_id", "artifact_digest"):
                if field not in original:
                    raise ValueError(f"original_release_evidence.{field} missing")
            for field in ("workflow_run_id", "workflow_run_attempt", "artifact_id"):
                if type(original[field]) is not int or original[field] <= 0:
                    raise ValueError(f"original_release_evidence.{field} invalid")
            require_digest(original["artifact_digest"], "original artifact_digest")
            require_true_checks(record.get("current_retry_verification"), REQUIRED_RETRY_CHECKS, "current_retry_verification")
        else:
            for field in ("local_manifest_digest", "local_config_digest", "oci_archive_sha256"):
                require_digest(record.get(field), field)
            if record["local_manifest_digest"] != digest:
                raise ValueError("local and remote image manifest digests differ")
            if record["local_config_digest"] != record["registry_image_identity"]["config_digest"]:
                raise ValueError("local and remote config digests differ")
            if record.get("original_release_evidence") is not None or record.get("current_retry_verification") is not None:
                raise ValueError("new release cannot claim retry/original evidence")
    else:
        if record.get("registry_reference"):
            raise ValueError("non-VERIFIED record cannot have a usable registry reference")
        if not isinstance(record.get("failure_stage"), str) or not record["failure_stage"]:
            raise ValueError("non-VERIFIED record requires failure_stage")
        if not isinstance(record.get("failure_reason"), str) or not record["failure_reason"]:
            raise ValueError("non-VERIFIED record requires failure_reason")
    return record


def verify_existing_release(remote: dict, evidence: list[dict], source_sha: str,
                            prior_record: dict, prior_artifact: dict, attempt_evidence: dict) -> dict:
    """Bind successful original release, attempt, artifact, and OCI identities."""
    source_sha = require_sha(source_sha, "source_git_commit")
    require_remote_identity(remote, source_sha)
    prior = make_release_record(prior_record)
    if prior["status"] != "VERIFIED" or prior["idempotent"]:
        raise ValueError("prior record must be original VERIFIED publication")
    if prior["source_git_commit"] != source_sha or prior["registry_manifest_digest"] != remote["manifest_digest"]:
        raise ValueError("prior release source or manifest digest does not match")
    if prior["registry_image_identity"] != remote:
        raise ValueError("prior registry config/layers/provenance do not match")
    if not isinstance(evidence, list):
        raise ValueError("release workflow evidence must be a list")
    matched = [run for run in evidence if isinstance(run, dict)
               and run.get("name") == "release-runtime-arm64"
               and run.get("head_sha") == source_sha and run.get("head_branch") == "main"
               and run.get("event") == "workflow_dispatch"
               and run.get("status") == "completed" and run.get("conclusion") == "success"
               and run.get("id") == prior["workflow_run_id"]
               and run.get("run_attempt") == prior["workflow_run_attempt"]]
    if len(matched) != 1:
        raise ValueError("prior release workflow run/attempt not proven successful")
    if not isinstance(prior_artifact, dict) or prior_artifact.get("name") != "phase-4b-runtime-release-evidence":
        raise ValueError("prior artifact metadata missing or wrong artifact")
    for field in ("id",):
        if type(prior_artifact.get(field)) is not int or prior_artifact[field] <= 0:
            raise ValueError("prior artifact ID missing or invalid")
    require_digest(prior_artifact.get("digest"), "prior artifact digest")
    workflow_run = prior_artifact.get("workflow_run")
    if not isinstance(workflow_run, dict) or workflow_run.get("id") != prior["workflow_run_id"] or workflow_run.get("head_sha") != source_sha:
        raise ValueError("prior artifact does not bind to exact workflow run and source")
    # GitHub artifact metadata does not identify a run attempt. Require the
    # authoritative attempt-specific run endpoint and an artifact creation time
    # in the completed attempt's window. Unknown metadata blocks the retry.
    if not isinstance(attempt_evidence, dict):
        raise ValueError("prior attempt metadata is missing")
    for field, expected in (("id", prior["workflow_run_id"]),
                            ("run_attempt", prior["workflow_run_attempt"]),
                            ("head_sha", source_sha),
                            ("event", "workflow_dispatch"),
                            ("conclusion", "success"),
                            ("status", "completed")):
        if attempt_evidence.get(field) != expected:
            raise ValueError(f"prior attempt {field} not trustworthy")
    def parse_time(value: object, name: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{name} missing")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{name} invalid") from error
        if parsed.tzinfo is None:
            raise ValueError(f"{name} not timezone-qualified")
        return parsed.astimezone(timezone.utc)
    began = parse_time(attempt_evidence.get("run_started_at"), "prior run_start")
    ended = parse_time(attempt_evidence.get("updated_at"), "prior run_end")
    created = parse_time(prior_artifact.get("created_at"), "prior artifact creation")
    if not (began <= created <= ended):
        raise ValueError("prior artifact is not bound to successful run attempt time window")
    return {
        "registry_manifest_digest": remote["manifest_digest"],
        "idempotent": True,
        "original_release_evidence": {
            "workflow_run_id": prior["workflow_run_id"],
            "workflow_run_attempt": prior["workflow_run_attempt"],
            "artifact_id": prior_artifact["id"],
            "artifact_digest": prior_artifact["digest"],
        },
    }


def create_workflow_record(release_dir: Path, source_sha: str, run_id: int,
                           run_attempt: int, prior_steps_success: bool,
                           evidence_upload_success: bool) -> tuple[dict, bool]:
    """Assemble execution evidence from CI step outputs, never inferred success."""
    from datetime import datetime, timezone

    def read_json(filename: str) -> dict:
        f = release_dir / filename
        if not f.is_file():
            return {}
        try:
            data = json.loads(f.read_text())
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return {}

    def file_value(filename: str) -> str | None:
        path = release_dir / filename
        if not path.is_file():
            return None
        value = path.read_text().strip()
        return value if value else None

    def flag(name: str) -> bool:
        return (release_dir / f"phase-4b-check-{name}").is_file()

    original_retry = read_json("phase-4b-idempotent-verification.json")
    idempotent = original_retry.get("idempotent") is True
    prior = read_json("phase-4b-prior-release-record.json") if idempotent else {}
    context = read_json("phase-4b-release-context.json")
    candidate = read_json("phase-4b-candidate.json")
    remote = read_json("phase-4b-existing-remote.json" if idempotent else "phase-4b-remote.json")
    remote_result = read_json("phase-4b-remote-verification.json")
    digest = original_retry.get("registry_manifest_digest") if idempotent else remote_result.get("registry_manifest_digest")
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        digest = None
    attempted = (release_dir / "phase-4b-publication-attempted").is_file()
    completed_pull = (release_dir / "phase-4b-postpull-tests-passed").is_file()
    ready = prior_steps_success and evidence_upload_success and completed_pull and digest is not None
    # The original release must have passed all of its own gates, even if a
    # retry deliberately does not repeat any local candidate build tests.
    tests = (prior.get("test_results") if idempotent else
             {name: flag(name) for name in REQUIRED_TEST_CHECKS})
    closures = (prior.get("closure_checks") if idempotent else {
        "apt_closure": (release_dir / "phase-4b-apt-closure-passed").is_file(),
        "runtime_manifest": (release_dir / "phase-4b-runtime-manifest-passed").is_file(),
    })
    retry_checks = ({name: flag(name) for name in REQUIRED_RETRY_CHECKS} if idempotent else None)
    status = "VERIFIED" if ready else "UNVERIFIED" if attempted else "BLOCKED"
    stage = ("evidence-upload" if prior_steps_success and not evidence_upload_success
             else file_value("phase-4b-stage") or "preflight")
    # Release timestamp means finalization, not the preflight initiation time.
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = {
        "status": status, "source_git_commit": source_sha,
        "workflow_run_id": run_id, "workflow_run_attempt": run_attempt,
        "release_timestamp": timestamp,
        "source_timestamp": context.get("source_timestamp"),
        "build_timestamp": (prior.get("build_timestamp") if idempotent else file_value("phase-4b-build.timestamp")),
        "platform": {"os": "linux", "architecture": "arm64"},
        "local_manifest_digest": None if idempotent else candidate.get("manifest_digest"),
        "local_config_digest": None if idempotent else candidate.get("config_digest"),
        "oci_archive_sha256": None if idempotent else file_value("phase-4b-archive.digest"),
        "lock_sha256": file_value("phase-4b-lock.digest"),
        "registry_manifest_digest": digest,
        "observed_registry_digest": file_value("phase-4b-registry.digest"),
        "registry_visibility": file_value("phase-4b-registry-visibility"),
        "registry_reference": f"ghcr.io/kunalz06/nidar-runtime@{digest}" if status == "VERIFIED" else None,
        "failure_stage": None if status == "VERIFIED" else stage,
        "failure_reason": None if status == "VERIFIED" else f"workflow failed or stopped at {stage}",
        "idempotent": idempotent,
        "closure_checks": closures,
        "test_results": tests,
        "current_retry_verification": retry_checks,
        "original_release_evidence": original_retry.get("original_release_evidence") if idempotent else None,
        "registry_image_identity": remote or None,
        "source_repository": "kunalz06/airmouse",
    }
    if status == "VERIFIED":
        try:
            return make_release_record(raw), True
        except ValueError as error:
            raw["status"] = "UNVERIFIED" if attempted else "BLOCKED"
            raw["registry_reference"] = None
            raw["failure_stage"] = "final-record-validation"
            raw["failure_reason"] = str(error)
            return make_release_record(raw), False
    return make_release_record(raw), False

def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def emit(value: object, output: Path | None) -> None:
    text = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    print(text, end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    ci = commands.add_parser("verify-ci")
    ci.add_argument("--runs-file", type=Path, required=True)
    ci.add_argument("--jobs-file", type=Path, required=True)
    ci.add_argument("--expected-sha", required=True)
    ci.add_argument("--current-main-sha", required=True)
    ci.add_argument("--output", type=Path)
    remote = commands.add_parser("verify-remote")
    remote.add_argument("--candidate-file", type=Path, required=True)
    remote.add_argument("--remote-file", type=Path, required=True)
    remote.add_argument("--output", type=Path)
    existing = commands.add_parser("verify-existing-release")
    existing.add_argument("--remote-file", type=Path, required=True)
    existing.add_argument("--runs-file", type=Path, required=True)
    existing.add_argument("--source-sha", required=True)
    existing.add_argument("--prior-record-file", type=Path, required=True)
    existing.add_argument("--prior-artifact-file", type=Path, required=True)
    existing.add_argument("--attempt-file", type=Path, required=True)
    existing.add_argument("--output", type=Path)
    final = commands.add_parser("finalize-workflow")
    final.add_argument("--release-dir", type=Path, required=True)
    final.add_argument("--source-sha", required=True)
    final.add_argument("--run-id", type=int, required=True)
    final.add_argument("--run-attempt", type=int, required=True)
    final.add_argument("--prior-steps-success", choices=("true", "false"), required=True)
    final.add_argument("--evidence-upload-success", choices=("true", "false"), required=True)
    final.add_argument("--allow-unverified", action="store_true")
    final.add_argument("--output", type=Path, required=True)
    package = commands.add_parser("check-package")
    package.add_argument("--status", type=int, required=True)
    package.add_argument("--response-file", type=Path, required=True)
    package.add_argument("--output", type=Path)
    bootstrap = commands.add_parser("verify-bootstrap-remote")
    bootstrap.add_argument("--tagged-file", type=Path, required=True)
    bootstrap.add_argument("--digest-file", type=Path, required=True)
    bootstrap.add_argument("--source-sha", required=True)
    bootstrap.add_argument("--sentinel-tag", required=True)
    bootstrap.add_argument("--output", type=Path)
    tag = commands.add_parser("check-tag")
    tag.add_argument("--exists", choices=("true", "false"), required=True)
    tag.add_argument("--diagnostic-file", type=Path, required=True)
    tag.add_argument("--package-visibility", required=True)
    tag.add_argument("--output", type=Path)
    record = commands.add_parser("write-record")
    record.add_argument("--record-file", type=Path, required=True)
    record.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify-ci":
        runs = load_json(args.runs_file)
        if not isinstance(runs, list):
            raise ValueError("runs file must be a list of paginated responses")
        jobs = load_json(args.jobs_file)
        if not isinstance(jobs, dict):
            raise ValueError("jobs file must be an object keyed by workflow run id")
        normalized_jobs = {int(key): value for key, value in jobs.items()}
        emit(validate_ci_evidence(runs, normalized_jobs, args.expected_sha, args.current_main_sha), args.output)
    elif args.command == "verify-remote":
        digest = verify_remote_identity(load_json(args.candidate_file), load_json(args.remote_file))
        emit({"registry_manifest_digest": digest}, args.output)
    elif args.command == "verify-existing-release":
        runs = load_json(args.runs_file)
        if not isinstance(runs, list):
            raise ValueError("release workflow runs file must be a list")
        prior = load_json(args.prior_record_file)
        verified = verify_existing_release(
            load_json(args.remote_file), runs, args.source_sha, prior,
            load_json(args.prior_artifact_file), load_json(args.attempt_file))
        emit(verified, args.output)
    elif args.command == "finalize-workflow":
        record, success = create_workflow_record(
            args.release_dir, args.source_sha, args.run_id, args.run_attempt,
            args.prior_steps_success == "true", args.evidence_upload_success == "true")
        emit(record, args.output)
        if not success and not args.allow_unverified:
            raise SystemExit(1)
    elif args.command == "check-package":
        emit({"visibility": classify_package(args.status, load_json(args.response_file))}, args.output)
    elif args.command == "verify-bootstrap-remote":
        emit(verify_bootstrap_remote(load_json(args.tagged_file), load_json(args.digest_file),
                                     args.source_sha, args.sentinel_tag), args.output)
    elif args.command == "check-tag":
        diagnostic = args.diagnostic_file.read_text()
        emit({"tag_state": classify_tag_result(args.exists == "true", diagnostic,
                                                args.package_visibility)}, args.output)
    else:
        emit(make_release_record(load_json(args.record_file)), args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"runtime release verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
