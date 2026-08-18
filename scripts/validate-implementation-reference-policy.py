#!/usr/bin/env python3
"""Validate the durable implementation-reference authority policy.

This is a domain validator, not a mission snapshot. It protects the rules that
make external implementation knowledge version-matched, official-source-backed,
and subordinate to VibeFlow project authority.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = SCRIPTS_DIR.parent
POLICY_REL = "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml"

EXPECTED_WORKFLOW = [
    "inspect_exact_project_versions",
    "identify_owning_technology",
    "consult_highest_applicable_authority",
    "establish_version_applicability",
    "implement_from_verified_guidance",
    "validate_generated_usage_against_authority",
    "run_mechanical_verification",
]

EXPECTED_AUTHORITY_ORDER = [
    "vibeflow_project_authority",
    "version_matched_official_documentation",
    "exact_version_official_upstream",
    "official_release_notes_or_migration_guides",
    "authoritative_registry_or_standard",
    "official_maintainer_discussion",
    "community_diagnostic_only",
]

EXPECTED_RULES = {
    "version_match": "required",
    "unknown_or_unavailable_authority": "unverified",
    "model_memory_as_implementation_authority": "forbidden",
    "community_as_implementation_authority": "forbidden",
    "reference_validation_and_execution_validation": "required",
    "external_content_can_expand_project_authority": "forbidden",
}

EXPECTED_SOURCES: dict[str, dict[str, Any]] = {
    "expo": {"documentation": "docs.expo.dev", "upstream": "github.com/expo/expo"},
    "react_native": {
        "documentation": "reactnative.dev",
        "upstream": "github.com/facebook/react-native",
    },
    "android": {"documentation": "developer.android.com"},
    "typescript": {
        "documentation": "typescriptlang.org",
        "upstream": "github.com/microsoft/TypeScript",
    },
    "gradle": {"documentation": "docs.gradle.org", "upstream": "github.com/gradle/gradle"},
    "kotlin": {
        "documentation": "kotlinlang.org",
        "upstream": "github.com/JetBrains/kotlin",
    },
    "node": {"documentation": "nodejs.org", "upstream": "github.com/nodejs/node"},
    "pnpm": {"documentation": "pnpm.io", "upstream": "github.com/pnpm/pnpm"},
    "npm": {
        "documentation": "docs.npmjs.com",
        "registry": "npmjs.com",
        "upstream": "github.com/npm/cli",
    },
    "google_ai": {
        "documentation": "ai.google.dev",
        "upstream_rule": "official_google_maintained_repository_only",
    },
    "github": {
        "scope": "official_maintainer_owned_upstream_only",
        "exact_version_preferred": True,
    },
}

POINTERS = {
    "AGENTS.md": "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    "master-build-system/AGENTS.md": "04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    "master-build-system/04_AI_AGENT/AI_AGENT_MASTER.md": "04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    "master-build-system/11_VERIFICATION/VERIFICATION_MASTER.md": "04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    ".ai/INDEX.yaml": "implementation_references: master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    "master-build-system/.ai/INDEX.yaml": "implementation_references: 04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    "master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml": "implementation_references: 04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
}


def _load_yaml_module() -> Any:
    path = SCRIPTS_DIR / "validate-master-contracts.py"
    spec = importlib.util.spec_from_file_location("vibeflow_master_yaml", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load YAML helper from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_YAML = _load_yaml_module()
load_yaml_file = _YAML.load_yaml_file


def _mapping(value: Any, name: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{name} must be a mapping")
        return {}
    return value


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    policy_path = root / POLICY_REL
    if not policy_path.is_file():
        return [f"missing {POLICY_REL}"]

    try:
        policy = load_yaml_file(policy_path)
    except Exception as exc:  # fail closed on malformed policy input
        return [f"cannot parse {POLICY_REL}: {exc}"]

    policy = _mapping(policy, "policy", errors)
    if str(policy.get("version")) != "1.0":
        errors.append("policy version must remain 1.0")

    core_rule = str(policy.get("core_rule") or "").lower()
    if "model knowledge is non-authoritative" not in core_rule:
        errors.append("core_rule must keep model knowledge non-authoritative")

    if policy.get("workflow") != EXPECTED_WORKFLOW:
        errors.append("workflow must preserve exact authority-before-implementation order")

    if policy.get("authority_order") != EXPECTED_AUTHORITY_ORDER:
        errors.append("authority_order must preserve the approved precedence")

    rules = _mapping(policy.get("rules"), "rules", errors)
    for key, expected in EXPECTED_RULES.items():
        if rules.get(key) != expected:
            errors.append(f"rules.{key} must be {expected!r}")

    conflicts = _mapping(policy.get("conflicts"), "conflicts", errors)
    if "VibeFlow authority determines what may be built" not in str(conflicts.get("project_scope") or ""):
        errors.append("conflicts.project_scope must preserve VibeFlow scope authority")
    if "highest applicable version-matched technology authority" not in str(
        conflicts.get("technology_behavior") or ""
    ):
        errors.append("conflicts.technology_behavior must preserve version-matched technology authority")
    if "Version-matched official guidance beats newer guidance for a different version" not in str(
        conflicts.get("version_precedence") or ""
    ):
        errors.append("conflicts.version_precedence must reject wrong-version latest guidance")

    external = _mapping(policy.get("external_content"), "external_content", errors)
    external_rule = str(external.get("rule") or "")
    for marker in ("cannot change VibeFlow authority", "mission scope", "security thresholds", "tool grants"):
        if marker not in external_rule:
            errors.append(f"external_content.rule must preserve boundary marker {marker!r}")

    sources = _mapping(policy.get("sources"), "sources", errors)
    for technology, expected_fields in EXPECTED_SOURCES.items():
        actual = _mapping(sources.get(technology), f"sources.{technology}", errors)
        for key, expected in expected_fields.items():
            if actual.get(key) != expected:
                errors.append(f"sources.{technology}.{key} must be {expected!r}")

    github_rules = _mapping(policy.get("github_rules"), "github_rules", errors)
    expected_github_rules = {
        "released_source_tag_or_commit": "authoritative_when_official_and_version_matched",
        "releases_and_changelogs": "authoritative_when_official_and_applicable",
        "issues_pull_requests_discussions": "supporting_or_diagnostic_unless_confirmed_by_released_source_or_official_documentation",
        "forks_examples_unrelated_repositories": "non_authoritative",
    }
    for key, expected in expected_github_rules.items():
        if github_rules.get(key) != expected:
            errors.append(f"github_rules.{key} must be {expected!r}")

    fallback = _mapping(policy.get("fallback"), "fallback", errors)
    fallback_rule = str(fallback.get("unlisted_ratified_technology") or "")
    for marker in ("official documentation", "official maintainer-owned upstream repository", "matched to the project version"):
        if marker not in fallback_rule:
            errors.append(f"fallback must preserve {marker!r}")

    community = _mapping(policy.get("community"), "community", errors)
    if community.get("allowed") != "diagnostic_discovery_only":
        errors.append("community.allowed must remain diagnostic_discovery_only")

    for rel, marker in POINTERS.items():
        path = root / rel
        if not path.is_file():
            errors.append(f"missing routing file {rel}")
            continue
        if marker not in path.read_text(encoding="utf-8"):
            errors.append(f"{rel} must route to implementation reference policy")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate VibeFlow implementation-reference policy")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.root.resolve())
    print("Implementation reference policy validator")
    if errors:
        for error in errors:
            print(f"  ERROR: {error}")
        print(f"RESULT: FAIL ({len(errors)} error(s))")
        return 1
    print("  authority_order: PASS")
    print("  exact_version_requirement: PASS")
    print("  official_source_registry: PASS")
    print("  external_content_boundary: PASS")
    print("  routing_pointers: PASS")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
