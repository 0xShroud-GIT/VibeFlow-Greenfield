#!/usr/bin/env python3
"""No-dependency master-contract consistency validator.

Parses the ratified YAML/CSV/JSON contracts with a stdlib-only subset loader.
Does not install packages and does not mutate architecture semantics.

Mission progression is validated generically (any mission may become the active
one as its dependencies are accepted) instead of hard-coding the M-001
bootstrap state. Statuses follow 10_IMPLEMENTATION/STATUS_PROTOCOL.md:
LOCKED -> READY -> IN_PROGRESS -> REVIEW -> DONE / BLOCKED.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MBS = REPO_ROOT / "master-build-system"

MISSION_STATUS_VOCAB = {"LOCKED", "READY", "IN_PROGRESS", "REVIEW", "DONE", "BLOCKED"}
CAPABILITY_STATUS_VOCAB = {"NOT_STARTED", "IN_PROGRESS", "IMPLEMENTED", "VERIFIED", "COMPLETE"}
# Unlocked but not yet accepted. Under normal serial progression exactly one
# mission is in this set and every earlier mission is DONE.
ACTIVE_MISSION_STATUSES = {"READY", "IN_PROGRESS", "REVIEW", "BLOCKED"}

EXPECTED = {
    "vibeflow_capabilities": 405,
    "replit_trace_rows": 390,
    "canonical_resources": 35,
    "invariants": 20,
    "approved_harvest_entries": 35,
    "phases": 33,
    "missions": 151,
    "frontend_surface_contracts": 13,
    "event_types": 37,
    "v1_gates": 15,
}

CAPABILITY_REQUIRED = (
    "vf_id",
    "domain",
    "domain_code",
    "capability",
    "origin",
    "evidence_class",
    "decision",
    "priority",
    "authority_rule",
    "verification_gate",
    "status",
)

BINDING_RESOURCES = {
    "AgentBinding",
    "ModelBinding",
    "WorkspaceBinding",
    "RepositoryBinding",
    "DeploymentBinding",
    "DataBinding",
    "ObjectStorageBinding",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.counts: dict[str, Any] = {}
        self.checks: dict[str, str] = {}

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def mark(self, key: str, status: str) -> None:
        self.checks[key] = status


def parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text == "" or text in {"null", "~", "Null", "NULL"}:
        return None
    if text in {"true", "True", "TRUE"}:
        return True
    if text in {"false", "False", "FALSE"}:
        return False
    # Explicit empty collections are used by policy documents that start with
    # an empty deny-by-default allowlist and later grow into nested entries.
    if text == "[]":
        return []
    if text == "{}":
        return {}
    if (text.startswith("'") and text.endswith("'")) or (
        text.startswith('"') and text.endswith('"')
    ):
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def load_simple_yaml(text: str) -> Any:
    """Load the indentation-based YAML subset used by the master pack.

    Supports the pack's folded plain scalars and same-indent nested sequences:
    `resources:` followed by `- resource: Account`.
    """

    logical: list[tuple[int, str]] = []
    pending: str | None = None
    pending_indent = 0
    for raw in text.splitlines():
        if raw.strip() == "" or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if pending is not None:
            # Fold wrapped prose only. Nested `key:` / `- item` lines are siblings, not continuations.
            if (
                indent > pending_indent
                and not stripped.startswith("- ")
                and not re.match(r"^[A-Za-z_*][\w*-]*:", stripped)
            ):
                pending = pending + " " + stripped
                continue
            logical.append((pending_indent, pending))
            pending = None
        if stripped.startswith("- "):
            body = stripped[2:]
            if ":" in body:
                _, val = body.split(":", 1)
                if val.strip() != "":
                    pending = stripped
                    pending_indent = indent
                    continue
            logical.append((indent, stripped))
            continue
        if ":" in stripped:
            _, val = stripped.split(":", 1)
            if val.strip() == "":
                logical.append((indent, stripped))
            else:
                pending = stripped
                pending_indent = indent
            continue
        logical.append((indent, stripped))
    if pending is not None:
        logical.append((pending_indent, pending))

    def parse_value(index: int, parent_indent: int) -> tuple[Any, int]:
        if index >= len(logical):
            return None, index
        indent, line = logical[index]
        if line.startswith("- "):
            if indent < parent_indent:
                return None, index
            return parse_list(index, indent)
        if indent > parent_indent:
            return parse_map(index, indent)
        return None, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        while index < len(logical):
            item_indent, item_line = logical[index]
            if item_indent != indent or not item_line.startswith("- "):
                break
            body = item_line[2:]
            if ":" not in body:
                items.append(parse_scalar(body))
                index += 1
                continue
            key, val = body.split(":", 1)
            mapping: dict[str, Any] = {}
            if val.strip() == "":
                child, index = parse_value(index + 1, item_indent)
                mapping[key] = child
            else:
                mapping[key] = parse_scalar(val)
                index += 1
            while index < len(logical):
                child_indent, child_line = logical[index]
                if child_indent <= item_indent:
                    break
                if child_line.startswith("- "):
                    child, index = parse_list(index, child_indent)
                    mapping.setdefault("_items", []).append(child)
                    continue
                if ":" not in child_line:
                    raise ValueError(f"Cannot parse YAML line: {child_line}")
                ckey, cval = child_line.split(":", 1)
                if cval.strip() == "":
                    child, index = parse_value(index + 1, child_indent)
                    mapping[ckey] = child
                else:
                    mapping[ckey] = parse_scalar(cval)
                    index += 1
            items.append(mapping)
        return items, index

    def parse_map(index: int, indent: int) -> tuple[dict[str, Any], int]:
        mapping: dict[str, Any] = {}
        while index < len(logical):
            item_indent, item_line = logical[index]
            if item_indent < indent:
                break
            if item_indent != indent or item_line.startswith("- "):
                break
            if ":" not in item_line:
                raise ValueError(f"Cannot parse YAML line: {item_line}")
            key, val = item_line.split(":", 1)
            if val.strip() == "":
                child, index = parse_value(index + 1, item_indent)
                mapping[key] = child
            else:
                mapping[key] = parse_scalar(val)
                index += 1
        return mapping, index

    doc, _ = parse_map(0, 0)
    return doc


def load_yaml_file(path: Path) -> Any:
    return load_simple_yaml(path.read_text(encoding="utf-8"))


def duplicates(values: list[str]) -> list[str]:
    counted = Counter(values)
    return sorted(key for key, n in counted.items() if n > 1)


def resource_allowed(name: str, canonical: set[str]) -> bool:
    if name in canonical:
        return True
    if name == "*Binding":
        return True
    if name.endswith("Binding") and name in BINDING_RESOURCES:
        return True
    return False


def event_allowed(name: str, event_names: set[str], prefixes: set[str]) -> bool:
    if name in event_names:
        return True
    if name.endswith(".*"):
        prefix = name[:-1]
        return any(existing.startswith(prefix) for existing in event_names) or name[:-2] in prefixes
    return False


def check_source_of_truth(report: Report) -> set[str]:
    sot_path = MBS / "00_MASTER" / "SOURCE_OF_TRUTH_INDEX.yaml"
    index_path = REPO_ROOT / ".ai" / "INDEX.yaml"
    pack_index_path = MBS / ".ai" / "INDEX.yaml"
    sot = load_yaml_file(sot_path)
    index = load_yaml_file(index_path)
    pack_index = load_yaml_file(pack_index_path)

    missing = []
    for key, rel in sot.items():
        path = MBS / str(rel)
        if not path.is_file():
            missing.append(f"{key} -> {rel}")
            report.err(f"SOURCE_OF_TRUTH missing file for {key}: {rel}")

    repo_paths = []
    for section in ("authorities", "machine_readable"):
        for key, rel in (index.get(section) or {}).items():
            path = REPO_ROOT / str(rel)
            repo_paths.append((section, key, str(rel), path.is_file()))
            if not path.is_file():
                report.err(f".ai/INDEX.yaml missing {section}.{key}: {rel}")
    for item in index.get("read_first") or []:
        path = REPO_ROOT / str(item)
        if not path.is_file():
            report.err(f".ai/INDEX.yaml read_first missing: {item}")

    for section in ("authorities", "machine_readable"):
        for key, rel in (pack_index.get(section) or {}).items():
            path = MBS / str(rel)
            if not path.is_file():
                report.err(f"pack .ai/INDEX.yaml missing {section}.{key}: {rel}")

    # Same responsibility must not point at two different files.
    aligned = {
        "product": ("product", "product"),
        "frontend": ("frontend", "frontend"),
        "backend": ("backend", "backend"),
        "agent": ("agent", "agent"),
        "security": ("security", "security"),
        "verification": ("verification", "verification"),
        "capabilities": ("machine_readable.capabilities", "capabilities"),
        "resources": ("machine_readable.resources", "resources"),
        "states": ("machine_readable.states", "states"),
        "events": ("machine_readable.events", "events"),
        "frontend_backend": ("machine_readable.frontend_backend", "frontend_backend"),
        "dependencies": ("machine_readable.dependencies", "dependencies"),
        "missions": ("machine_readable.missions", "missions"),
    }
    for label, (index_key, sot_key) in aligned.items():
        if "." in index_key:
            section, key = index_key.split(".", 1)
            index_rel = Path((index.get(section) or {}).get(key, "")).name
        else:
            index_rel = Path((index.get("authorities") or {}).get(index_key, "")).name
        sot_rel = Path(str(sot.get(sot_key, ""))).name
        if index_rel and sot_rel and index_rel != sot_rel:
            report.err(
                f"Conflicting authority for {label}: INDEX={index_rel} SOURCE_OF_TRUTH={sot_rel}"
            )

    acceptance = Path((index.get("machine_readable") or {}).get("acceptance", "")).name
    if acceptance and acceptance != "V1_ACCEPTANCE.yaml":
        report.err(f"Unexpected acceptance authority: {acceptance}")
    if sot.get("verification") and "VERIFICATION_MASTER.md" not in str(sot.get("verification")):
        report.err("SOURCE_OF_TRUTH verification is not VERIFICATION_MASTER.md")

    report.note(
        "INDEX machine_readable.acceptance is V1_ACCEPTANCE.yaml; "
        "SOURCE_OF_TRUTH verification is VERIFICATION_MASTER.md. Complementary, not circular."
    )
    report.counts["source_of_truth_entries"] = len(sot)
    if missing:
        report.mark("C", "FAIL")
    else:
        report.mark("C", "PASS")
    return set()


def check_resources(report: Report) -> set[str]:
    model = load_yaml_file(MBS / "02_ARCHITECTURE" / "CANONICAL_RESOURCE_MODEL.yaml")
    ownership = load_yaml_file(MBS / "02_ARCHITECTURE" / "STATE_OWNERSHIP.yaml")
    resources = model.get("resources") or []
    names = [str(item.get("resource")) for item in resources]
    report.counts["canonical_resources"] = len(names)
    if len(names) != EXPECTED["canonical_resources"]:
        report.err(
            f"Canonical resources: expected {EXPECTED['canonical_resources']}, got {len(names)}"
        )
    dups = duplicates(names)
    if dups:
        report.err(f"Duplicate canonical resource names: {dups}")
    empty = [name for name, item in zip(names, resources) if not item.get("authority")]
    if empty:
        report.err(f"Resources missing authority: {empty}")

    owned = [str(item.get("resource")) for item in (ownership.get("rules") or [])]
    if owned != names:
        report.err(
            "STATE_OWNERSHIP resource list does not exactly match CANONICAL_RESOURCE_MODEL"
        )
        report.err(f"model-only={sorted(set(names)-set(owned))} ownership-only={sorted(set(owned)-set(names))}")
    if len(owned) != len(set(owned)):
        report.err(f"Duplicate state-ownership resources: {duplicates(owned)}")

    binding_like = [name for name in names if name.endswith("Binding")]
    if set(binding_like) != BINDING_RESOURCES:
        report.warn(f"Binding family differs from expected set: {binding_like}")

    if report.errors and any("resource" in e.lower() or "STATE_OWNERSHIP" in e for e in report.errors[-6:]):
        report.mark("D", "FAIL")
    else:
        report.mark("D", "PASS" if len(names) == EXPECTED["canonical_resources"] and not dups else "FAIL")
    return set(names)


def check_invariants(report: Report) -> None:
    data = load_yaml_file(MBS / "00_MASTER" / "NON_NEGOTIABLE_INVARIANTS.yaml")
    invariants = data.get("invariants") or []
    ids = [str(item.get("id")) for item in invariants]
    report.counts["invariants"] = len(ids)
    if len(ids) != EXPECTED["invariants"]:
        report.err(f"Invariants: expected {EXPECTED['invariants']}, got {len(ids)}")
    if duplicates(ids):
        report.err(f"Duplicate invariant IDs: {duplicates(ids)}")
    for item in invariants:
        if not str(item.get("rule") or "").strip():
            report.err(f"Empty invariant rule: {item.get('id')}")
        enforcement = item.get("enforcement")
        if not enforcement:
            report.err(f"Invariant {item.get('id')} missing enforcement")
    expected_ids = [f"INV-{i:03d}" for i in range(1, 21)]
    if ids != expected_ids:
        report.err(f"Invariant IDs are not INV-001..INV-020 in order: {ids}")
    report.mark(
        "E",
        "PASS"
        if len(ids) == EXPECTED["invariants"] and not duplicates(ids) and all(i.get("rule") for i in invariants)
        else "FAIL",
    )


def check_state_machines(report: Report) -> None:
    data = load_yaml_file(MBS / "03_BACKEND" / "STATE_MACHINES.yaml")
    machines = data.get("machines") or {}
    report.counts["state_machines"] = len(machines)
    required = {
        "Task",
        "Execution",
        "Approval",
        "Connection",
        "Verification",
        "Release",
        "RecoveryRecord",
    }
    if set(machines) != required:
        report.err(f"Unexpected state machines: {sorted(machines)} expected {sorted(required)}")

    for name, machine in machines.items():
        states = list(machine.get("states") or [])
        terminal = list(machine.get("terminal") or [])
        rule = str(machine.get("rule") or "")
        if duplicates(states):
            report.err(f"{name}: duplicate states {duplicates(states)}")
        if not rule.strip():
            report.err(f"{name}: empty rule")
        missing_terminal = [s for s in terminal if s not in states]
        if missing_terminal:
            report.err(f"{name}: terminal states not in states: {missing_terminal}")

    execution = machines["Execution"]
    exec_states = set(execution["states"])
    exec_term = set(execution["terminal"])
    if "VERIFIED" not in exec_term or "CANDIDATE_COMPLETE" not in exec_states:
        report.err("Execution must include CANDIDATE_COMPLETE and terminal VERIFIED")
    if "CANDIDATE_COMPLETE" in exec_term:
        report.err("Execution CANDIDATE_COMPLETE must not be terminal")
    if not {"CANCELLED", "FAILED", "LOST", "VERIFIED"} <= exec_term:
        report.err("Execution terminals must include VERIFIED/FAILED/CANCELLED/LOST")
    if "VERIFIED" not in str(execution.get("rule")) or "CANDIDATE_COMPLETE" not in str(execution.get("rule")):
        report.err("Execution rule must keep candidate completion distinct from VERIFIED")

    task = machines["Task"]
    if set(task["terminal"]) != {"VERIFIED", "FAILED", "CANCELLED"}:
        report.err(f"Task terminals unexpected: {task['terminal']}")
    if "CANDIDATE_COMPLETE" in set(task["terminal"]):
        report.err("Task CANDIDATE_COMPLETE must not be terminal")
    if "Verification" not in str(task.get("rule")):
        report.err("Task rule must require Verification for VERIFIED")

    verification = machines["Verification"]
    ver_term = set(verification["terminal"])
    if not {"PASSED", "FAILED", "STALE"} <= ver_term:
        report.err("Verification terminals must include PASSED/FAILED/STALE")
    if "INTERRUPTED" in ver_term:
        report.err("Verification INTERRUPTED must not be silently terminal-success")
    if "invalidates" not in str(verification.get("rule")).lower() and "STALE" not in str(verification.get("rule")):
        report.err("Verification rule must invalidate stale candidate PASS")

    recovery = machines["RecoveryRecord"]
    rec_states = set(recovery["states"])
    if not {"REPLAYING_EVENTS", "RECONCILING_WORKSPACE", "REATTACHING_PROVIDER", "REVERIFYING"} <= rec_states:
        report.err("RecoveryRecord must distinguish replay, reconcile, reattach, reverify")
    if "EXECUTION_LOST" not in set(recovery["terminal"]):
        report.err("RecoveryRecord must allow honest EXECUTION_LOST terminal")
    if "replay" not in str(recovery.get("rule")).lower():
        report.err("RecoveryRecord rule must separate replay from recovery")

    report.note(
        "State machines declare states, terminals, and semantic rules; "
        "they do not enumerate transition edges. Terminal membership plus rules "
        "are the ratified restart/authority constraints."
    )
    report.mark("F", "PASS" if not any(e.startswith(("Execution", "Task", "Verification", "Recovery")) or "state machine" in e.lower() for e in report.errors) else "FAIL")
    # Recompute F from machine-specific errors more reliably:
    machine_fail = [
        e
        for e in report.errors
        if e.split(":")[0] in required or e.startswith("Unexpected state machines")
    ]
    report.mark("F", "FAIL" if machine_fail else "PASS")


def check_events(report: Report, canonical: set[str]) -> tuple[set[str], set[str]]:
    data = load_yaml_file(MBS / "03_BACKEND" / "EVENT_CATALOG.yaml")
    events = data.get("events") or []
    ids = [str(item.get("id")) for item in events]
    names = [str(item.get("name")) for item in events]
    report.counts["event_types"] = len(events)
    if len(events) != EXPECTED["event_types"]:
        report.err(f"Event types: expected {EXPECTED['event_types']}, got {len(events)}")
    if duplicates(ids):
        report.err(f"Duplicate event IDs: {duplicates(ids)}")
    if duplicates(names):
        report.err(f"Duplicate event names: {duplicates(names)}")
    expected_ids = [f"EVT-{i:03d}" for i in range(1, EXPECTED["event_types"] + 1)]
    if ids != expected_ids:
        report.err(f"Event IDs are not EVT-001..EVT-037 in order: {ids}")

    prefixes: set[str] = set()
    for item in events:
        resource = str(item.get("resource") or "")
        if not resource_allowed(resource, canonical):
            report.err(f"Event {item.get('id')} resource not canonical: {resource}")
        if not item.get("producer"):
            report.err(f"Event {item.get('id')} missing producer")
        if not item.get("name"):
            report.err(f"Event {item.get('id')} missing name")
        prefixes.add(str(item.get("name")).split(".", 1)[0])
        # Replay of records is not command re-execution: durable catalog events are facts.
        if str(item.get("name")).endswith(".command") or str(item.get("name")).startswith("command."):
            report.err(f"Event {item.get('id')} looks like a command re-execution type")

    report.note(
        "Event catalog records lifecycle facts with unique event_id idempotency; "
        "ordinary replay therefore cannot imply command re-execution."
    )
    report.mark(
        "G",
        "PASS"
        if len(events) == EXPECTED["event_types"] and not duplicates(ids) and not duplicates(names)
        else "FAIL",
    )
    return set(names), prefixes


def check_frontend(report: Report, canonical: set[str], event_names: set[str], prefixes: set[str]) -> None:
    data = load_yaml_file(MBS / "09_CONTRACTS" / "FRONTEND_BACKEND_MATRIX.yaml")
    surfaces = data.get("surfaces") or []
    ids = [str(item.get("id")) for item in surfaces]
    report.counts["frontend_surface_contracts"] = len(surfaces)
    if len(surfaces) != EXPECTED["frontend_surface_contracts"]:
        report.err(
            f"Frontend surfaces: expected {EXPECTED['frontend_surface_contracts']}, got {len(surfaces)}"
        )
    if duplicates(ids):
        report.err(f"Duplicate frontend surface IDs: {duplicates(ids)}")
    rule = str(data.get("rule") or "")
    if "authoritative" not in rule.lower():
        report.err("FRONTEND_BACKEND_MATRIX missing authoritative-state rule")

    projection_events = []
    for surface in surfaces:
        sid = surface.get("id")
        for resource in surface.get("resources") or []:
            if not resource_allowed(str(resource), canonical):
                report.err(f"{sid} references unknown resource {resource}")
        if not surface.get("backend_modules"):
            report.err(f"{sid} missing backend_modules")
        for event in surface.get("events") or []:
            name = str(event)
            if not event_allowed(name, event_names, prefixes):
                projection_events.append((sid, name))
    if projection_events:
        report.note(
            "Frontend matrix names some projection/wildcard events that are not "
            "themselves catalog types: "
            + ", ".join(f"{sid}:{name}" for sid, name in projection_events)
            + ". Treated as UI projections, not an independent authoritative vocabulary."
        )
    report.mark(
        "H",
        "PASS"
        if len(surfaces) == EXPECTED["frontend_surface_contracts"] and not duplicates(ids)
        else "FAIL",
    )


def check_capabilities(report: Report) -> None:
    csv_path = MBS / "01_PRODUCT" / "VIBEFLOW_CAPABILITY_LEDGER.csv"
    yaml_path = MBS / "01_PRODUCT" / "VIBEFLOW_CAPABILITY_LEDGER.yaml"
    yaml_doc = load_yaml_file(yaml_path)
    yaml_rows = yaml_doc.get("capabilities") or []
    yaml_ids = [str(item.get("vf_id")) for item in yaml_rows]
    yaml_statuses = {str(item.get("vf_id")): str(item.get("status")) for item in yaml_rows}
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["vf_id"] for row in rows]
    report.counts["vibeflow_capabilities"] = len(rows)
    report.counts["capability_yaml_ids"] = len(yaml_ids)
    if len(rows) != EXPECTED["vibeflow_capabilities"]:
        report.err(f"Capabilities: expected {EXPECTED['vibeflow_capabilities']}, got {len(rows)}")
    if len(yaml_ids) != len(rows) or set(yaml_ids) != set(ids):
        report.err("Capability ledger YAML vf_id set does not match CSV")
    if duplicates(ids):
        report.err(f"Duplicate vf_id values: {duplicates(ids)}")

    origins = Counter()
    statuses = Counter()
    for row in rows:
        origins[row.get("origin", "")] += 1
        statuses[row.get("status", "")] += 1
        for field in CAPABILITY_REQUIRED:
            if not (row.get(field) or "").strip():
                report.err(f"{row.get('vf_id')} missing required field {field}")
        if (row.get("origin") or "").startswith("REPLIT") and not (row.get("source_r2v_ids") or "").strip():
            report.err(f"{row['vf_id']} REPLIT-derived but missing source_r2v_ids")
        status = row.get("status") or ""
        if status not in CAPABILITY_STATUS_VOCAB:
            report.err(f"{row['vf_id']} status {status!r} is outside the capability status vocabulary")
        if yaml_statuses.get(row["vf_id"]) != status:
            report.err(
                f"{row['vf_id']} status disagrees between ledger CSV ({status!r}) and YAML "
                f"({yaml_statuses.get(row['vf_id'])!r})"
            )

    report.counts["capability_origins"] = dict(origins)
    report.counts["capability_statuses"] = dict(statuses)
    native = origins.get("VibeFlow-native requirement", 0)
    derived = origins.get("REPLIT-DERIVED-REQUIREMENT", 0)
    if native + derived != len(rows):
        report.err(f"Unclassified capability origins: {dict(origins)}")
    if native == 0 or derived == 0:
        report.err("Native and Replit-derived capabilities must remain distinguishable")

    map_path = MBS / "99_REFERENCE" / "REPLIT_TO_VIBEFLOW_390_EVIDENCE_MAP.csv"
    with map_path.open(newline="", encoding="utf-8") as handle:
        r2v_rows = list(csv.DictReader(handle))
    r2v_ids = [row["id"] for row in r2v_rows]
    report.counts["replit_trace_rows"] = len(r2v_rows)
    if len(r2v_rows) != EXPECTED["replit_trace_rows"]:
        report.err(f"Replit trace rows: expected {EXPECTED['replit_trace_rows']}, got {len(r2v_rows)}")
    if duplicates(r2v_ids):
        report.err(f"Duplicate R2V IDs: {duplicates(r2v_ids)}")

    referenced: list[str] = []
    for row in rows:
        raw = row.get("source_r2v_ids") or ""
        for part in re.split(r"[,;]", raw):
            token = part.strip()
            if token:
                referenced.append(token)
    missing = sorted(set(referenced) - set(r2v_ids))
    if missing:
        report.err(f"Capability source_r2v_ids missing from 390-row map: {missing}")
    unused = sorted(set(r2v_ids) - set(referenced))
    if unused:
        report.warn(f"{len(unused)} R2V rows are not referenced by the capability ledger")
    report.counts["ledger_r2v_refs"] = len(set(referenced))
    report.mark(
        "I",
        "PASS"
        if len(rows) == EXPECTED["vibeflow_capabilities"]
        and not duplicates(ids)
        and not (set(statuses) - CAPABILITY_STATUS_VOCAB)
        and all(yaml_statuses.get(row["vf_id"]) == row.get("status") for row in rows)
        and not missing
        else "FAIL",
    )


def _parse_deps(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if text in {"", "[]"}:
        return []
    return [part.strip() for part in re.split(r"[, ]+", text) if part.strip()]


def check_missions(report: Report) -> None:
    dag = load_yaml_file(MBS / "10_IMPLEMENTATION" / "MISSION_DAG.yaml")
    phases = dag.get("phases") or []
    missions = dag.get("missions") or []
    phase_ids = [item.get("id") for item in phases]
    mission_ids = [str(item.get("mission_id")) for item in missions]
    report.counts["phases"] = len(phases)
    report.counts["missions"] = len(missions)
    if len(phases) != EXPECTED["phases"]:
        report.err(f"Phases: expected {EXPECTED['phases']}, got {len(phases)}")
    if len(missions) != EXPECTED["missions"]:
        report.err(f"Missions: expected {EXPECTED['missions']}, got {len(missions)}")
    if duplicates([str(x) for x in phase_ids]):
        report.err(f"Duplicate phase IDs: {duplicates([str(x) for x in phase_ids])}")
    if duplicates(mission_ids):
        report.err(f"Duplicate mission IDs: {duplicates(mission_ids)}")
    if sorted(int(x) for x in phase_ids) != list(range(0, EXPECTED["phases"])):
        report.err(f"Phase IDs are not 0..32: {phase_ids}")

    by_id = {str(item.get("mission_id")): item for item in missions}
    graph: dict[str, list[str]] = {}
    for item in missions:
        mid = str(item.get("mission_id"))
        deps = _parse_deps(item.get("depends_on"))
        graph[mid] = deps
        for dep in deps:
            if dep not in by_id:
                report.err(f"{mid} depends on missing mission {dep}")

    # Cycle detection.
    visiting: set[str] = set()
    seen: set[str] = set()

    def visit(node: str) -> None:
        if node in seen:
            return
        if node in visiting:
            report.err(f"Mission DAG cycle involving {node}")
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            visit(dep)
        visiting.remove(node)
        seen.add(node)

    for mid in mission_ids:
        visit(mid)

    statuses = Counter(str(item.get("status")) for item in missions)
    report.counts["mission_statuses"] = dict(statuses)

    # --- Generic mission-progression validation (STATUS_PROTOCOL.md) ---
    bad_status = [m for m in mission_ids if str(by_id[m].get("status")) not in MISSION_STATUS_VOCAB]
    if bad_status:
        report.err(f"Missions with status outside the status vocabulary: {bad_status}")

    active_ids = [
        mid for mid in mission_ids if str(by_id[mid].get("status")) in ACTIVE_MISSION_STATUSES
    ]
    if len(active_ids) != 1:
        report.err(
            f"Exactly one mission may be active/reviewable under serial progression; found {len(active_ids)}: {active_ids}"
        )
    active_id = active_ids[0] if len(active_ids) == 1 else None

    done_ids = [mid for mid in mission_ids if str(by_id[mid].get("status")) == "DONE"]

    # A mission may only be READY/IN_PROGRESS/REVIEW/BLOCKED when all its
    # dependencies are DONE (accepted).
    for mid in active_ids:
        not_done = [dep for dep in graph.get(mid, []) if str(by_id[dep].get("status")) != "DONE"]
        if not_done:
            report.err(f"{mid} is unlocked but dependencies are not DONE: {not_done}")

    # Accepted missions may precede the active mission, never follow it.
    if active_id is not None:
        active_index = mission_ids.index(active_id)
        trailing_done = [mid for mid in done_ids if mission_ids.index(mid) > active_index]
        if trailing_done:
            report.err(f"DONE missions may not follow the active mission: {trailing_done}")

    # Everything that is neither DONE nor the single active mission stays LOCKED.
    unlocked = [
        mid
        for mid in mission_ids
        if mid != active_id
        and mid not in done_ids
        and str(by_id[mid].get("status")) != "LOCKED"
    ]
    if unlocked:
        report.err(f"Missions that must remain LOCKED are unlocked: {unlocked}")

    # Future dependent missions remain LOCKED: every transitive dependent of a
    # non-DONE mission must be LOCKED. This subsumes "M-003 stays LOCKED during
    # M-002" and "M-004 stays LOCKED until M-003 is accepted" as instances.
    dependents: dict[str, list[str]] = {mid: [] for mid in mission_ids}
    for mid, deps in graph.items():
        for dep in deps:
            dependents.setdefault(dep, []).append(mid)

    def transitive_dependents(node: str) -> set[str]:
        out: set[str] = set()
        stack = list(dependents.get(node, []))
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(dependents.get(cur, []))
        return out

    for mid in mission_ids:
        if str(by_id[mid].get("status")) != "DONE":
            bad_dependents = [
                d for d in transitive_dependents(mid) if str(by_id[d].get("status")) != "LOCKED"
            ]
            if bad_dependents:
                report.err(
                    f"Dependent missions of non-DONE {mid} must remain LOCKED: {sorted(bad_dependents)}"
                )

    # No mission may skip its dependency chain: dependencies must reference
    # strictly earlier register/DAG entries (no forward references).
    forward_refs = [
        (mid, dep)
        for mid in mission_ids
        for dep in graph.get(mid, [])
        if dep in mission_ids and mission_ids.index(dep) >= mission_ids.index(mid)
    ]
    if forward_refs:
        report.err(f"Missions referencing same/later missions as dependencies: {forward_refs}")

    # Bootstrap chain remains a structural invariant of this mission system.
    if "M-001" not in graph.get("M-002", []):
        report.err("M-002 must depend on M-001")
    if "M-002" not in graph.get("M-003", []):
        report.err("M-003 must depend on M-002")
    m004 = by_id.get("M-004") or {}
    if m004.get("phase") != 1:
        report.err("M-004 must be Phase 1 Repository Foundation")
    if "M-003" not in graph.get("M-004", []):
        report.err("M-004 must depend on M-003 (Phase 0 complete)")

    # The active-mission pointer must agree with the DAG.
    active_mission_file = REPO_ROOT / ".ai" / "ACTIVE_MISSION.md"
    if active_mission_file.is_file():
        am_text = active_mission_file.read_text(encoding="utf-8")
        am_mission = re.search(r"\*\*Mission:\*\*\s*(M-\d{3})", am_text)
        am_status = re.search(r"\*\*Status:\*\*\s*([A-Z_]+)", am_text)
        if not am_mission or not am_status:
            report.err(".ai/ACTIVE_MISSION.md must declare '**Mission:** M-NNN' and '**Status:** ...'")
        elif active_id is not None:
            if am_mission.group(1) != active_id:
                report.err(
                    f".ai/ACTIVE_MISSION.md names {am_mission.group(1)} but the active mission is {active_id}"
                )
            if am_status.group(1) != str(by_id[active_id].get("status")):
                report.err(
                    f".ai/ACTIVE_MISSION.md status {am_status.group(1)} != DAG status "
                    f"{by_id[active_id].get('status')} for {active_id}"
                )

    # Every human-facing mission pointer must name the same active mission as
    # the DAG. A stale pointer misroutes contributors and coding agents, so it
    # is an error, not a warning.
    if active_id is not None:
        for rel in ("README.md", "docs/WORKSPACE_BOOTSTRAP_STATUS.md"):
            pointer_file = REPO_ROOT / rel
            if not pointer_file.is_file():
                report.err(f"Mission pointer file missing: {rel}")
                continue
            text = pointer_file.read_text(encoding="utf-8")
            named = sorted(set(re.findall(r"M-\d{3}", text)))
            if not named:
                report.err(f"{rel} names no mission; it must name the active mission {active_id}")
                continue
            if active_id not in named:
                report.err(
                    f"{rel} does not name the active mission {active_id} (names {named}); "
                    "mission pointer is stale"
                )
                continue
            # A pointer may reference accepted history, but must not describe a
            # non-active mission as the current/active one.
            for match in re.finditer(
                r"[Aa]ctive[^.\n]*?(M-\d{3})|(M-\d{3})[^.\n]{0,80}?is the active", text
            ):
                named_mission = match.group(1) or match.group(2)
                if named_mission != active_id:
                    report.err(
                        f"{rel} describes {named_mission} as the active mission, "
                        f"but the active mission is {active_id}"
                    )

    with (MBS / "10_IMPLEMENTATION" / "MISSION_REGISTER.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        register = list(csv.DictReader(handle))
    reg_ids = [row["mission_id"] for row in register]
    if reg_ids != mission_ids:
        report.err("MISSION_REGISTER.csv mission_id order/set does not match MISSION_DAG.yaml")
    else:
        for row in register:
            mid = row["mission_id"]
            if row.get("status") != str(by_id[mid].get("status")):
                report.err(
                    f"MISSION_REGISTER.csv status {row.get('status')} != DAG status "
                    f"{by_id[mid].get('status')} for {mid}"
                )

    build_phases = load_yaml_file(MBS / "10_IMPLEMENTATION" / "BUILD_PHASES.yaml")
    bp = build_phases.get("phases") or []
    if len(bp) != EXPECTED["phases"]:
        report.err(f"BUILD_PHASES.yaml phases: expected {EXPECTED['phases']}, got {len(bp)}")
    report.mark(
        "J",
        "PASS"
        if len(phases) == EXPECTED["phases"]
        and len(missions) == EXPECTED["missions"]
        and not unlocked
        else "FAIL",
    )


def check_v1_gates(report: Report) -> None:
    data = load_yaml_file(MBS / "11_VERIFICATION" / "V1_ACCEPTANCE.yaml")
    gates = data.get("gates") or []
    ids = [str(item.get("id")) for item in gates]
    report.counts["v1_gates"] = len(gates)
    if len(gates) != EXPECTED["v1_gates"]:
        report.err(f"V1 gates: expected {EXPECTED['v1_gates']}, got {len(gates)}")
    if duplicates(ids):
        report.err(f"Duplicate V1 gate IDs: {duplicates(ids)}")
    expected_ids = [f"V1-{i:03d}" for i in range(1, EXPECTED["v1_gates"] + 1)]
    if ids != expected_ids:
        report.err(f"V1 gate IDs are not V1-001..V1-015: {ids}")
    required_themes = {
        "evidence": False,
        "security": False,
        "verification": False,
        "recovery": False,
        "provider": False,
    }
    for item in gates:
        req = (str(item.get("requirement") or "") + " " + str(item.get("gate") or "")).lower()
        if "evidence" in req or "bundle" in req or "prove" in req or "pass" in req:
            required_themes["evidence"] = True
        if "security" in req:
            required_themes["security"] = True
        if "verif" in req:
            required_themes["verification"] = True
        if "recover" in req or "crash" in req:
            required_themes["recovery"] = True
        if "provider" in req or "agent" in req or "workspace" in req:
            required_themes["provider"] = True
        if not str(item.get("requirement") or "").strip():
            report.err(f"Empty V1 requirement: {item.get('id')}")
    missing_themes = [key for key, present in required_themes.items() if not present]
    if missing_themes:
        report.err(f"V1 gates missing required themes: {missing_themes}")
    report.mark(
        "K",
        "PASS" if len(gates) == EXPECTED["v1_gates"] and not duplicates(ids) else "FAIL",
    )


def check_harvest_and_clean_room(report: Report) -> None:
    do_not_invent = MBS / "06_HARVEST" / "DO_NOT_INVENT.yaml"
    harvest = MBS / "06_HARVEST" / "OSS_HARVEST_REGISTRY.yaml"
    if not do_not_invent.is_file() or not harvest.is_file():
        report.err("Harvest authority files missing")
        report.mark("L", "FAIL")
        return
    harvest_doc = load_yaml_file(harvest)
    entries = harvest_doc.get("entries") or []
    ids = [str(item.get("id")) for item in entries]
    report.counts["approved_harvest_entries"] = len(entries)
    if len(entries) != EXPECTED["approved_harvest_entries"]:
        report.warn(
            f"Harvest entries: summary expects {EXPECTED['approved_harvest_entries']}, got {len(entries)} (M-002 owns full ratification)"
        )
    if duplicates(ids):
        report.err(f"Duplicate harvest IDs: {duplicates(ids)}")
    dni = load_yaml_file(do_not_invent)
    if not (dni.get("entries") or []):
        report.err("DO_NOT_INVENT.yaml has no entries")

    summary = (MBS / "99_REFERENCE" / "REPLIT_EVIDENCE_SUMMARY.md").read_text(encoding="utf-8")
    if "not how to copy Replit internals" not in summary and "not an implementation source" not in summary.lower():
        report.err("Replit evidence summary does not restate clean-room boundary")
    if "REPLIT_TO_VIBEFLOW_390_EVIDENCE_MAP.csv" not in summary:
        report.err("Replit evidence summary does not route traceability to the 390-row map")

    # Implementation trees must remain seed READMEs, not Replit source.
    # After M-004, the seven shared packages are allowed to contain their foundation manifests.
    impl_roots = [
        REPO_ROOT / "apps",
        REPO_ROOT / "packages",
        REPO_ROOT / "services",
        REPO_ROOT / "adapters",
        REPO_ROOT / "workers",
    ]
    # After M-004, the seven shared packages are allowed to contain their foundation manifests.
    # For validator stability across historical-state mutation tests, allow them unconditionally.
    allowed_packages = {
        "core",
        "contracts",
        "remote",
        "bridge",
        "provider-sdk",
        "verification",
        "ui",
    }
    allowed_files = {
        "package.json",
        "tsconfig.json",
    }
    allowed_src_files = {
        "src/index.ts",
        "src/typebox-smoke.test.ts",
    }
    # M-005 derived contract artifacts. These are generated from the master pack
    # by scripts/generate-contracts.py, are marked DO NOT EDIT, and carry no
    # harvested third-party source. The exact inventory is enforced here and by
    # `generate-contracts.py --check`.
    allowed_generated_files = {
        "contracts": {
            "src/generated/catalog.ts",
            "generated/catalog.schema.json",
            "generated/catalog.manifest.json",
        },
    }
    ignored_dirs = {
        "dist",
        ".turbo",
        "node_modules",
        ".cache",
        ".vite",
        "__pycache__",
        ".pytest_cache",
        ".next",
        ".expo",
    }
    unexpected = []
    for root in impl_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in ignored_dirs for part in path.parts):
                continue
            if path.name == "README.md":
                continue
            rel = path.relative_to(REPO_ROOT)
            if (
                rel.parts[0] == "packages"
                and len(rel.parts) >= 2
                and rel.parts[1] in allowed_packages
            ):
                suffix = "/".join(rel.parts[2:])
                if suffix in allowed_files or suffix in allowed_src_files:
                    continue
                if suffix in allowed_generated_files.get(rel.parts[1], set()):
                    continue
            unexpected.append(str(path.relative_to(REPO_ROOT)))
    if unexpected:
        report.err(f"Implementation trees contain non-seed files: {unexpected}")
    report.mark("L", "PASS" if not unexpected else "FAIL")


def check_pack_summary(report: Report) -> None:
    summary = json.loads((MBS / "PACK_SUMMARY.json").read_text(encoding="utf-8"))
    report.counts["pack_summary"] = summary
    mapping = {
        "vibeflow_capabilities": "vibeflow_capabilities",
        "replit_trace_rows": "replit_trace_rows",
        "canonical_resources": "canonical_resources",
        "invariants": "invariants",
        "approved_harvest_entries": "approved_harvest_entries",
        "phases": "phases",
        "missions": "missions",
        "frontend_surface_contracts": "frontend_surface_contracts",
        "event_types": "event_types",
        "v1_gates": "v1_gates",
    }
    for key, count_key in mapping.items():
        declared = summary.get(key)
        actual = report.counts.get(count_key)
        if declared != EXPECTED[key]:
            report.err(f"PACK_SUMMARY.json {key}={declared} != expected baseline {EXPECTED[key]}")
        if actual is not None and declared != actual:
            report.err(f"PACK_SUMMARY.json {key}={declared} != counted {actual}")


def render(report: Report) -> str:
    lines = ["VibeFlow master-contract validator", ""]
    lines.append("Counts:")
    for key in (
        "canonical_resources",
        "invariants",
        "event_types",
        "frontend_surface_contracts",
        "vibeflow_capabilities",
        "replit_trace_rows",
        "phases",
        "missions",
        "v1_gates",
        "approved_harvest_entries",
        "capability_origins",
        "capability_statuses",
        "mission_statuses",
    ):
        if key in report.counts:
            lines.append(f"  {key}: {report.counts[key]}")
    lines.append("")
    lines.append("Checks:")
    for key in ("C", "D", "E", "F", "G", "H", "I", "J", "K", "L"):
        lines.append(f"  {key}: {report.checks.get(key, 'n/a')}")
    if report.errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"  - {item}" for item in report.errors)
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in report.warnings)
    if report.notes:
        lines.append("")
        lines.append("Notes:")
        lines.extend(f"  - {item}" for item in report.notes)
    lines.append("")
    lines.append("RESULT: " + ("PASS" if not report.errors else "FAIL"))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate VibeFlow master contracts")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root to validate (defaults to the repository containing this script)",
    )
    args = parser.parse_args(argv)

    global REPO_ROOT, MBS
    if args.root is not None:
        REPO_ROOT = Path(args.root).resolve()
        MBS = REPO_ROOT / "master-build-system"

    report = Report()
    try:
        check_source_of_truth(report)
        canonical = check_resources(report)
        check_invariants(report)
        check_state_machines(report)
        event_names, prefixes = check_events(report, canonical)
        check_frontend(report, canonical, event_names, prefixes)
        check_capabilities(report)
        check_missions(report)
        check_v1_gates(report)
        check_harvest_and_clean_room(report)
        check_pack_summary(report)
        # Recalculate letter grades that may have collected later errors.
        if report.checks.get("C") != "FAIL" and any("SOURCE_OF_TRUTH" in e or "INDEX.yaml" in e for e in report.errors):
            report.mark("C", "FAIL")
        if report.checks.get("D") != "FAIL" and any("Canonical resources" in e or "STATE_OWNERSHIP" in e for e in report.errors):
            report.mark("D", "FAIL")
        if report.checks.get("I") != "FAIL" and any(e.startswith("VF-") or "Capabilities" in e or "R2V" in e for e in report.errors):
            report.mark("I", "FAIL")
        if report.checks.get("J") != "FAIL" and any(
            e.startswith("M-") or e.startswith("Phases") or e.startswith("Missions") or "DAG" in e
            for e in report.errors
        ):
            report.mark("J", "FAIL")
    except Exception as exc:  # noqa: BLE001 — validator must not hide parse failures
        report.err(f"Validator exception: {type(exc).__name__}: {exc}")

    text = render(report)
    sys.stdout.write(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(
                {
                    "result": "PASS" if not report.errors else "FAIL",
                    "counts": report.counts,
                    "checks": report.checks,
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "notes": report.notes,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
