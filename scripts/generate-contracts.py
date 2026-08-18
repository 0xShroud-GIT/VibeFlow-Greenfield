#!/usr/bin/env python3
"""M-005 deterministic contract catalog generator (stdlib only).

The Master Build System is authoritative. The artifacts produced here are
DERIVED. This generator reads only the authoritative master files routed by
`00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml`:

    resources -> 02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml
    states    -> 03_BACKEND/STATE_MACHINES.yaml
    events    -> 03_BACKEND/EVENT_CATALOG.yaml

It never parses Replit evidence, README files or mission evidence, and it never
maintains a second hand-written copy of the canonical vocabularies.

Generated artifacts (exact inventory):

    packages/contracts/src/generated/catalog.ts
    packages/contracts/generated/catalog.schema.json
    packages/contracts/generated/catalog.manifest.json

Usage:

    python3 scripts/generate-contracts.py            # write artifacts
    python3 scripts/generate-contracts.py --check     # no writes; drift check

Determinism: output is a pure function of the authoritative input bytes. No
timestamps, hostnames, machine paths, random identifiers or clock values are
emitted, so identical inputs always yield byte-identical outputs.

No third-party dependency is used or required. The YAML subset loader is reused
from `scripts/validate-master-contracts.py` (the repository's already-tested
stdlib loader) rather than reimplemented or replaced by a YAML package.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = SCRIPTS_DIR.parent

GENERATOR_ID = "scripts/generate-contracts.py"
CATALOG_SCHEMA_VERSION = "1.0"
CATALOG_SCHEMA_ID = "urn:vibeflow:contracts:catalog:v1"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

# Authoritative routing keys in SOURCE_OF_TRUTH_INDEX.yaml -> expected target.
REQUIRED_ROUTES = {
    "resources": "02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml",
    "states": "03_BACKEND/STATE_MACHINES.yaml",
    "events": "03_BACKEND/EVENT_CATALOG.yaml",
}

# Event metadata fields that exist in EVENT_CATALOG.yaml and are projected into
# the generated catalog. No field here is invented by M-005.
EVENT_FIELDS = ("id", "name", "resource", "producer", "envelope", "durable")

GENERATED_TS = "packages/contracts/src/generated/catalog.ts"
GENERATED_SCHEMA = "packages/contracts/generated/catalog.schema.json"
GENERATED_MANIFEST = "packages/contracts/generated/catalog.manifest.json"

# Exact generated inventory. Nothing else may appear in the generated trees.
GENERATED_ARTIFACTS = (GENERATED_TS, GENERATED_SCHEMA, GENERATED_MANIFEST)

# Directories owned entirely by this generator (used for unexpected-file checks).
GENERATED_DIRS = (
    "packages/contracts/src/generated",
    "packages/contracts/generated",
)


class GeneratorError(RuntimeError):
    """Raised when authority is missing, malformed or mis-routed."""


def _load_yaml_module() -> Any:
    """Load the repository's stdlib YAML-subset loader.

    Reuses `scripts/validate-master-contracts.py` so there is exactly one
    tested YAML subset implementation in the repository. Its public
    `load_yaml_file(...)` behaviour is unchanged by M-005.
    """
    spec = importlib.util.spec_from_file_location(
        "validate_master_contracts", SCRIPTS_DIR / "validate-master-contracts.py"
    )
    if spec is None or spec.loader is None:
        raise GeneratorError("cannot load scripts/validate-master-contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_YAML = _load_yaml_module()
load_yaml_file = _YAML.load_yaml_file


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_dumps(data: Any) -> str:
    """Deterministic JSON rendering used for every generated JSON artifact."""
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def ts_string(value: str) -> str:
    """Render a TypeScript double-quoted string literal deterministically."""
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Authority loading
# ---------------------------------------------------------------------------


class Authority:
    """The authoritative inputs, loaded and structurally validated."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.mbs = root / "master-build-system"
        self._load_routes()
        self._load_resources()
        self._load_state_machines()
        self._load_events()

    # -- routing ----------------------------------------------------------

    def _load_routes(self) -> None:
        sot_path = self.mbs / "00_MASTER" / "SOURCE_OF_TRUTH_INDEX.yaml"
        if not sot_path.is_file():
            raise GeneratorError(f"missing authority index: {sot_path}")
        sot = load_yaml_file(sot_path)
        if not isinstance(sot, dict):
            raise GeneratorError("SOURCE_OF_TRUTH_INDEX.yaml did not parse as a mapping")

        self.source_of_truth_index = sot
        for key, expected in REQUIRED_ROUTES.items():
            actual = str(sot.get(key) or "")
            if actual != expected:
                raise GeneratorError(
                    f"SOURCE_OF_TRUTH_INDEX.yaml routes {key!r} to {actual!r}, expected {expected!r}"
                )

        self.route_paths: dict[str, Path] = {}
        for key, rel in REQUIRED_ROUTES.items():
            path = self.mbs / rel
            if not path.is_file():
                raise GeneratorError(f"authoritative source missing: master-build-system/{rel}")
            self.route_paths[key] = path

        # Ordered list of authoritative inputs, index file first.
        self.source_paths: list[str] = [
            "master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml",
            *(f"master-build-system/{REQUIRED_ROUTES[key]}" for key in ("resources", "states", "events")),
        ]

    # -- resources --------------------------------------------------------

    def _load_resources(self) -> None:
        doc = load_yaml_file(self.route_paths["resources"])
        entries = (doc or {}).get("resources") or []
        names: list[str] = []
        for entry in entries:
            name = str((entry or {}).get("resource") or "").strip()
            if not name:
                raise GeneratorError("CANONICAL_RESOURCE_MODEL.yaml has a resource without a name")
            names.append(name)
        if len(names) != len(set(names)):
            raise GeneratorError("CANONICAL_RESOURCE_MODEL.yaml contains duplicate resource names")
        if not names:
            raise GeneratorError("CANONICAL_RESOURCE_MODEL.yaml defines no resources")
        self.resources = names  # canonical file order preserved

    # -- state machines ---------------------------------------------------

    def _load_state_machines(self) -> None:
        doc = load_yaml_file(self.route_paths["states"])
        machines = (doc or {}).get("machines") or {}
        if not isinstance(machines, dict) or not machines:
            raise GeneratorError("STATE_MACHINES.yaml defines no machines")

        self.machines: dict[str, dict[str, list[str]]] = {}
        for name, machine in machines.items():
            machine_name = str(name).strip()
            if not machine_name.isidentifier():
                raise GeneratorError(
                    f"state machine name is not a usable identifier: {machine_name!r}"
                )
            states = [str(s) for s in ((machine or {}).get("states") or [])]
            terminal = [str(s) for s in ((machine or {}).get("terminal") or [])]
            if not states:
                raise GeneratorError(f"state machine {machine_name} has no states")
            if len(states) != len(set(states)):
                raise GeneratorError(f"state machine {machine_name} has duplicate states")
            if len(terminal) != len(set(terminal)):
                raise GeneratorError(f"state machine {machine_name} has duplicate terminal states")
            missing = [s for s in terminal if s not in states]
            if missing:
                raise GeneratorError(
                    f"state machine {machine_name} terminal states are not a subset of states: {missing}"
                )
            if not terminal:
                raise GeneratorError(f"state machine {machine_name} declares no terminal states")
            self.machines[machine_name] = {"states": states, "terminal": terminal}

    # -- events -----------------------------------------------------------

    def _load_events(self) -> None:
        doc = load_yaml_file(self.route_paths["events"])
        entries = (doc or {}).get("events") or []
        if not entries:
            raise GeneratorError("EVENT_CATALOG.yaml defines no events")

        catalog: list[dict[str, Any]] = []
        for entry in entries:
            record: dict[str, Any] = {}
            for field in EVENT_FIELDS:
                if field not in (entry or {}):
                    raise GeneratorError(
                        f"EVENT_CATALOG.yaml entry {entry.get('id')!r} is missing field {field!r}"
                    )
                value = entry[field]
                record[field] = value if isinstance(value, bool) else str(value)
            catalog.append(record)

        ids = [item["id"] for item in catalog]
        names = [item["name"] for item in catalog]
        if len(ids) != len(set(ids)):
            raise GeneratorError("EVENT_CATALOG.yaml contains duplicate event IDs")
        if len(names) != len(set(names)):
            raise GeneratorError("EVENT_CATALOG.yaml contains duplicate event names")

        self.events = catalog  # canonical file order preserved
        self.event_ids = ids
        self.event_names = names

    # -- derived ----------------------------------------------------------

    @property
    def machine_names(self) -> list[str]:
        return list(self.machines)

    def source_hashes(self) -> dict[str, str]:
        return {rel: sha256_file(self.root / rel) for rel in self.source_paths}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def string_enum_schema(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def render_catalog_ts(authority: Authority) -> str:
    """Render packages/contracts/src/generated/catalog.ts."""

    def const_enum(name: str, values: list[str], doc: str) -> list[str]:
        members = ",\n".join(f"    {ts_string(v)}" for v in values)
        return [
            f"/** {doc} */",
            f"export const {name} = {{",
            '  type: "string",',
            "  enum: [",
            members,
            "  ]",
            "} as const;",
            "",
        ]

    lines: list[str] = [
        "/**",
        " * GENERATED FILE — DO NOT EDIT.",
        " *",
        f" * Produced by {GENERATOR_ID} from the VibeFlow Master Build System.",
        " * Authoritative inputs (routed by 00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml):",
        " *   resources -> 02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml",
        " *   states    -> 03_BACKEND/STATE_MACHINES.yaml",
        " *   events    -> 03_BACKEND/EVENT_CATALOG.yaml",
        " *",
        " * Contracts are JSON Schema first. Every TypeScript type below is derived",
        " * from its raw JSON Schema literal via TypeBox `Static<>` inference; no",
        " * parallel handwritten union vocabulary is maintained here.",
        " *",
        " * Regenerate:  pnpm run contracts:generate",
        " * Verify:      pnpm run contracts:check",
        " */",
        "",
        'import type { Static } from "typebox";',
        "",
        "/** Catalog identity, stable across regeneration of identical inputs. */",
        f"export const CONTRACT_CATALOG_ID = {ts_string(CATALOG_SCHEMA_ID)} as const;",
        "",
        f"export const CONTRACT_CATALOG_SCHEMA_VERSION = {ts_string(CATALOG_SCHEMA_VERSION)} as const;",
        "",
        "// ---------------------------------------------------------------------------",
        "// Canonical resources (02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml)",
        "// ---------------------------------------------------------------------------",
        "",
        "/** Canonical resource names in authoritative file order. */",
        "export const CANONICAL_RESOURCES = [",
    ]
    lines.extend(f"  {ts_string(name)}," for name in authority.resources)
    lines.extend(
        [
            "] as const;",
            "",
        ]
    )
    lines.extend(
        const_enum(
            "CanonicalResourceNameSchema",
            authority.resources,
            "JSON Schema for the canonical resource-name vocabulary.",
        )
    )
    lines.extend(
        [
            "export type CanonicalResourceName = Static<typeof CanonicalResourceNameSchema>;",
            "",
            "// ---------------------------------------------------------------------------",
            "// State machines (03_BACKEND/STATE_MACHINES.yaml)",
            "// ---------------------------------------------------------------------------",
            "",
            "/** Canonical state-machine names in authoritative file order. */",
            "export const STATE_MACHINE_NAMES = [",
        ]
    )
    lines.extend(f"  {ts_string(name)}," for name in authority.machine_names)
    lines.extend(["] as const;", ""])
    lines.extend(
        const_enum(
            "StateMachineNameSchema",
            authority.machine_names,
            "JSON Schema for the canonical state-machine-name vocabulary.",
        )
    )
    lines.append("export type StateMachineName = Static<typeof StateMachineNameSchema>;")
    lines.append("")

    for machine in authority.machine_names:
        states = authority.machines[machine]["states"]
        terminal = authority.machines[machine]["terminal"]
        lines.extend(
            const_enum(
                f"{machine}StateSchema",
                states,
                f"JSON Schema for the canonical {machine} states.",
            )
        )
        lines.append(f"export type {machine}State = Static<typeof {machine}StateSchema>;")
        lines.append("")
        lines.extend(
            const_enum(
                f"{machine}TerminalStateSchema",
                terminal,
                f"JSON Schema for the canonical {machine} terminal states.",
            )
        )
        lines.append(
            f"export type {machine}TerminalState = Static<typeof {machine}TerminalStateSchema>;"
        )
        lines.append("")

    lines.extend(
        [
            "// ---------------------------------------------------------------------------",
            "// Events (03_BACKEND/EVENT_CATALOG.yaml)",
            "// ---------------------------------------------------------------------------",
            "",
            "/** Canonical event IDs in authoritative file order. */",
            "export const EVENT_IDS = [",
        ]
    )
    lines.extend(f"  {ts_string(v)}," for v in authority.event_ids)
    lines.extend(
        [
            "] as const;",
            "",
            "/** Canonical event names in authoritative file order. */",
            "export const EVENT_NAMES = [",
        ]
    )
    lines.extend(f"  {ts_string(v)}," for v in authority.event_names)
    lines.extend(["] as const;", ""])
    lines.extend(
        const_enum("EventIdSchema", authority.event_ids, "JSON Schema for canonical event IDs.")
    )
    lines.append("export type EventId = Static<typeof EventIdSchema>;")
    lines.append("")
    lines.extend(
        const_enum("EventNameSchema", authority.event_names, "JSON Schema for canonical event names.")
    )
    lines.append("export type EventName = Static<typeof EventNameSchema>;")
    lines.extend(
        [
            "",
            "/**",
            " * Canonical event catalog metadata in authoritative file order.",
            " *",
            " * Only metadata that EVENT_CATALOG.yaml actually defines is projected here.",
            " * Event payload schemas are intentionally absent: no authoritative domain",
            " * mission has defined them yet, and M-005 does not manufacture authority.",
            " */",
            "export const EVENT_CATALOG = [",
        ]
    )
    for event in authority.events:
        fields = ", ".join(
            f"{field}: " + ("true" if event[field] is True else "false" if event[field] is False else ts_string(event[field]))
            for field in EVENT_FIELDS
        )
        lines.append(f"  {{ {fields} }},")
    lines.extend(
        [
            "] as const;",
            "",
            "/** One canonical event-catalog row, derived from the generated catalog data. */",
            "export type EventCatalogEntry = (typeof EVENT_CATALOG)[number];",
            "",
        ]
    )
    return "\n".join(lines)


def render_catalog_schema(authority: Authority) -> str:
    """Render packages/contracts/generated/catalog.schema.json."""
    defs: dict[str, Any] = {
        "CanonicalResourceName": string_enum_schema(authority.resources),
        "StateMachineName": string_enum_schema(authority.machine_names),
    }
    for machine in authority.machine_names:
        defs[f"{machine}State"] = string_enum_schema(authority.machines[machine]["states"])
        defs[f"{machine}TerminalState"] = string_enum_schema(authority.machines[machine]["terminal"])
    defs["EventId"] = string_enum_schema(authority.event_ids)
    defs["EventName"] = string_enum_schema(authority.event_names)

    bundle = {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": CATALOG_SCHEMA_ID,
        "title": "VibeFlow canonical contract catalog",
        "description": (
            "Generated JSON Schema bundle derived from the VibeFlow Master Build System. "
            "DO NOT EDIT: regenerate with scripts/generate-contracts.py."
        ),
        "$defs": defs,
    }
    return json_dumps(bundle)


def render_catalog_manifest(authority: Authority) -> str:
    """Render packages/contracts/generated/catalog.manifest.json."""
    manifest = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_id": CATALOG_SCHEMA_ID,
        "generator": GENERATOR_ID,
        "json_schema_dialect": JSON_SCHEMA_DIALECT,
        "authority": (
            "master-build-system is authoritative; these artifacts are derived. "
            "Regenerate rather than edit."
        ),
        "sources": [
            {"path": rel, "sha256": sha256_file(authority.root / rel)}
            for rel in authority.source_paths
        ],
        "counts": {
            "canonical_resources": len(authority.resources),
            "state_machines": len(authority.machine_names),
            "events": len(authority.events),
        },
        "artifacts": list(GENERATED_ARTIFACTS),
    }
    return json_dumps(manifest)


