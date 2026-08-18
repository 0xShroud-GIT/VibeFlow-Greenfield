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
# LICENSE_POLICY.md requires every entry to record: approved version/version line,
# license classification, use, ownership boundary, upgrade policy and replacement
# strategy (plus registry identity fields).
REQUIRED_FIELDS = (
    "id",
    "capability",
    "name",
    "version",
    "decision",
    "integration",
    "license",
    "source",
    "rule",
    "use",
    "ownership",
    "upgrade_policy",
    "replacement_strategy",
)

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

PACKAGE_COORDINATE_FIELDS = (
    "ecosystem",
    "name",
    "harvest_id",
    "approved_usage",
)
SUPPORTED_PACKAGE_ECOSYSTEMS = {"npm"}
SUPPORTED_PACKAGE_USAGE = {"development", "production", "both"}
NPM_PACKAGE_RE = re.compile(r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")

# Exact official upstream identities verified during M-002 (evidence:
# evidence/missions/M-002/DEPENDENCY_HARVEST_RATIFICATION.md).
#
# Generic `github.com` is NOT proof of provenance. For GitHub-hosted projects the
# expected `owner/repo` path must match exactly (case-insensitive); for official
# domains the exact hostname (optionally with a path prefix) must match.
# Spec formats:
#   ("github", "owner/repo")            -> https://github.com/owner/repo[/...]
#   ("domain", "host[/path-prefix]")    -> https://host/path-prefix[/...]
OFFICIAL_SOURCES: dict[str, list[tuple[str, str]]] = {
    "H-001": [("domain", "nodejs.org")],
    "H-002": [("github", "microsoft/TypeScript")],
    "H-003": [("github", "pnpm/pnpm")],
    "H-004": [("github", "vercel/turborepo")],
    "H-005": [("domain", "expo.dev")],
    "H-006": [("github", "facebook/react-native")],
    "H-007": [("github", "microsoft/monaco-editor")],
    "H-008": [("github", "xtermjs/xterm.js")],
    "H-009": [("github", "fastify/fastify")],
    "H-010": [("domain", "postgresql.org")],
    "H-011": [("github", "drizzle-team/drizzle-orm")],
    "H-012": [("github", "better-auth/better-auth")],
    "H-013": [("github", "openfga/openfga")],
    "H-014": [("github", "temporalio/sdk-typescript")],
    "H-015": [("github", "OpenHands/software-agent-sdk")],
    "H-016": [("github", "daytonaio/daytona")],
    "H-017": [("github", "e2b-dev/E2B")],
    "H-018": [("github", "agentclientprotocol/agent-client-protocol")],
    "H-019": [("domain", "modelcontextprotocol.io")],
    "H-020": [("github", "a2aproject/A2A")],
    "H-021": [("domain", "docs.ag-ui.com")],
    "H-022": [("github", "vercel/ai")],
    "H-023": [("domain", "containers.dev")],
    "H-024": [("github", "open-telemetry/opentelemetry-js")],
    "H-025": [("github", "sinclairzx81/typebox")],
    "H-026": [("github", "microsoft/playwright")],
    "H-027": [("github", "mobile-dev-inc/Maestro")],
    "H-028": [("github", "vitest-dev/vitest")],
    "H-029": [("github", "gitleaks/gitleaks")],
    "H-030": [("github", "aquasecurity/trivy")],
    "H-031": [("github", "google/osv-scanner")],
    "H-032": [("github", "semgrep/semgrep")],
    "H-033": [("github", "octokit/octokit.js")],
    "H-034": [("github", "aws/aws-sdk-js-v3")],
    "H-035": [("github", "cloudevents/spec")],
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


def source_matches(url: str, specs: list[tuple[str, str]]) -> tuple[bool, str]:
    """True when the URL is exactly one of the official upstream identities."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False, "unparseable URL"
    if parsed.scheme != "https":
        return False, "must use https"
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip("/")
    for kind, expected in specs:
        if kind == "github":
            if host not in ("github.com", "www.github.com"):
                continue
            parts = path.split("/")
            if len(parts) >= 2 and "/".join(parts[:2]).lower() == expected.lower():
                return True, ""
        elif kind == "domain":
            expected_host = expected.split("/", 1)[0].lower()
            # www.<official-domain> is the same official identity, nothing else.
            if host not in (expected_host, "www." + expected_host):
                continue
            prefix = expected.split("/", 1)[1].strip("/") if "/" in expected else ""
            if not prefix or path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                return True, ""
    return False, f"URL does not match any official upstream identity {[s[1] for s in specs]}"


def validate(root: Path) -> dict:
    mbs = root / "master-build-system"
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    review_required: list[str] = []
    package_coordinates: dict[tuple[str, str], dict[str, str]] = {}

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
            specs = OFFICIAL_SOURCES.get(hid, [])
            ok, why = source_matches(source, specs)
            if not ok:
                errors.append(f"{hid}: source '{source}' rejected official-identity check ({why})")

        # Package coordinates are attached to their ratified harvest entry, not
        # maintained in a second technology registry. A list supports multiple
        # installable packages for one harvested technology.
        coordinates = entry.get("package_coordinates") or []
        if not isinstance(coordinates, list):
            errors.append(f"{hid}: package_coordinates must be a list")
            coordinates = []
        for index, coordinate in enumerate(coordinates):
            label = f"{hid}: package_coordinates[{index}]"
            if not isinstance(coordinate, dict):
                errors.append(f"{label} must be a mapping")
                continue
            for field in PACKAGE_COORDINATE_FIELDS:
                if not str(coordinate.get(field) or "").strip():
                    errors.append(f"{label} missing required field '{field}'")

            ecosystem = str(coordinate.get("ecosystem") or "").strip().lower()
            package = str(coordinate.get("name") or "").strip()
            coordinate_hid = str(coordinate.get("harvest_id") or "").strip()
            usage = str(coordinate.get("approved_usage") or "").strip()
            key = (ecosystem, package.lower())

            if ecosystem not in SUPPORTED_PACKAGE_ECOSYSTEMS:
                errors.append(f"{label} has unsupported ecosystem {ecosystem!r}")
            if ecosystem == "npm" and not NPM_PACKAGE_RE.fullmatch(package):
                errors.append(f"{label} has malformed npm package name {package!r}")
            if coordinate_hid not in EXPECTED_IDS:
                errors.append(f"{label} maps to unknown harvest ID {coordinate_hid!r}")
            elif coordinate_hid != hid:
                errors.append(
                    f"{label} harvest_id {coordinate_hid!r} must match containing entry {hid}"
                )
            if usage not in SUPPORTED_PACKAGE_USAGE:
                errors.append(f"{label} has unsupported approved_usage {usage!r}")
            if usage in {"production", "both"} and license_class == "REVIEW_REQUIRED":
                errors.append(
                    f"{label} cannot approve production use for review-required license {entry.get('license')!r}"
                )
            if key in package_coordinates:
                previous = package_coordinates[key]
                errors.append(
                    f"Duplicate package coordinate {ecosystem}:{package} in {previous['harvest_id']} and {hid}"
                )
            elif ecosystem and package:
                package_coordinates[key] = {
                    "ecosystem": ecosystem,
                    "name": package,
                    "harvest_id": coordinate_hid,
                    "approved_usage": usage,
                    "license_class": license_class,
                }

    # Install/build scripts are deny-by-default. Each exception must map back to
    # an approved package coordinate and carry a human-reviewable rationale.
    build_policy = doc.get("install_build_script_policy")
    approvals: list[dict[str, str]] = []
    if not isinstance(build_policy, dict):
        errors.append("install_build_script_policy must be a mapping")
    else:
        if build_policy.get("default") != "deny":
            errors.append("install_build_script_policy.default must be 'deny'")
        raw_approvals = build_policy.get("approvals")
        if not isinstance(raw_approvals, list):
            errors.append("install_build_script_policy.approvals must be a list")
            raw_approvals = []
        seen_approvals: set[tuple[str, str]] = set()
        for index, approval in enumerate(raw_approvals):
            label = f"install_build_script_policy.approvals[{index}]"
            if not isinstance(approval, dict):
                errors.append(f"{label} must be a mapping")
                continue
            required = ("ecosystem", "package", "harvest_id", "approved", "rationale")
            for field in required:
                value = approval.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{label} missing required field '{field}'")
            ecosystem = str(approval.get("ecosystem") or "").strip().lower()
            package = str(approval.get("package") or "").strip()
            approval_hid = str(approval.get("harvest_id") or "").strip()
            key = (ecosystem, package.lower())
            if approval.get("approved") is not True:
                errors.append(f"{label}.approved must be the boolean true")
            if approval_hid not in EXPECTED_IDS:
                errors.append(f"{label} maps to unknown harvest ID {approval_hid!r}")
            coordinate = package_coordinates.get(key)
            if coordinate is None:
                errors.append(f"{label} references unregistered package coordinate {ecosystem}:{package}")
            elif coordinate["harvest_id"] != approval_hid:
                errors.append(
                    f"{label} harvest_id {approval_hid!r} disagrees with coordinate mapping {coordinate['harvest_id']!r}"
                )
            if key in seen_approvals:
                errors.append(f"Duplicate install/build-script approval for {ecosystem}:{package}")
            seen_approvals.add(key)
            approvals.append(
                {
                    "ecosystem": ecosystem,
                    "package": package,
                    "harvest_id": approval_hid,
                    "rationale": str(approval.get("rationale") or "").strip(),
                }
            )

    counts["package_coordinates"] = len(package_coordinates)
    counts["install_build_script_approvals"] = len(approvals)

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
        "package_coordinates": sorted(package_coordinates.values(), key=lambda item: (item["ecosystem"], item["name"])),
        "install_build_script_approvals": approvals,
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
    lines.append(f"  package coordinates: {result['counts'].get('package_coordinates')}")
    lines.append(f"  install/build-script approvals: {result['counts'].get('install_build_script_approvals')}")
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
