#!/usr/bin/env python3
"""Read the ARM64 OCI image manifest digest and validate Docker/OCI provenance.

An image's Docker config ID is not the image manifest digest. Read the digest
from the OCI index, verify the content-addressed blobs, and cross-check the
locally loaded image. No registry upload or source modification is performed.
"""
import argparse
import hashlib
import json
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oci", required=True, type=Path)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--output", type=Path)
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
    for name, value in required.items():
        if labels.get(name) != value or local_labels.get(name) != value:
            raise ValueError(f"provenance mismatch for {name}")
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
        f"build_timestamp={labels.get('org.opencontainers.image.created')}",
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
