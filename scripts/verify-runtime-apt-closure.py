#!/usr/bin/env python3
"""Verify or explicitly generate the pinned ARM64 runtime APT closure."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib

STAGES = ("mavsdk-build", "app-build", "runtime")
IMAGE_PATH = "/usr/local/share/nidar/provenance"
PACKAGE_RE = re.compile(r"^[a-zA-Z0-9+_.:-]+\t[^\t\r\n ]+\t(?:arm64|all)$")


def _comma_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"versions.lock {name} must be a non-empty comma-separated string")
    values = tuple(value.split(","))
    if any(not item or item.strip() != item for item in values) or len(set(values)) != len(values):
        raise ValueError(f"versions.lock {name} has empty, padded, or duplicate values")
    return values


def _relative_path(value: object, name: str) -> Path:
    if not isinstance(value, str):
        raise ValueError(f"versions.lock {name} must be a relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"versions.lock {name} must be a safe repository-relative path")
    return path


def load_policy(repo: Path) -> dict:
    """Parse the sole authoritative APT policy from config/versions.lock."""
    try:
        lock = tomllib.loads((repo / "config/versions.lock").read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"cannot parse config/versions.lock: {error}") from error
    required = (
        "ubuntu_24_04_apt_snapshot_url", "ubuntu_24_04_apt_snapshot_suites",
        "ubuntu_24_04_apt_snapshot_components", "ubuntu_24_04_apt_snapshot_signed_by",
        "ubuntu_24_04_apt_bootstrap_bundle", "ubuntu_24_04_apt_bootstrap_bundle_sha256",
        "ubuntu_24_04_arm64_apt_closure_lock", "ubuntu_24_04_arm64_apt_closure_schema",
    )
    missing = [name for name in required if name not in lock]
    if missing:
        raise ValueError("versions.lock lacks required APT policy fields: " + ", ".join(missing))
    url = lock["ubuntu_24_04_apt_snapshot_url"]
    if not isinstance(url, str) or not re.fullmatch(
            r"https://snapshot\.ubuntu\.com/ubuntu/\d{8}T\d{6}Z", url):
        raise ValueError("versions.lock snapshot URL must be a dated HTTPS Ubuntu snapshot")
    try:
        from datetime import datetime
        datetime.strptime(url.rsplit("/", 1)[1], "%Y%m%dT%H%M%SZ")
    except ValueError as error:
        raise ValueError("versions.lock snapshot timestamp is invalid") from error
    suites = _comma_list(lock["ubuntu_24_04_apt_snapshot_suites"], "snapshot suites")
    if suites != ("noble", "noble-updates", "noble-security", "noble-backports"):
        raise ValueError("versions.lock snapshot suites must be the approved Noble suite set")
    components = _comma_list(lock["ubuntu_24_04_apt_snapshot_components"], "snapshot components")
    if components != ("main", "restricted", "universe", "multiverse"):
        raise ValueError("versions.lock snapshot components must be the approved Ubuntu component set")
    signed_by = lock["ubuntu_24_04_apt_snapshot_signed_by"]
    if signed_by != "/usr/share/keyrings/ubuntu-archive-keyring.gpg":
        raise ValueError("versions.lock snapshot signing key is not the Ubuntu archive keyring")
    trust_sha256 = lock["ubuntu_24_04_apt_bootstrap_bundle_sha256"]
    if not isinstance(trust_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", trust_sha256):
        raise ValueError("versions.lock bootstrap trust checksum must be lowercase SHA-256")
    schema = lock["ubuntu_24_04_arm64_apt_closure_schema"]
    if not isinstance(schema, str) or not re.fullmatch(r"nidar-phase-4a-apt-closure-v[1-9][0-9]*", schema):
        raise ValueError("versions.lock APT closure schema is invalid")
    return {
        "url": url, "suites": suites, "components": components, "signed_by": signed_by,
        "trust_bundle": _relative_path(lock["ubuntu_24_04_apt_bootstrap_bundle"], "bootstrap bundle"),
        "trust_sha256": trust_sha256,
        "lock_path": _relative_path(lock["ubuntu_24_04_arm64_apt_closure_lock"], "closure lock"),
        "schema": schema,
    }


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def validate_inventory(content: bytes, stage: str) -> dict:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{stage}: invalid UTF-8") from exc
    lines = text.splitlines()
    if not lines or not text.endswith("\n"):
        raise ValueError(f"{stage}: missing or unterminated package inventory")
    if len(lines) != len(set(row.split("\t", 1)[0] for row in lines)):
        raise ValueError(f"{stage}: duplicate package name")
    if lines != sorted(lines, key=lambda row: row.encode("utf-8")):
        raise ValueError(f"{stage}: package inventory is not byte-sorted")
    for line in lines:
        if not PACKAGE_RE.fullmatch(line):
            raise ValueError(f"{stage}: invalid package/version/architecture: {line[:100]}")
    return {"filename": f"{stage}-packages.tsv", "package_count": len(lines), "sha256": sha(content)}


def snapshot_sources(policy: dict) -> bytes:
    return (
        f"Types: deb\n"
        f"URIs: {policy['url']}\n"
        f"Suites: {' '.join(policy['suites'])}\n"
        f"Components: {' '.join(policy['components'])}\n"
        f"Signed-By: {policy['signed_by']}\n"
    ).encode("utf-8")


def lock_metadata(inventories: dict, policy: dict) -> dict:
    return {
        "schema": policy["schema"],
        "platform": "linux/arm64",
        "snapshot": {"url": policy["url"], "suites": list(policy["suites"]),
                     "signed_by": policy["signed_by"],
                     "bootstrap_trust_sha256": "sha256:" + policy["trust_sha256"]},
        "stages": inventories,
    }


def verify_snapshot_sources(content: bytes, policy: dict) -> None:
    """Require the sole runtime APT source to be the reviewed Deb822 stanza."""
    if content != snapshot_sources(policy):
        raise ValueError("snapshot sources must be the exact reviewed Deb822 configuration")


def validate_lock(lock: dict, lock_dir: Path, policy: dict) -> dict:
    expected = lock_metadata({}, policy)
    if lock.get("schema") != policy["schema"] or lock.get("platform") != "linux/arm64":
        raise ValueError("unknown APT closure lock schema or platform")
    if lock.get("snapshot") != expected["snapshot"]:
        raise ValueError("APT closure lock snapshot or trust metadata differs from policy")
    stages = lock.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        raise ValueError("APT closure lock must cover all 3 Docker stages")
    result = {}
    for stage in STAGES:
        data = (lock_dir / f"{stage}-packages.tsv").read_bytes()
        actual = validate_inventory(data, stage)
        if stages[stage] != actual:
            raise ValueError(f"{stage}: committed closure inventory differs from lock manifest")
        result[stage] = actual
    return result


def verify_installer_trust_hash(installer: str, policy: dict) -> None:
    matches = re.findall(
        r"sha256sum /etc/ssl/certs/ca-certificates\.crt[\s\S]*?=\s*(?:\\\s*)?\n?\s*([0-9a-f]{64})",
        installer,
    )
    if matches != [policy["trust_sha256"]]:
        raise ValueError("APT installer bootstrap trust checksum differs from versions.lock policy")


def repository_policy_check(repo: Path) -> dict:
    policy = load_policy(repo)
    lock_path = repo / policy["lock_path"]
    lock_dir = lock_path.parent / "apt-closure"
    if not lock_path.is_file():
        raise ValueError(f"missing committed APT closure lock {policy['lock_path']}; generate the reviewed baseline explicitly")
    lock = json.loads(lock_path.read_text())
    inventories = validate_lock(lock, lock_dir, policy)
    verify_snapshot_sources((repo / "docker/apt/nidar-snapshot.sources").read_bytes(), policy)
    cert = (repo / policy["trust_bundle"]).read_bytes()
    if hashlib.sha256(cert).hexdigest() != policy["trust_sha256"]:
        raise ValueError("bootstrap trust bundle checksum differs from lock policy")
    runtime = (repo / "docker/runtime/Dockerfile").read_text()
    installer = (repo / "docker/apt/install-locked.sh").read_text()
    if "nidar-snapshot.sources" not in runtime or str(policy["trust_bundle"]) not in runtime:
        raise ValueError("runtime Dockerfile does not bootstrap the pinned snapshot trust")
    for stage in STAGES:
        if f"install-locked-apt {stage}" not in runtime:
            raise ValueError(f"runtime Dockerfile does not install the locked {stage} closure")
    if "APT::Update::Error-Mode=any" not in installer:
        raise ValueError("runtime Dockerfile lacks strict APT update mode")
    if re.search(r"(?:Verify-Peer\s+\"?false|allow-unauthenticated|trusted=yes)", runtime + installer, re.I):
        raise ValueError("runtime Dockerfile weakens APT/TLS verification")
    verify_installer_trust_hash(installer, policy)
    return inventories


def collect_from_image(image_ref: str) -> dict:
    cid = subprocess.check_output(["docker", "create", "--platform", "linux/arm64", image_ref], text=True).strip()
    try:
        with tempfile.TemporaryDirectory(prefix="nidar-apt-closure-") as tmp:
            tmp_path = Path(tmp)
            subprocess.run(["docker", "cp", f"{cid}:{IMAGE_PATH}/.", str(tmp_path)], check=True,
                           stdout=subprocess.DEVNULL)
            inventories, contents = {}, {}
            for stage in STAGES:
                data = (tmp_path / f"{stage}-packages.tsv").read_bytes()
                contents[stage] = data
                inventories[stage] = validate_inventory(data, stage)
            fmt = "${binary:Package}\\t${Version}\\t${Architecture}\\n"
            current = subprocess.check_output([
                "docker", "run", "--rm", "--platform", "linux/arm64", "--entrypoint", "/bin/sh", image_ref,
                "-c", f"LC_ALL=C dpkg-query -W -f='{fmt}' | LC_ALL=C sort",
            ])
            if current != contents["runtime"]:
                raise ValueError("runtime package inventory differs from current dpkg state")
            return {"inventories": inventories, "contents": contents}
    finally:
        subprocess.run(["docker", "rm", "-f", cid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def collect_from_inventory_dir(inventory_dir: Path) -> dict:
    """Read exactly the three files emitted by the APT-only Docker target."""
    if not inventory_dir.is_dir():
        raise ValueError(f"inventory directory does not exist: {inventory_dir}")
    expected = {f"{stage}-packages.tsv" for stage in STAGES}
    actual = {path.name for path in inventory_dir.iterdir()}
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected " + ", ".join(unexpected))
        raise ValueError("inventory directory must contain exactly the three stage closures (" + "; ".join(detail) + ")")
    inventories, contents = {}, {}
    for stage in STAGES:
        path = inventory_dir / f"{stage}-packages.tsv"
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"{stage}: inventory must be a regular file")
        data = path.read_bytes()
        contents[stage] = data
        inventories[stage] = validate_inventory(data, stage)
    return {"inventories": inventories, "contents": contents}


def write_lock(inventories: dict, contents: dict, lock_dir: Path, policy: dict) -> Path:
    lock_path = lock_dir.parent / policy["lock_path"].name
    if lock_path.exists():
        raise ValueError(f"refusing to overwrite existing APT closure lock: {lock_path}")
    lock_dir.mkdir(parents=True, exist_ok=True)
    for stage, data in contents.items():
        (lock_dir / f"{stage}-packages.tsv").write_bytes(data)
    lock_path.write_text(json.dumps(lock_metadata(inventories, policy), indent=2, sort_keys=True) + "\n")
    return lock_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-ref")
    parser.add_argument("--inventory-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--write-lock", action="store_true")
    parser.add_argument("--check-repository", action="store_true")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--lock-dir", type=Path,
                        help="candidate inventory directory for --write-lock only")
    args = parser.parse_args()
    if args.image_ref and args.inventory_dir:
        parser.error("--image-ref and --inventory-dir are mutually exclusive")
    if args.write_lock and not (args.image_ref or args.inventory_dir):
        parser.error("--write-lock requires --image-ref or --inventory-dir")
    repo = args.repo.resolve()
    policy = load_policy(repo)
    configured_lock_dir = repo / policy["lock_path"].parent / "apt-closure"
    if args.check_repository:
        if args.lock_dir is not None:
            parser.error("--lock-dir cannot override the authoritative closure location in --check-repository")
        repository_policy_check(repo)
        print("committed APT snapshot and closure lock policy passed")
    if args.image_ref:
        collected = collect_from_image(args.image_ref)
        inventories, contents = collected["inventories"], collected["contents"]
    elif args.inventory_dir:
        collected = collect_from_inventory_dir(args.inventory_dir)
        inventories, contents = collected["inventories"], collected["contents"]
    else:
        inventories = contents = None
    if inventories is not None:
        if args.write_lock:
            lock_dir = args.lock_dir or configured_lock_dir
            lock_path = write_lock(inventories, contents, lock_dir, policy)
            print(f"wrote reviewed candidate closure lock: {lock_path}")
        else:
            if args.lock_dir is not None:
                parser.error("--lock-dir cannot override the authoritative closure location when validating")
            lock_path = repo / policy["lock_path"]
            lock = json.loads(lock_path.read_text())
            expected = validate_lock(lock, configured_lock_dir, policy)
            if inventories != expected:
                raise ValueError("image APT closure differs from committed lock")
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for stage, data in contents.items():
                (args.output_dir / f"{stage}-packages.tsv").write_bytes(data)
            summary = lock_metadata(inventories, policy)
            summary["evidence_lock_sha256"] = sha((repo / policy["lock_path"]).read_bytes())
            (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        for stage, entry in inventories.items():
            print(f"{stage}: {entry['package_count']} packages, {entry['sha256']}")
        print("ARM64 APT package-closure verification passed")
    elif not args.check_repository:
        parser.error("--image-ref, --inventory-dir, or --check-repository is required")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as error:
        print(f"APT closure verification failed: {error}", file=sys.stderr)
        sys.exit(1)
