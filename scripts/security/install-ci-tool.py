#!/usr/bin/env python3
"""Install one exact, checksum-verified M-006 scanner distribution.

The tool lock is repository authority. Downloads go only to the caller-selected
CI scratch directory; repository source is never modified.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "security/ci-toolchain.lock.json"
INSTALLABLE = {"gitleaks", "trivy", "osv-scanner"}


def download(url: str, destination: Path) -> None:
    error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "VibeFlow-M006-CI/1"})
            with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            return
        except Exception as exc:  # noqa: BLE001 — retry then report exact failure
            error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"download failed after 3 attempts: {url}: {error}")


def install(tool_name: str, destination_dir: Path) -> Path:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    tool = lock["tools"][tool_name]
    expected = tool["immutable_sha256"]
    url = tool["distribution_coordinate"]
    destination_dir.mkdir(parents=True, exist_ok=True)
    binary = destination_dir / tool_name

    with tempfile.TemporaryDirectory(prefix=f"vibeflow-{tool_name}-") as temp:
        archive = Path(temp) / "distribution"
        download(url, archive)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"{tool_name} distribution checksum mismatch: expected {expected}, got {actual}"
            )

        if tool_name == "trivy":
            # Trivy's malicious-release history makes the official release
            # checksum and Sigstore subject binding mandatory in addition to
            # the locally calculated archive checksum.
            checksum_file = Path(temp) / "checksums.txt"
            download(tool["official_checksum_manifest"], checksum_file)
            checksum_file_sha = hashlib.sha256(checksum_file.read_bytes()).hexdigest()
            if checksum_file_sha != tool["checksum_manifest_sha256"]:
                raise RuntimeError("Trivy official checksum manifest identity mismatch")
            archive_name = url.rsplit("/", 1)[-1]
            expected_line = f"{expected}  {archive_name}"
            if expected_line not in checksum_file.read_text(encoding="utf-8").splitlines():
                raise RuntimeError("Trivy archive is not bound by the locked official checksum manifest")

            bundle_file = Path(temp) / "sigstore.json"
            download(tool["sigstore_bundle_coordinate"], bundle_file)
            bundle_sha = hashlib.sha256(bundle_file.read_bytes()).hexdigest()
            if bundle_sha != tool["sigstore_bundle_sha256"]:
                raise RuntimeError("Trivy Sigstore bundle identity mismatch")
            bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
            encoded_subject = bundle["messageSignature"]["messageDigest"]["digest"]
            subject = base64.b64decode(encoded_subject).hex()
            if subject != expected:
                raise RuntimeError("Trivy Sigstore bundle subject does not match archive checksum")

        member_name = tool.get("archive_member")
        if member_name:
            with tarfile.open(archive, "r:gz") as bundle:
                members = [member for member in bundle.getmembers() if member.name == member_name]
                if len(members) != 1 or not members[0].isfile():
                    raise RuntimeError(f"{tool_name} archive has no unique regular member {member_name!r}")
                source = bundle.extractfile(members[0])
                if source is None:
                    raise RuntimeError(f"cannot read {member_name!r} from {tool_name} archive")
                temporary_binary = destination_dir / f".{tool_name}.tmp"
                temporary_binary.write_bytes(source.read())
        else:
            temporary_binary = destination_dir / f".{tool_name}.tmp"
            temporary_binary.write_bytes(archive.read_bytes())

    temporary_binary.chmod(
        temporary_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    os.replace(temporary_binary, binary)
    return binary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=sorted(INSTALLABLE))
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "vibeflow-security-tools",
    )
    args = parser.parse_args()
    try:
        path = install(args.tool, args.destination.resolve())
    except Exception as exc:  # noqa: BLE001 — fail closed with useful CI diagnosis
        print(f"security tool installation failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
