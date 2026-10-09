#!/usr/bin/env python3
"""Verify/export exact ARM64 APT package/version/architecture closure.

Inventories are produced by dpkg-query inside pinned Docker build stages.
These are observed package versions, not immutable .deb package hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

STAGES = ("mavsdk-build", "app-build", "runtime")
IMAGE_PATH = "/usr/local/share/nidar/provenance"
PACKAGE_RE = re.compile(r"^[a-zA-Z0-9+_.:-]+\t[^\t\r\n ]+\t(?:arm64|all)$")


def validate_inventory(content: bytes, stage: str) -> dict:
    try:
        txt = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{stage}: invalid UTF-8") from exc
    lines = txt.splitlines()
    if not lines or not txt.endswith("\n"):
        raise ValueError(f"{stage}: missing or unterminated package inventory")
    if len(lines) != len(set(row.split("\t", 1)[0] for row in lines)):
        raise ValueError(f"{stage}: duplicate package name")
    if lines != sorted(lines, key=lambda row: row.encode("utf-8")):
        raise ValueError(f"{stage}: package inventory is not byte-sorted")
    for line in lines:
        if not PACKAGE_RE.fullmatch(line):
            raise ValueError(f"{stage}: invalid package/version/architecture: {line[:100]}")
    return {
        "stage": stage,
        "package_count": len(lines),
        "sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
        "filename": f"{stage}-packages.tsv",
        "format": "dpkg-query:binary:Package,Version,Architecture",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cid = subprocess.check_output(
        ["docker", "create", "--platform", "linux/arm64", args.image_ref], text=True
    ).strip()
    try:
        with tempfile.TemporaryDirectory(prefix="nidar-apt-closure-") as tmp:
            tmp_path = Path(tmp)
            subprocess.run(
                ["docker", "cp", f"{cid}:{IMAGE_PATH}/.", str(tmp_path)],
                check=True, stdout=subprocess.DEVNULL
            )
            inventories = {}
            for stage in STAGES:
                name = f"{stage}-packages.tsv"
                data = (tmp_path / name).read_bytes()
                inventories[stage] = validate_inventory(data, stage)
            # Validate recorded runtime closure against the live dpkg inventory.
            dollar = chr(36)
            fmt = (
                f"{dollar}{{binary:Package}}\\t"
                f"{dollar}{{Version}}\\t{dollar}{{Architecture}}\\n"
            )
            current = subprocess.check_output([
                "docker", "run", "--rm", "--platform", "linux/arm64",
                "--entrypoint", "/bin/sh", args.image_ref,
                "-c", f"LC_ALL=C dpkg-query -W -f='{fmt}' | LC_ALL=C sort",
            ])
            if current != (tmp_path / "runtime-packages.tsv").read_bytes():
                raise ValueError("runtime package inventory differs from current dpkg state")
            runtime = (tmp_path / "runtime-packages.tsv").read_text()
            installed = {row.split("\t", 1)[0].split(":", 1)[0] for row in runtime.splitlines()}
            if not {"ca-certificates", "libgcc-s1", "libstdc++6"} <= installed:
                raise ValueError("runtime missing required OS packages")
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for stage in STAGES:
                name = f"{stage}-packages.tsv"
                (args.output_dir / name).write_bytes((tmp_path / name).read_bytes())
            summary = {
                "schema": "nidar-phase-4a-apt-closure-v1",
                "platform": "linux/arm64",
                "scope": "installed package inventory per Docker stage; not immutable apt snapshot",
                "stages": inventories,
            }
            (args.output_dir / "summary.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n"
            )
            for stage in STAGES:
                entry = inventories[stage]
                print(f"{stage}: {entry['package_count']} packages, {entry['sha256']}")
            print("ARM64 APT package-closure evidence passed")
    finally:
        subprocess.run(["docker", "rm", "-f", cid],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f"APT closure verification failed: {exc}", file=sys.stderr)
        sys.exit(1)
