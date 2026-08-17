#!/usr/bin/env python3
"""M-002 no-dependency dependency/harvest registry validator.

Ratifies structural integrity of `06_HARVEST/OSS_HARVEST_REGISTRY.yaml`:
35 unique sequential H-IDs, required fields, official-source allowlist,
decision/integration vocabulary, license classification (green vs explicit
review-required vs unresolved), DO_NOT_INVENT coherence, and no BUILD entry
without ADR justification.

Stdlib only; does not install packages; does not mutate architecture.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
MBS = REPO_ROOT / "master-build-system"

_spec = importlib.util.spec_from_file_location(
    "validate_master_contracts", SCRIPTS_DIR / "validate-master-contracts.py"
)
_vmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vmc)
load_simple_yaml = _vmc.load_simple_yaml

EXPECTED_ENTRY_COUNT = 35
EXPECTED_IDS = [f"H-{i:03d}" for i in range(1, EXPECTED_ENTRY_COUNT + 1)]
REQUIRED_FIELDS = ("id", "capability", "name", "version", "decision", "integration", "license", "source", "rule")

SUPPORTED_DECISIONS = {
    "ADOPT",
    "ADOPT_LATER",
    "ADOPT_AS_DEFAULT_ADAPTER",
    "ADOPT_AS_PROVIDER",
    "ADOPT_WHEN_DELEGATION",
    "ADOPT_PROFILE",
    "OPTIONAL_BRIDGE",
    "WRAP",
    "BRIDGE",
    "EXTEND",
    # BUILD is policy-allowed only with explicit ADR justification in the rule.
    "BUILD",
}

SUPPORTED_INTEGRATIONS = {
    "DEPEND",
    "DEPEND_DEV",
    "DEPEND_SERVICE",
    "SERVICE",
    "SERVICE_ADAPTER",
    "PROTOCOL",
    "PROTOCOL_SDK",
    "ADAPTER",
    "STANDARD",
    "TOOL",
    "CI_TOOL",
    "WRAP",
}

# Permissive software licenses default-green under LICENSE_POLICY.md.
GREEN_LICENSE_TOKENS = ("MIT", "Apache-2.0", "BSD", "ISC", "PostgreSQL")
# Permissive documentation license (attribution when reproducing spec text).
GREEN_DOC_TOKENS = ("CC-BY-4.0",)
# Copyleft / conditional / deferred-verification markers that make an entry
# explicitly REVIEW REQUIRED under LICENSE_POLICY.md.
REVIEW_LICENSE_MARKERS = (
    "AGPL",
    "GPL",
    "LGPL",
    "MPL",
    "SSPL",
    "BSL",
    "source-available",
    "network copyleft",
    "review",
    "varies",
    "vary ",
    "verify",
    "confirm",
)
# Wording that means the license was never classified — a hard failure.
UNRESOLVED_LICENSE_MARKERS = (
    "see upstream",
    "see official",
    "see spec",
    "tbd",
    "unknown",
)

# Official upstream source hosts verified during M-002 (evidence:
# evidence/missions/M-002/DEPENDENCY_HARVEST_RATIFICATION.md).
OFFICIAL_SOURCE_HOSTS: dict[str, set[str]] = {
    "H-001": {"nodejs.org", "www.nodejs.org"},
    "H-002": {"github.com"},
    "H-003": {"github.com"},
    "H-004": {"github.com"},
    "H-005": {"expo.dev", "www.expo.dev"},
    "H-006": {"github.com"},
    "H-007": {"github.com"},
    "H-008": {"github.com"},
    "H-009": {"github.com"},
    "H-010": {"postgresql.org", "www.postgresql.org"},
    "H-011": {"github.com"},
    "H-012": {"github.com"},
    "H-013": {"github.com"},
    "H-014": {"github.com"},
    "H-015": {"github.com"},
    "H-016": {"github.com"},
    "H-017": {"github.com"},
    "H-018": {"github.com"},
    "H-019": {"modelcontextprotocol.io", "www.modelcontextprotocol.io", "github.com"},
    "H-020": {"github.com"},
    "H-021": {"docs.ag-ui.com", "ag-ui.com", "www.ag-ui.com", "github.com"},
    "H-022": {"github.com"},
    "H-023": {"containers.dev", "www.containers.dev", "github.com"},
    "H-024": {"github.com"},
    "H-025": {"github.com"},
    "H-026": {"github.com"},
    "H-027": {"github.com"},
    "H-028": {"github.com"},
    "H-029": {"github.com"},
    "H-030": {"github.com"},
    "H-031": {"github.com"},
    "H-032": {"github.com"},
    "H-033": {"github.com"},
    "H-034": {"github.com"},
    "H-035": {"github.com"},
}

# DO_NOT_INVENT.yaml problems must remain covered by ratified registry names.
DNI_COVERAGE: dict[str, tuple[str, ...]] = {
    "code editor": ("Monaco Editor",),
    "terminal emulator": ("xterm.js",),
    "coding-agent client protocol": ("Agent Client Protocol",),
    "agent tool/data protocol": ("Model Context Protocol",),
    "agent-to-agent delegation protocol": ("Agent2Agent",),
    "durable workflow engine": ("Temporal",),
    "workspace compute fabric": ("Daytona", "E2B"),
    "telemetry transport": ("OpenTelemetry",),
    "authentication primitives": ("Better Auth",),
    "Git hosting": ("GitHub",),
    "environment descriptor": ("Development Containers",),
    "database": ("PostgreSQL",),
}


def classify_license(raw: str) -> str:
    text = (raw or "").strip()
    low = text.lower()
    if text == "":
        return "MISSING"
    if any(marker in low for marker in UNRESOLVED_LICENSE_MARKERS):
        return "UNRESOLVED"
    if any(marker in text for marker in REVIEW_LICENSE_MARKERS) or any(
        marker in low for marker in ("varies",)
    ):
        return "REVIEW_REQUIRED"
    if any(token in text for token in GREEN_LICENSE_TOKENS) or any(
        token in text for token in GREEN_DOC_TOKENS
    ):
        return "GREEN"
    return "UNCLASSIFIED"


def source_host(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            return None
        return parsed.netloc.lower()
    except ValueError:
        return None


def validate(root: Path) -> dict:
    mbs = root / "master-build-system"
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    review_required: list[str] = []

    registry_path = mbs / "06_HARVEST" / "OSS_HARVEST_REGISTRY.yaml"
    if not registry_path.is_file():
        return {"result": "FAIL", "errors": ["OSS_HARVEST_REGISTRY.yaml missing"], "warnings": [], "counts": {}, "entries": []}

    doc = load_simple_yaml(registry_path.read_text(encoding="utf-8"))
    entries = doc.get("entries") or []
    counts["entries"] = len(entries)

    if len(entries) != EXPECTED_ENTRY_COUNT:
        errors.append(f"Expected exactly {EXPECTED_ENTRY_COUNT} registry entries, got {len(entries)}")

    ids = [str(e.get("id")) for e in entries]
    seen: set[str] = set()
    for hid in ids:
        if hid in seen:
            errors.append(f"Duplicate H-ID: {hid}")
        seen.add(hid)
    if ids != EXPECTED_IDS:
        errors.append(
            "H-IDs must be exactly H-001..H-035 unique and sequential; got "
            + json.dumps(ids)
        )

    for entry in entries:
        hid = str(entry.get("id") or "?")
        for field in REQUIRED_FIELDS:
            if field not in entry or entry.get(field) is None or str(entry.get(field)).strip() == "":
                errors.append(f"{hid}: missing required field '{field}'")

        decision = str(entry.get("decision") or "")
        if decision and decision not in SUPPORTED_DECISIONS:
            errors.append(f"{hid}: unsupported decision '{decision}'")
        if decision == "BUILD":
            rule = str(entry.get("rule") or "")
            if not re.search(r"ADR|ADR-[0-9]+", rule):
                errors.append(f"{hid}: BUILD decision requires explicit ADR justification in 'rule'")

        integration = str(entry.get("integration") or "")
        if integration and integration not in SUPPORTED_INTEGRATIONS:
            errors.append(f"{hid}: unsupported integration classification '{integration}'")

        license_class = classify_license(str(entry.get("license") or ""))
        if license_class == "MISSING":
            errors.append(f"{hid}: missing license classification")
        elif license_class == "UNRESOLVED":
            errors.append(f"{hid}: unresolved license classification '{entry.get('license')}'")
        elif license_class == "UNCLASSIFIED":
            errors.append(f"{hid}: license does not map to a green or review-required class: '{entry.get('license')}'")
        elif license_class == "REVIEW_REQUIRED":
            review_required.append(hid)

        source = str(entry.get("source") or "")
        if source:
            host = source_host(source)
            allowed = OFFICIAL_SOURCE_HOSTS.get(hid, set())
            if host is None:
                errors.append(f"{hid}: source must be a well-formed https URL, got '{source}'")
            elif host not in allowed:
                errors.append(
                    f"{hid}: source host '{host}' is not in the official upstream allowlist {sorted(allowed)}"
                )

    # Registry must stay synchronized with the pack summary.
    try:
        summary = json.loads((mbs / "PACK_SUMMARY.json").read_text(encoding="utf-8"))
        declared = summary.get("approved_harvest_entries")
        if declared != EXPECTED_ENTRY_COUNT or declared != len(entries):
            errors.append(
                f"PACK_SUMMARY.json approved_harvest_entries={declared} != registry entry count {len(entries)}"
            )
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"PACK_SUMMARY.json unreadable: {exc}")

    # DO_NOT_INVENT coherence: every approved generic solution stays backed by
    # a ratified registry entry, so no custom subsystem is silently invented.
    dni_path = mbs / "06_HARVEST" / "DO_NOT_INVENT.yaml"
    if not dni_path.is_file():
        errors.append("DO_NOT_INVENT.yaml missing")
    else:
        dni = load_simple_yaml(dni_path.read_text(encoding="utf-8"))
        names_blob = "\n".join(str(e.get("name") or "") for e in entries)
        for item in dni.get("entries") or []:
            problem = str((item.get("problem") or "").strip())
            expected_names = DNI_COVERAGE.get(problem)
            if expected_names is None:
                errors.append(f"DO_NOT_INVENT problem '{problem}' has no registry-coverage mapping in the validator")
                continue
            for expected in expected_names:
                if expected not in names_blob:
                    errors.append(
                        f"DO_NOT_INVENT problem '{problem}' expects approved candidate '{expected}' but no registry entry provides it"
                    )

    counts["review_required_licenses"] = len(review_required)
    return {
        "result": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "review_required": review_required,
        "entries": [
            {
                "id": str(e.get("id")),
                "name": str(e.get("name")),
                "capability": str(e.get("capability")),
                "decision": str(e.get("decision")),
                "integration": str(e.get("integration")),
                "version": str(e.get("version")),
                "license_class": classify_license(str(e.get("license") or "")),
            }
            for e in entries
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the VibeFlow dependency/harvest registry (M-002)")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root to validate (defaults to the repository containing this script)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root is not None else REPO_ROOT
    result = validate(root)

    lines = ["M-002 dependency/harvest registry validator", ""]
    lines.append(f"  entries: {result['counts'].get('entries')}")
    lines.append(f"  review-required licenses: {result['counts'].get('review_required_licenses')} {result.get('review_required', [])}")
    if result["errors"]:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"  - {item}" for item in result["errors"])
    lines.append("")
    lines.append("RESULT: " + result["result"])
    sys.stdout.write("\n".join(lines) + "\n")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