def build_artifacts(root: Path) -> dict[str, str]:
    """Produce the full expected artifact set in memory (no writes)."""
    authority = Authority(root)
    return {
        GENERATED_TS: render_catalog_ts(authority),
        GENERATED_SCHEMA: render_catalog_schema(authority),
        GENERATED_MANIFEST: render_catalog_manifest(authority),
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def existing_generated_files(root: Path) -> list[str]:
    found: list[str] = []
    for rel_dir in GENERATED_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                found.append(path.relative_to(root).as_posix())
    return sorted(found)


def do_write(root: Path) -> int:
    artifacts = build_artifacts(root)
    for rel, content in artifacts.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # Remove stale files the generator no longer owns.
    expected = set(GENERATED_ARTIFACTS)
    for rel in existing_generated_files(root):
        if rel not in expected:
            (root / rel).unlink()
            print(f"  removed stale generated file: {rel}")
    print("Contract catalog generated")
    for rel in GENERATED_ARTIFACTS:
        print(f"  wrote {rel}")
    return 0


def do_check(root: Path) -> int:
    """Regenerate in memory and compare against tracked output. No writes."""
    errors: list[str] = []
    try:
        artifacts = build_artifacts(root)
    except GeneratorError as exc:
        print("Contract catalog check FAILED")
        print(f"  ERROR: authority error: {exc}")
        return 1

    expected = set(GENERATED_ARTIFACTS)
    present = set(existing_generated_files(root))

    for rel in sorted(expected - present):
        errors.append(f"missing generated artifact: {rel}")
    for rel in sorted(present - expected):
        errors.append(f"unexpected file in generated output tree: {rel}")

    for rel in GENERATED_ARTIFACTS:
        path = root / rel
        if not path.is_file():
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != artifacts[rel]:
            errors.append(
                f"stale generated artifact: {rel} "
                f"(tracked sha256={sha256_bytes(actual.encode('utf-8'))[:16]}, "
                f"expected sha256={sha256_bytes(artifacts[rel].encode('utf-8'))[:16]}) "
                "— run: pnpm run contracts:generate"
            )

    if errors:
        print("Contract catalog check FAILED")
        for error in errors:
            print(f"  ERROR: {error}")
        print(f"Total errors: {len(errors)}")
        return 1

    print("Contract catalog check PASSED")
    print(f"  artifacts={len(GENERATED_ARTIFACTS)} up to date with master-build-system authority")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the VibeFlow contract catalog from Master Build System authority"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write. Regenerate in memory and fail on missing/stale/unexpected output.",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        if args.check:
            return do_check(root)
        return do_write(root)
    except GeneratorError as exc:
        print("Contract catalog generation FAILED")
        print(f"  ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
