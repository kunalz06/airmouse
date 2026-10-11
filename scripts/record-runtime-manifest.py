#!/usr/bin/env python3
"""Read the ARM64 OCI image manifest digest and validate Docker/OCI provenance.

An image's Docker config ID is not the image manifest digest. Read the digest
from the OCI index, verify the content-addressed blobs, and cross-check the
locally loaded image. No registry upload or source modification is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def parse_canonical_utc_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UTC timestamp string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError(f"{field} must be canonical UTC YYYY-MM-DDTHH:MM:SSZ") from error
    return parsed


def validate_created_timestamps(expected: str, labels: dict, local_labels: dict,
                                oci_config: dict, docker: dict) -> datetime:
    """Bind exporter-produced creation fields to one captured build instant."""
    built_at = parse_canonical_utc_timestamp(expected, "captured build timestamp")
    observed = {
        "OCI created label": labels.get("org.opencontainers.image.created"),
        "loaded Docker created label": local_labels.get("org.opencontainers.image.created"),
        "OCI config.created": oci_config.get("created"),
        "loaded Docker image .Created": docker.get("Created"),
    }
    for name, value in observed.items():
        parse_canonical_utc_timestamp(value, name)
        if value != expected:
            raise ValueError(f"{name} differs from captured build timestamp")
    return built_at


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oci", required=True, type=Path)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apt-summary", type=Path, required=True)
    args = parser.parse_args()

    lock = tomllib.loads(Path("config/versions.lock").read_text())
    git_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    docker = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", args.image_ref], text=True
    ))[0]

    with tarfile.open(args.oci, "r:*") as archive:
        def read_blob(digest: str) -> bytes:
            algorithm, hexdigest = digest.split(":", 1)
            if algorithm != "sha256" or len(hexdigest) != 64:
                raise ValueError(f"invalid OCI digest: {digest}")
            data = archive.extractfile(f"blobs/{algorithm}/{hexdigest}").read()
            if sha(data) != digest:
                raise ValueError(f"OCI blob digest mismatch: {digest}")
            return data

        index = json.loads(archive.extractfile("index.json").read())
        arm64 = [
            descriptor for descriptor in index["manifests"]
            if descriptor.get("platform", {}).get("os") == "linux"
            and descriptor.get("platform", {}).get("architecture") == "arm64"
        ]
        if len(arm64) != 1:
            raise ValueError(f"expected one linux/arm64 OCI image; found {len(arm64)}")
        manifest_digest = arm64[0]["digest"]
        manifest = json.loads(read_blob(manifest_digest))
        config_digest = manifest["config"]["digest"]
        config = json.loads(read_blob(config_digest))
        for layer in manifest["layers"]:
            read_blob(layer["digest"])

    labels = config["config"]["Labels"]
    local_labels = docker["Config"]["Labels"]
    required = {
        "org.opencontainers.image.revision": git_sha,
        "io.nidar.mavsdk.version": lock["mavsdk"].removeprefix("v"),
        "io.nidar.mavsdk.source-commit": lock["mavsdk_arm64_source_commit"],
        "io.nidar.target.architecture": "linux/arm64",
        "org.opencontainers.image.base.digest": lock["ubuntu_24_04_image_index"],
    }
    if docker["Architecture"] != "arm64" or docker["Os"] != "linux":
        raise ValueError("loaded image platform is not linux/arm64")
    if config["architecture"] != "arm64" or config["os"] != "linux":
        raise ValueError("OCI config platform is not linux/arm64")
    if config["config"]["User"] != "65532:65532":
        raise ValueError("OCI runtime user is not the approved numeric non-root user")
    source_timestamp = subprocess.check_output(
        ["git", "show", "-s", "--format=%cI", "HEAD"], text=True
    ).strip()
    expected_created = os.environ.get("NIDAR_BUILD_TIMESTAMP", "")
    if not expected_created:
        raise ValueError("NIDAR_BUILD_TIMESTAMP captured at build initiation is required")
    built_at = validate_created_timestamps(expected_created, labels, local_labels, config, docker)
    created = expected_created
    checked_at = datetime.now(timezone.utc)
    try:
        source_at = datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError) as error:
        raise ValueError("invalid build/source timestamp") from error
    if source_at.utcoffset() is None:
        raise ValueError("Git source commit timestamp lacks timezone")
    if built_at < source_at or built_at > checked_at:
        raise ValueError("build wall-clock timestamp outside source-to-manifest window")
    if (checked_at - built_at).total_seconds() > 4 * 3600:
        raise ValueError("build wall-clock timestamp too old for fresh CI verification")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "0")
    workflow = os.environ.get("GITHUB_WORKFLOW", "local")
    ci_sha = os.environ.get("GITHUB_SHA", git_sha)
    ci_head_sha = os.environ.get("NIDAR_PR_HEAD_SHA", git_sha)
    ci_repository = os.environ.get("GITHUB_REPOSITORY", "local")
    if len(ci_head_sha) != 40 or any(c not in "0123456789abcdef" for c in ci_head_sha):
        raise ValueError("PR head identity is not an exact Git SHA")
    if ci_sha != git_sha:
        raise ValueError("checked-out Git SHA differs from recorded CI commit")
    if run_id != "local" and (not run_id.isdecimal() or not run_attempt.isdecimal()
                              or int(run_id) <= 0 or int(run_attempt) <= 0):
        raise ValueError("CI run ID/attempt are invalid")
    required.update({
        "org.opencontainers.image.created": created,
        "io.nidar.source.commit-timestamp": source_timestamp,
        "io.nidar.ci.run-id": run_id,
        "io.nidar.ci.run-attempt": run_attempt,
        "io.nidar.ci.workflow": workflow,
        "io.nidar.ci.sha": ci_sha,
        "io.nidar.ci.head-sha": ci_head_sha,
        "io.nidar.ci.repository": ci_repository,
    })
    for name, value in required.items():
        if labels.get(name) != value or local_labels.get(name) != value:
            raise ValueError(f"provenance mismatch for {name}")
    summary = json.loads(args.apt_summary.read_text())
    apt_schema = lock["ubuntu_24_04_arm64_apt_closure_schema"]
    apt_lock_path = Path(lock["ubuntu_24_04_arm64_apt_closure_lock"])
    if summary.get("schema") != apt_schema:
        raise ValueError("unknown apt closure evidence schema")
    apt_lock_bytes = apt_lock_path.read_bytes()
    if summary.get("evidence_lock_sha256") != sha(apt_lock_bytes):
        raise ValueError("APT evidence was not produced from the committed closure lock")
    apt_lock = json.loads(apt_lock_bytes)
    if summary.get("snapshot") != apt_lock.get("snapshot"):
        raise ValueError("APT evidence snapshot differs from committed closure lock")
    stages = summary["stages"]
    apt_records = []
    if set(stages) != {"mavsdk-build", "app-build", "runtime"}:
        raise ValueError("APT closure must cover all 3 Docker stages")
    for stage in ("mavsdk-build", "app-build", "runtime"):
        info = stages[stage]
        fname = f"{stage}-packages.tsv"
        data = (args.apt_summary.parent / fname).read_bytes()
        if info["filename"] != fname or info["package_count"] != len(data.splitlines()):
            raise ValueError(f"{stage}: invalid APT package count or filename")
        digest = sha(data)
        if info["sha256"] != digest:
            raise ValueError(f"{stage}: APT evidence checksum mismatch")
        apt_records.extend([f"apt_{stage}_package_count={info['package_count']}",
                            f"apt_{stage}_sha256={digest}"])
    apt_records.extend([
        f"apt_snapshot_url={summary['snapshot']['url']}",
        f"apt_closure_lock_sha256={summary['evidence_lock_sha256']}",
    ])
    # Containerd-backed Docker image stores can report the manifest digest as
    # image Id; classic Docker stores can report the config digest.
    if docker["Id"] not in (manifest_digest, config_digest):
        raise ValueError("loaded Docker image ID differs from OCI identity")

    report = "\n".join([
        "Phase 4A immutable linux/arm64 runtime manifest",
        f"source_git_commit={git_sha}",
        f"oci_image_manifest_digest={manifest_digest}",
        f"oci_image_config_digest={config_digest}",
        f"local_docker_image_id={docker['Id']}",
        f"oci_archive_sha256={archive_sha256(args.oci)}",
        f"oci_archive_size_bytes={args.oci.stat().st_size}",
        f"docker_image_size_uncompressed_bytes={docker['Size']}",
        "target_platform=linux/arm64",
        f"runtime_user={config['config']['User']}",
        f"mavsdk_version={required['io.nidar.mavsdk.version']}",
        f"mavsdk_source_commit={required['io.nidar.mavsdk.source-commit']}",
        f"runtime_base_index_digest={required['org.opencontainers.image.base.digest']}",
        f"application_version={labels.get('org.opencontainers.image.version')}",
        f"source_commit_timestamp={source_timestamp}",
        f"build_timestamp={created}",
        f"oci_config_created={config['created']}",
        f"local_docker_created={docker['Created']}",
        f"ci_run_id={run_id}",
        f"ci_run_attempt={run_attempt}",
        f"ci_workflow={workflow}",
        f"ci_source_sha={ci_sha}",
        f"ci_pr_head_sha={ci_head_sha}",
        f"ci_repository={ci_repository}",
        f"ci_run_url=https://github.com/{ci_repository}/actions/runs/{run_id}/attempts/{run_attempt}" if run_id != "local" else "ci_run_url=local",
        *apt_records,
        "note=OCI image manifest digest is distinct from Docker image config digest",
        "",
    ])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    print(report, end="")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"runtime manifest validation failed: {error}", file=sys.stderr)
        sys.exit(1)
