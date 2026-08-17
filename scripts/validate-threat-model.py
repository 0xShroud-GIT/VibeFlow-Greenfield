#!/usr/bin/env python3
"""Validate M-003 threat-model and trust-boundary security contracts.

No third-party dependencies. The validator intentionally checks structure,
cross-references, and constitutional policy markers rather than attempting to
"understand" arbitrary prose.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ASSETS = [f"AS-{i:03d}" for i in range(1, 13)]
EXPECTED_THREATS = [f"TM-{i:03d}" for i in range(1, 25)]
EXPECTED_BOUNDARIES = [f"TB-{i:03d}" for i in range(1, 14)]
EXPECTED_INVARIANTS = [f"INV-{i:03d}" for i in range(1, 21)]

THREAT_FIELDS = [
    "Actors",
    "Assets",
    "Boundaries",
    "Risk",
    "Attack",
    "Required controls",
    "Detection/evidence",
    "Residual risk",
]
BOUNDARY_FIELDS = [
    "Source",
    "Destination",
    "Trust",
    "Authentication",
    "Authorization",
    "Allowed data/actions",
    "Forbidden",
    "Replay/confusion defense",
    "Audit/evidence",
]

SECURITY_MASTER_REFS = [
    "02_ARCHITECTURE/TRUST_BOUNDARIES.md",
    "08_SECURITY/THREAT_MODEL.md",
    "08_SECURITY/SECRET_HANDLING.md",
    "08_SECURITY/WORKSPACE_ISOLATION.md",
    "08_SECURITY/SUPPLY_CHAIN.md",
    "00_MASTER/NON_NEGOTIABLE_INVARIANTS.yaml",
]

SECRET_POLICY_MARKERS = [
    "`SecretRef` is opaque metadata",
    "Raw secrets live only in an approved encrypted broker/KMS boundary",
    "minimum secret",
    "shortest practical lifetime",
    "Never place raw secrets in Agent prompts, event payloads, evidence blobs, logs, analytics or the native-web bridge",
]

WORKSPACE_POLICY_MARKERS = [
    "filesystem/project scoping",
    "process isolation",
    "network controls",
    "preview auth",
    "secrets exposure",
    "snapshot/persistence behavior",
    "resource limits",
    "cleanup",
    "cross-tenant separation",
    "Provider documentation is not sufficient evidence",
]

SECURITY_PRINCIPLE_MARKERS = [
    "Availability is not permission",
    "External content is data, not instruction authority",
    "Execution claims are not verification",
    "Continuity is proven, not guessed",
    "fails closed",
    "Security tests are negative by default",
    "Do not invent cryptography or security protocols",
]


def read(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def ids_in_headings(text: str, prefix: str, level: int) -> list[str]:
    marks = "#" * level
    return re.findall(rf"(?m)^{re.escape(marks)} ({re.escape(prefix)}-\d{{3}})\b", text)


def duplicate_ids(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dup: list[str] = []
    for item in ids:
        if item in seen and item not in dup:
            dup.append(item)
        seen.add(item)
    return dup


def split_sections(text: str, prefix: str, level: int) -> dict[str, str]:
    marks = "#" * level
    pat = re.compile(
        rf"(?m)^{re.escape(marks)} (?P<id>{re.escape(prefix)}-\d{{3}})\b[^\n]*\n"
    )
    matches = list(pat.finditer(text))
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[match.group("id")] = text[start:end]
    return sections


def field_value(section: str, field: str) -> str | None:
    match = re.search(
        rf"(?m)^- \*\*{re.escape(field)}:\*\*\s*(?P<value>.+?)\s*$", section
    )
    return match.group("value").strip() if match else None


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    try:
        threats_text = read(root, "master-build-system/08_SECURITY/THREAT_MODEL.md")
        boundaries_text = read(root, "master-build-system/02_ARCHITECTURE/TRUST_BOUNDARIES.md")
        security_text = read(root, "master-build-system/08_SECURITY/SECURITY_MASTER.md")
        secret_text = read(root, "master-build-system/08_SECURITY/SECRET_HANDLING.md")
        workspace_text = read(root, "master-build-system/08_SECURITY/WORKSPACE_ISOLATION.md")
        invariants_text = read(root, "master-build-system/00_MASTER/NON_NEGOTIABLE_INVARIANTS.yaml")
    except (OSError, UnicodeError) as exc:
        return {
            "result": "FAIL",
            "errors": [f"required security contract unreadable: {exc}"],
            "warnings": [],
            "counts": {},
        }

    asset_ids = ids_in_headings(threats_text, "AS", 3)
    threat_ids = ids_in_headings(threats_text, "TM", 3)
    boundary_ids = ids_in_headings(boundaries_text, "TB", 2)

    counts["assets"] = len(asset_ids)
    counts["threats"] = len(threat_ids)
    counts["boundaries"] = len(boundary_ids)

    for label, actual, expected in [
        ("asset", asset_ids, EXPECTED_ASSETS),
        ("threat", threat_ids, EXPECTED_THREATS),
        ("boundary", boundary_ids, EXPECTED_BOUNDARIES),
    ]:
        dup = duplicate_ids(actual)
        if dup:
            errors.append(f"duplicate {label} IDs: {dup}")
        if actual != expected:
            errors.append(f"{label} IDs must be exactly {expected}; got {actual}")

    threat_sections = split_sections(threats_text, "TM", 3)
    referenced_boundaries: set[str] = set()
    referenced_assets: set[str] = set()

    for tid in EXPECTED_THREATS:
        section = threat_sections.get(tid)
        if section is None:
            continue
        for field in THREAT_FIELDS:
            value = field_value(section, field)
            if value is None or not value.strip():
                errors.append(f"{tid}: missing required field '{field}'")
        boundary_value = field_value(section, "Boundaries") or ""
        asset_value = field_value(section, "Assets") or ""

        tbs = re.findall(r"\bTB-\d{3}\b", boundary_value)
        assets = re.findall(r"\bAS-\d{3}\b", asset_value)
        if not tbs:
            errors.append(f"{tid}: Boundaries must reference at least one TB-ID")
        if not assets:
            errors.append(f"{tid}: Assets must reference at least one AS-ID")
        for bid in tbs:
            referenced_boundaries.add(bid)
            if bid not in EXPECTED_BOUNDARIES:
                errors.append(f"{tid}: unknown boundary reference {bid}")
        for aid in assets:
            referenced_assets.add(aid)
            if aid not in EXPECTED_ASSETS:
                errors.append(f"{tid}: unknown asset reference {aid}")

    missing_boundary_coverage = sorted(set(EXPECTED_BOUNDARIES) - referenced_boundaries)
    if missing_boundary_coverage:
        errors.append(
            "trust boundaries not covered by any threat: " + ", ".join(missing_boundary_coverage)
        )
    missing_asset_coverage = sorted(set(EXPECTED_ASSETS) - referenced_assets)
    if missing_asset_coverage:
        errors.append(
            "assets not covered by any threat: " + ", ".join(missing_asset_coverage)
        )

    boundary_sections = split_sections(boundaries_text, "TB", 2)
    for bid in EXPECTED_BOUNDARIES:
        section = boundary_sections.get(bid)
        if section is None:
            continue
        for field in BOUNDARY_FIELDS:
            value = field_value(section, field)
            if value is None or not value.strip():
                errors.append(f"{bid}: missing required field '{field}'")

    actual_invariants = re.findall(r"(?m)^- id: (INV-\d{3})\s*$", invariants_text)
    if actual_invariants != EXPECTED_INVARIANTS:
        errors.append(
            f"non-negotiable invariant IDs changed or incomplete: expected {EXPECTED_INVARIANTS}, got {actual_invariants}"
        )

    crosswalk_heading = "## Non-negotiable invariant crosswalk"
    if crosswalk_heading not in threats_text:
        errors.append("THREAT_MODEL.md missing non-negotiable invariant crosswalk")
    else:
        crosswalk = threats_text.split(crosswalk_heading, 1)[1]
        for iid in EXPECTED_INVARIANTS:
            occurrences = len(re.findall(rf"(?m)^- \*\*{re.escape(iid)}:\*\*", crosswalk))
            if occurrences != 1:
                errors.append(f"invariant crosswalk must contain {iid} exactly once; got {occurrences}")

    for ref in SECURITY_MASTER_REFS:
        if ref not in security_text:
            errors.append(f"SECURITY_MASTER.md missing normative reference '{ref}'")
    for marker in SECURITY_PRINCIPLE_MARKERS:
        if marker not in security_text:
            errors.append(f"SECURITY_MASTER.md missing constitutional marker '{marker}'")

    for marker in SECRET_POLICY_MARKERS:
        if marker not in secret_text:
            errors.append(f"SECRET_HANDLING.md missing required policy marker '{marker}'")

    for marker in WORKSPACE_POLICY_MARKERS:
        if marker not in workspace_text:
            errors.append(f"WORKSPACE_ISOLATION.md missing required certification marker '{marker}'")

    anti_authority_markers = [
        ("master-build-system/02_ARCHITECTURE/TRUST_BOUNDARIES.md", boundaries_text, "Agent is an untrusted executor"),
        ("master-build-system/02_ARCHITECTURE/TRUST_BOUNDARIES.md", boundaries_text, "Tool availability"),
        ("master-build-system/02_ARCHITECTURE/TRUST_BOUNDARIES.md", boundaries_text, "Raw BYOK/provider tokens"),
        ("master-build-system/08_SECURITY/THREAT_MODEL.md", threats_text, "Agent finish never VERIFIED"),
        ("master-build-system/08_SECURITY/THREAT_MODEL.md", threats_text, "Repository != workspace"),
        ("master-build-system/08_SECURITY/THREAT_MODEL.md", threats_text, "replay != workspace reconciliation"),
    ]
    for rel, text, marker in anti_authority_markers:
        if marker not in text:
            errors.append(f"{rel} missing anti-authority marker '{marker}'")

    counts["referenced_boundaries"] = len(referenced_boundaries)
    counts["referenced_assets"] = len(referenced_assets)
    counts["invariants_crosswalked"] = sum(
        1
        for iid in EXPECTED_INVARIANTS
        if re.search(rf"(?m)^- \*\*{re.escape(iid)}:\*\*", threats_text)
    )

    return {
        "result": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate VibeFlow M-003 threat-model and trust-boundary contracts"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (defaults to repository containing this script)",
    )
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root is not None else REPO_ROOT
    result = validate(root)

    print("M-003 threat-model/trust-boundary validator")
    print(f"  assets: {result['counts'].get('assets')}")
    print(f"  threats: {result['counts'].get('threats')}")
    print(f"  boundaries: {result['counts'].get('boundaries')}")
    print(f"  invariant crosswalk: {result['counts'].get('invariants_crosswalked')}")
    if result["errors"]:
        print("\nErrors:")
        for error in result["errors"]:
            print(f"  - {error}")
    print(f"\nRESULT: {result['result']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
