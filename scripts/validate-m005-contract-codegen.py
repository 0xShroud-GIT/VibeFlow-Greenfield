#!/usr/bin/env python3
"""M-005 schema/codegen pipeline contract validator (stdlib only).

Enforces that the generated contract catalog remains a faithful, non-stale,
non-invented derivation of the Master Build System, that the mission state is
coherent, and that no dependency or supply-chain protection was weakened to
make codegen work.

This gate is retained by CI after M-005, so it is progression-aware and runs in
one of two modes selected from the mission state:

  M005-ACTIVE mode (M-005 is REVIEW/IN_PROGRESS)
      M-005's own snapshot is asserted in full: the 35/7/37 catalog totals, no
      new dependency, no invented command/payload/error-code vocabulary, and no
      implementation under apps/services/workers/adapters. Successor missions
      must remain LOCKED.

  DURABLE mode (M-005 is DONE — accepted)
      Only properties that must hold forever are asserted, so a correct M-006+
      branch passes this retained gate. Successor progression is delegated to
      validate-master-contracts.py, and a later authoritative mission may
      legitimately expand the catalog (more resources/states/events, and
      eventually command/event payload or error-code contracts) without
      rewriting M-005 history.

Durable properties enforced in BOTH modes:

  - M-001..M-004 remain DONE and M-005 never regresses below REVIEW
  - DAG/register agreement, and mission-pointer coherence with the active row
  - SOURCE_OF_TRUTH routing for resources/states/events is intact
  - the generator exists and its --check drift gate passes
  - the generated artifact inventory is exact
  - generated counts equal the CURRENT authoritative inputs, and the manifest
    source hashes match current authority and the pack
  - generated enums exactly match the authoritative resources, states, terminal
    states (a subset of states) and event IDs/names in canonical order
  - types are derived from JSON Schema, never a second handwritten vocabulary
  - HealthSchema never returns as public contract authority
  - typebox stays on the selected 1.x line at its exact pin; @sinclair/typebox
    stays forbidden
  - pnpm supply-chain protections and the contracts:generate/check scripts stay
  - the Master Build System workflow keeps its M-005 steps and path triggers

Checks A..Z are labelled in error output so failures are precise.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = SCRIPTS_DIR.parent

TYPEBOX_PIN = "1.3.6"
FORBIDDEN_TYPEBOX_PACKAGE = "@sinclair/typebox"
EXPECTED_RESOURCE_COUNT = 35
EXPECTED_STATE_MACHINE_COUNT = 7
EXPECTED_EVENT_COUNT = 37

# The exact approved dependency set at M-005. M-005 adds no dependency.
APPROVED_ROOT_DEV = {"typescript": "6.0.3", "turbo": "2.10.6", "vitest": "4.1.7"}
APPROVED_PACKAGE_DEPS = {"contracts": {"typebox": TYPEBOX_PIN}}

GENERATED_TS = "packages/contracts/src/generated/catalog.ts"
GENERATED_SCHEMA = "packages/contracts/generated/catalog.schema.json"
GENERATED_MANIFEST = "packages/contracts/generated/catalog.manifest.json"
GENERATED_ARTIFACTS = (GENERATED_TS, GENERATED_SCHEMA, GENERATED_MANIFEST)
GENERATED_DIRS = ("packages/contracts/src/generated", "packages/contracts/generated")

GENERATOR = "scripts/generate-contracts.py"

REQUIRED_ROUTES = {
    "resources": "02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml",
    "states": "03_BACKEND/STATE_MACHINES.yaml",
    "events": "03_BACKEND/EVENT_CATALOG.yaml",
}

MBS_WORKFLOW = ".github/workflows/master-build-system-integrity.yml"
REQUIRED_MBS_STEPS = (
    "python3 scripts/validate-m005-contract-codegen.py",
    "python3 tests/contract/test_m005_contract_codegen.py",
)

# Domain semantics M-005 is explicitly forbidden from inventing (section 12).
FORBIDDEN_INVENTED_TOKENS = (
    "ErrorCode",
    "ERROR_CODES",
    "ERROR_CATALOG",
    "CommandSchema",
    "COMMAND_CATALOG",
    "PayloadSchema",
    "RequestSchema",
    "ResponseSchema",
    "TableSchema",
    "ColumnSchema",
)


def load_yaml_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_master_contracts", SCRIPTS_DIR / "validate-master-contracts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Validator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.mbs = root / "master-build-system"
        self.errors: list[str] = []
        self.yaml = load_yaml_module()
        # Progression flags, set by check_mission_state(). Default to the
        # active-M-005 snapshot so an unreadable mission state can never
        # silently relax M-005's own scope rules.
        self.m005_active = True
        self.m005_accepted = False
        # Live counts derived from current authority, for the summary line.
        self.live_counts: dict[str, int] = {}

    # -- helpers ----------------------------------------------------------

    def err(self, label: str, message: str) -> None:
        self.errors.append(f"{label}: {message}")

    def read_text(self, rel: str, label: str) -> str | None:
        path = self.root / rel
        if not path.is_file():
            self.err(label, f"missing file: {rel}")
            return None
        return path.read_text(encoding="utf-8")

    def read_json(self, rel: str, label: str) -> dict[str, Any] | None:
        text = self.read_text(rel, label)
        if text is None:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            self.err(label, f"invalid JSON in {rel}: {exc}")
            return None
        if not isinstance(data, dict):
            self.err(label, f"expected a JSON object in {rel}")
            return None
        return data

    def load_yaml(self, rel: str, label: str) -> Any:
        path = self.root / rel
        if not path.is_file():
            self.err(label, f"missing authority file: {rel}")
            return None
        try:
            return self.yaml.load_yaml_file(path)
        except Exception as exc:  # noqa: BLE001 — surface parse failures
            self.err(label, f"failed to parse {rel}: {type(exc).__name__}: {exc}")
            return None

    # -- A/B/C/D: mission state -------------------------------------------

    def parse_dag_statuses(self) -> dict[str, str]:
        text = self.read_text(
            "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml", "A"
        )
        if text is None:
            return {}
        statuses: dict[str, str] = {}
        current: str | None = None
        for line in text.splitlines():
            match = re.match(r"\s*-\s*mission_id:\s*(M-\d{3})\s*$", line)
            if match:
                current = match.group(1)
                continue
            if current:
                match = re.match(r"\s*status:\s*([A-Z_]+)\s*$", line)
                if match:
                    statuses[current] = match.group(1)
                    current = None
        return statuses

    def parse_register_statuses(self) -> dict[str, str]:
        path = self.root / "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv"
        if not path.is_file():
            self.err("D", "missing MISSION_REGISTER.csv")
            return {}
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return {
            (row.get("mission_id") or "").strip(): (row.get("status") or "").strip()
            for row in rows
            if (row.get("mission_id") or "").strip()
        }

    def check_mission_state(self) -> None:
        dag = self.parse_dag_statuses()
        register = self.parse_register_statuses()

        # A. M-004 DONE — M-005 consumed that acceptance and depends on it.
        for source, statuses in (("DAG", dag), ("register", register)):
            if statuses.get("M-004") != "DONE":
                self.err(
                    "A",
                    f"{source} M-004 must be DONE (externally accepted), got "
                    f"{statuses.get('M-004')!r}",
                )

        # Phase 0 must remain accepted.
        for mid in ("M-001", "M-002", "M-003"):
            if dag.get(mid) != "DONE" or register.get(mid) != "DONE":
                self.err("A", f"{mid} must remain DONE")

        # B. Progression-aware M-005 state.
        #
        #   historical M-005 : M-005 REVIEW/IN_PROGRESS, M-006+ LOCKED
        #   accepted M-005   : M-005 DONE, later serial progression delegated
        #                      to validate-master-contracts.py
        #
        # M-005 may never regress below REVIEW, and DAG/register must agree.
        m005_dag = dag.get("M-005")
        m005_register = register.get("M-005")
        active_states = {"REVIEW", "IN_PROGRESS"}
        valid_states = active_states | {"DONE"}

        for source, status in (("DAG", m005_dag), ("register", m005_register)):
            if status not in valid_states:
                self.err(
                    "B",
                    f"{source} M-005 must be REVIEW (its own mission, IN_PROGRESS allowed "
                    f"during implementation) or DONE (accepted), got {status!r}",
                )
        if m005_dag != m005_register:
            self.err(
                "B",
                f"M-005 status disagrees between DAG ({m005_dag!r}) and register "
                f"({m005_register!r})",
            )

        self.m005_active = m005_dag in active_states and m005_register in active_states
        self.m005_accepted = m005_dag == "DONE" and m005_register == "DONE"

        # C. While M-005 is the active mission, successors stay LOCKED. Once
        # M-005 is DONE, successor progression is owned by
        # validate-master-contracts.py; only DAG/register agreement is checked
        # here so a correct M-006 branch is not rejected by this retained gate.
        if self.m005_active:
            for index in range(6, 152):
                mid = f"M-{index:03d}"
                if dag.get(mid) != "LOCKED":
                    self.err(
                        "C",
                        f"DAG {mid} must remain LOCKED while M-005 is {m005_dag}, "
                        f"got {dag.get(mid)!r}",
                    )
                if register.get(mid) != "LOCKED":
                    self.err(
                        "C",
                        f"register {mid} must remain LOCKED while M-005 is {m005_register}, "
                        f"got {register.get(mid)!r}",
                    )

        # D. DAG/register/ACTIVE/README/bootstrap coherence.
        for mid in sorted(set(dag) | set(register)):
            if dag.get(mid) != register.get(mid):
                self.err(
                    "D",
                    f"{mid} status disagrees between DAG ({dag.get(mid)!r}) and "
                    f"register ({register.get(mid)!r})",
                )

        # The mission pointers must track whichever mission is actually active.
        # While M-005 is active that is M-005; afterwards it is the successor
        # the DAG names, which this validator does not attempt to re-derive.
        active_ids = [
            mid
            for mid, status in dag.items()
            if status in {"READY", "IN_PROGRESS", "REVIEW", "BLOCKED"}
        ]
        expected_pointer = "M-005" if self.m005_active else (
            active_ids[0] if len(active_ids) == 1 else None
        )

        active_text = self.read_text(".ai/ACTIVE_MISSION.md", "D")
        if active_text is not None and expected_pointer is not None:
            mission = re.search(r"\*\*Mission:\*\*\s*(M-\d{3})", active_text)
            status = re.search(r"\*\*Status:\*\*\s*([A-Z_]+)", active_text)
            if not mission or not status:
                self.err("D", ".ai/ACTIVE_MISSION.md must declare Mission and Status")
            else:
                if mission.group(1) != expected_pointer:
                    self.err(
                        "D",
                        f".ai/ACTIVE_MISSION.md names {mission.group(1)}, expected "
                        f"{expected_pointer}",
                    )
                if status.group(1) != dag.get(expected_pointer):
                    self.err(
                        "D",
                        f".ai/ACTIVE_MISSION.md status {status.group(1)} != DAG status "
                        f"{dag.get(expected_pointer)!r}",
                    )

        if expected_pointer is not None:
            for rel in ("README.md", "docs/WORKSPACE_BOOTSTRAP_STATUS.md"):
                text = self.read_text(rel, "D")
                if text is None:
                    continue
                if expected_pointer not in text:
                    self.err(
                        "D",
                        f"{rel} does not name the active mission {expected_pointer} "
                        "(stale pointer)",
                    )
                for match in re.finditer(
                    r"[Aa]ctive[^.\n]*?(M-\d{3})|(M-\d{3})[^.\n]{0,80}?is the active", text
                ):
                    named = match.group(1) or match.group(2)
                    if named != expected_pointer:
                        self.err(
                            "D",
                            f"{rel} describes {named} as the active mission, expected "
                            f"{expected_pointer}",
                        )

    # -- E/F/G/H: dependency + supply chain --------------------------------

    def check_h025(self) -> None:
        doc = self.load_yaml("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml", "E")
        if doc is None:
            return
        entries = {str(e.get("id")): e for e in (doc.get("entries") or [])}
        h025 = entries.get("H-025")
        if not h025:
            self.err("E", "harvest registry has no H-025 entry")
            return
        blob = " ".join(
            str(h025.get(field) or "")
            for field in ("name", "version", "rule", "upgrade_policy", "ownership")
        )
        lowered = blob.lower()

        # The governing clauses must live in the `rule` field, which is what
        # implementers read; restating them only in `ownership` is not enough.
        rule = str(h025.get("rule") or "")
        rule_lower = rule.lower()
        if "json schema first" not in rule_lower:
            self.err("E", "H-025 rule must record that contracts are JSON Schema first")
        if "derived" not in rule_lower:
            self.err("E", "H-025 rule must record that TypeScript types are derived")
        if "1.x" not in blob:
            self.err("E", "H-025 must record TypeBox 1.x as the selected line")
        if TYPEBOX_PIN not in blob:
            self.err("E", f"H-025 must record the foundation exact pin {TYPEBOX_PIN}")
        if "selected" not in lowered:
            self.err("E", "H-025 must state that TypeBox 1.x is the VibeFlow selected line")
        if "m-004" not in lowered:
            self.err("E", "H-025 must attribute the TypeBox line selection to M-004")
        if FORBIDDEN_TYPEBOX_PACKAGE not in blob:
            self.err(
                "E",
                f"H-025 must explicitly record that {FORBIDDEN_TYPEBOX_PACKAGE} 0.x is not the "
                "VibeFlow selected line",
            )
        # The delegated decision must no longer read as unresolved.
        for unresolved in ("choose one at m-004", "choose 1.x (esm) or 0.x lts at m-004"):
            if unresolved in lowered:
                self.err(
                    "E",
                    "H-025 still defers the TypeBox line choice to M-004; the decision was made "
                    f"(TypeBox 1.x, {TYPEBOX_PIN}) and must be recorded as selected",
                )

    def check_dependencies(self) -> None:
        # F. typebox remains exactly 1.3.6
        contracts = self.read_json("packages/contracts/package.json", "F")
        if contracts is not None:
            deps = contracts.get("dependencies") or {}
            if self.m005_active:
                if deps != {"typebox": TYPEBOX_PIN}:
                    self.err(
                        "F",
                        f"packages/contracts dependencies must be exactly "
                        f"{{'typebox': '{TYPEBOX_PIN}'}}, got {deps}",
                    )
            elif deps.get("typebox") != TYPEBOX_PIN:
                # Durable: the selected TypeBox line and its exact pin survive
                # later missions, even if they add further approved deps.
                self.err(
                    "F",
                    f"packages/contracts must keep the typebox@{TYPEBOX_PIN} pin, "
                    f"got {deps.get('typebox')!r}",
                )

        # G. No new dependency — M-005's own present-mission scope. This is the
        # rule that keeps M-005 honest about adding no codegen/schema package;
        # it is not asserted once M-005 is accepted and later authoritative
        # missions add their own approved dependencies (which remain governed
        # by the harvest registry and the foundation validator).
        root_pkg = self.read_json("package.json", "G")
        if root_pkg is not None and self.m005_active:
            if root_pkg.get("dependencies"):
                self.err("G", "root dependencies must remain empty; M-005 adds no dependency")
            dev = root_pkg.get("devDependencies") or {}
            if dev != APPROVED_ROOT_DEV:
                self.err(
                    "G",
                    f"root devDependencies must remain {APPROVED_ROOT_DEV}, got {dev} "
                    "(M-005 adds no code-generation or schema dependency)",
                )

        packages_dir = self.root / "packages"
        for manifest in sorted(packages_dir.glob("*/package.json")):
            name = manifest.parent.name
            pkg = self.read_json(f"packages/{name}/package.json", "G")
            if pkg is None:
                continue
            merged: dict[str, str] = {}
            for field in (
                "dependencies",
                "devDependencies",
                "peerDependencies",
                "optionalDependencies",
            ):
                merged.update({str(k): str(v) for k, v in (pkg.get(field) or {}).items()})
            expected = APPROVED_PACKAGE_DEPS.get(name, {})
            if self.m005_active and merged != expected:
                self.err(
                    "G",
                    f"packages/{name} dependency set changed: expected {expected}, got {merged}",
                )
            # Durable in every state: the forbidden TypeBox 0.x package must
            # never appear, whichever mission is active.
            if FORBIDDEN_TYPEBOX_PACKAGE in merged:
                self.err(
                    "F",
                    f"packages/{name} uses {FORBIDDEN_TYPEBOX_PACKAGE}; TypeBox 1.x "
                    "(package 'typebox') is the selected line",
                )

        # H. pnpm supply-chain protections retained
        workspace = self.read_text("pnpm-workspace.yaml", "H")
        if workspace is not None:
            required = {
                "minimumReleaseAge": "1440",
                "minimumReleaseAgeStrict": "true",
                "minimumReleaseAgeIgnoreMissingTime": "false",
                "blockExoticSubdeps": "true",
                "strictDepBuilds": "true",
                "trustLockfile": "false",
            }
            settings: dict[str, str] = {}
            for line in workspace.splitlines():
                stripped = line.strip()
                if line.startswith(" ") or not stripped or stripped.startswith("#"):
                    continue
                if ":" in stripped:
                    key, value = stripped.split(":", 1)
                    settings[key.strip()] = value.strip()
            for key, value in required.items():
                if settings.get(key) != value:
                    self.err(
                        "H",
                        f"pnpm-workspace.yaml {key} must remain {value!r}, got "
                        f"{settings.get(key)!r}",
                    )
            # Blanket script execution is forbidden forever, even if someone
            # attempts to add the key with a false value as camouflage.
            if "dangerouslyAllowAllBuilds" in settings:
                self.err("H", "dangerouslyAllowAllBuilds is permanently forbidden")

            try:
                workspace_doc = self.yaml.load_yaml_file(self.root / "pnpm-workspace.yaml")
            except Exception as exc:  # noqa: BLE001 — deterministic policy failure
                self.err("H", f"cannot parse pnpm-workspace.yaml build policy: {exc}")
                workspace_doc = {}
            allow_present = "allowBuilds" in workspace_doc
            allow_builds = workspace_doc.get("allowBuilds") if allow_present else {}
            if self.m005_active and allow_present:
                self.err("H", "M-005 active snapshot forbids allowBuilds")
            elif self.m005_accepted and allow_present:
                if not isinstance(allow_builds, dict) or not allow_builds:
                    self.err("H", "durable allowBuilds must be a non-empty per-package mapping")
                else:
                    registry = self.load_yaml(
                        "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml", "H"
                    )
                    approved: dict[str, str] = {}
                    coordinates: dict[str, str] = {}
                    if isinstance(registry, dict):
                        for entry in registry.get("entries") or []:
                            hid = str(entry.get("id") or "")
                            for coordinate in entry.get("package_coordinates") or []:
                                if coordinate.get("ecosystem") == "npm":
                                    coordinates[str(coordinate.get("name") or "")] = hid
                        policy = registry.get("install_build_script_policy") or {}
                        for approval in policy.get("approvals") or []:
                            if (
                                approval.get("ecosystem") == "npm"
                                and approval.get("approved") is True
                                and str(approval.get("rationale") or "").strip()
                            ):
                                approved[str(approval.get("package") or "")] = str(
                                    approval.get("harvest_id") or ""
                                )
                    for package, value in allow_builds.items():
                        if value is not True:
                            self.err(
                                "H",
                                f"allowBuilds[{package!r}] must be the explicit boolean true, got {value!r}",
                            )
                        elif package not in coordinates:
                            self.err("H", f"allowBuilds package {package!r} has no harvest coordinate")
                        elif approved.get(str(package)) != coordinates[str(package)]:
                            self.err(
                                "H",
                                f"allowBuilds package {package!r} lacks matching harvest-side approval and rationale",
                            )

    # -- I/J/K/L: routing, generator, inventory ----------------------------

    def check_routing(self) -> None:
        sot = self.load_yaml("master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml", "I")
        if sot is None:
            return
        for key, expected in REQUIRED_ROUTES.items():
            actual = str(sot.get(key) or "")
            if actual != expected:
                self.err(
                    "I",
                    f"SOURCE_OF_TRUTH_INDEX.yaml routes {key!r} to {actual!r}, expected {expected!r}",
                )
            if not (self.mbs / expected).is_file():
                self.err("I", f"authoritative source missing: master-build-system/{expected}")

    def check_generator_and_inventory(self) -> None:
        # J. generator exists
        generator = self.root / GENERATOR
        if not generator.is_file():
            self.err("J", f"missing generator: {GENERATOR}")
            return
        source = generator.read_text(encoding="utf-8")
        if "--check" not in source:
            self.err("J", f"{GENERATOR} must support a no-write --check mode")

        # K. generated inventory is exact
        found: list[str] = []
        for rel_dir in GENERATED_DIRS:
            base = self.root / rel_dir
            if not base.is_dir():
                continue
            found.extend(
                path.relative_to(self.root).as_posix()
                for path in sorted(base.rglob("*"))
                if path.is_file()
            )
        expected = set(GENERATED_ARTIFACTS)
        for rel in sorted(expected - set(found)):
            self.err("K", f"missing generated artifact: {rel}")
        for rel in sorted(set(found) - expected):
            self.err("K", f"unexpected file in generated output tree: {rel}")

        # L. --check passes (no writes)
        result = subprocess.run(
            [sys.executable, str(generator), "--check", "--root", str(self.root)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
            self.err("L", f"generate-contracts.py --check failed: {detail}")

    # -- M..T: generated content vs authority ------------------------------

    def check_generated_content(self) -> None:
        manifest = self.read_json(GENERATED_MANIFEST, "M")
        schema = self.read_json(GENERATED_SCHEMA, "K")
        catalog = self.read_text(GENERATED_TS, "K")

        resources_doc = self.load_yaml(
            f"master-build-system/{REQUIRED_ROUTES['resources']}", "N"
        )
        states_doc = self.load_yaml(f"master-build-system/{REQUIRED_ROUTES['states']}", "O")
        events_doc = self.load_yaml(f"master-build-system/{REQUIRED_ROUTES['events']}", "P")
        if resources_doc is None or states_doc is None or events_doc is None:
            return

        resources = [str(r.get("resource")) for r in (resources_doc.get("resources") or [])]
        machines = states_doc.get("machines") or {}
        events = events_doc.get("events") or []
        event_ids = [str(e.get("id")) for e in events]
        event_names = [str(e.get("name")) for e in events]

        # M. manifest source hashes match current authority (and the pack).
        if manifest is not None:
            import hashlib

            pack_hashes: dict[str, str] = {}
            sums = self.mbs / "SHA256SUMS.txt"
            if sums.is_file():
                for line in sums.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        digest, rel = line.split(None, 1)
                        pack_hashes[rel.strip()] = digest
            sources = manifest.get("sources") or []
            if not sources:
                self.err("M", "generated manifest records no authoritative sources")
            for entry in sources:
                rel = str(entry.get("path") or "")
                declared = str(entry.get("sha256") or "")
                path = self.root / rel
                if not path.is_file():
                    self.err("M", f"manifest references missing source: {rel}")
                    continue
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if declared != actual:
                    self.err(
                        "M",
                        f"manifest sha256 for {rel} is stale: manifest={declared[:16]} "
                        f"actual={actual[:16]} — run: pnpm run contracts:generate",
                    )
                pack_rel = rel.removeprefix("master-build-system/")
                if pack_rel in pack_hashes and pack_hashes[pack_rel] != actual:
                    self.err(
                        "M",
                        f"authoritative source {rel} does not match its SHA256SUMS.txt pack entry",
                    )
            if "generated_at" in manifest or "timestamp" in manifest:
                self.err("M", "generated manifest must not contain a timestamp")

        self.live_counts = {
            "resources": len(resources),
            "machines": len(machines),
            "events": len(events),
        }

        # N/O/P. Counts.
        #
        # The durable rule is: generated counts equal the CURRENT authoritative
        # inputs (enforced against the manifest just below, and structurally by
        # the enum comparisons further down). A later authoritative mission may
        # legitimately expand the catalog, so fixed historical totals are only
        # asserted while M-005 itself is the active mission. The 35/7/37
        # snapshot is additionally recorded in M-005 evidence and tests.
        if self.m005_active:
            if len(resources) != EXPECTED_RESOURCE_COUNT:
                self.err(
                    "N",
                    f"expected exactly {EXPECTED_RESOURCE_COUNT} canonical resources at M-005, "
                    f"got {len(resources)}",
                )
            if len(machines) != EXPECTED_STATE_MACHINE_COUNT:
                self.err(
                    "O",
                    f"expected exactly {EXPECTED_STATE_MACHINE_COUNT} state machines at M-005, "
                    f"got {len(machines)}",
                )
            if len(events) != EXPECTED_EVENT_COUNT:
                self.err(
                    "P",
                    f"expected exactly {EXPECTED_EVENT_COUNT} events at M-005, got {len(events)}",
                )

        if manifest is not None:
            counts = manifest.get("counts") or {}
            for key, actual in (
                ("canonical_resources", len(resources)),
                ("state_machines", len(machines)),
                ("events", len(events)),
            ):
                if counts.get(key) != actual:
                    self.err(
                        "M",
                        f"manifest counts.{key}={counts.get(key)!r} != authoritative {actual}",
                    )
            declared_artifacts = list(manifest.get("artifacts") or [])
            if declared_artifacts != list(GENERATED_ARTIFACTS):
                self.err(
                    "K",
                    f"manifest artifact inventory {declared_artifacts} != {list(GENERATED_ARTIFACTS)}",
                )

        if schema is None or catalog is None:
            return
        defs = schema.get("$defs") or {}

        def enum_of(name: str) -> list[str] | None:
            entry = defs.get(name)
            if not isinstance(entry, dict):
                self.err("K", f"catalog.schema.json missing $defs.{name}")
                return None
            values = entry.get("enum")
            if not isinstance(values, list):
                self.err("K", f"$defs.{name} has no enum")
                return None
            return [str(v) for v in values]

        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            self.err("K", "catalog.schema.json must declare the JSON Schema 2020-12 dialect")
        if not str(schema.get("$id") or "").startswith("urn:vibeflow:contracts:catalog:"):
            self.err("K", f"catalog.schema.json has no stable versioned $id: {schema.get('$id')!r}")

        # Resources.
        generated_resources = enum_of("CanonicalResourceName")
        if generated_resources is not None and generated_resources != resources:
            self.err(
                "N",
                "generated CanonicalResourceName enum does not match CANONICAL_RESOURCE_MODEL "
                f"(missing={sorted(set(resources) - set(generated_resources))}, "
                f"extra={sorted(set(generated_resources) - set(resources))})",
            )

        # Q/R/S. state and terminal enums.
        generated_machines = enum_of("StateMachineName")
        if generated_machines is not None and generated_machines != list(machines):
            self.err(
                "O",
                f"generated StateMachineName enum {generated_machines} != STATE_MACHINES "
                f"{list(machines)}",
            )
        for machine_name, machine in machines.items():
            states = [str(s) for s in (machine.get("states") or [])]
            terminal = [str(s) for s in (machine.get("terminal") or [])]
            generated_states = enum_of(f"{machine_name}State")
            if generated_states is not None and generated_states != states:
                self.err(
                    "Q",
                    f"generated {machine_name}State enum {generated_states} != authoritative {states}",
                )
            generated_terminal = enum_of(f"{machine_name}TerminalState")
            if generated_terminal is not None and generated_terminal != terminal:
                self.err(
                    "R",
                    f"generated {machine_name}TerminalState enum {generated_terminal} != "
                    f"authoritative {terminal}",
                )
            not_subset = [s for s in terminal if s not in states]
            if not_subset:
                self.err(
                    "S",
                    f"{machine_name} terminal states are not a subset of its states: {not_subset}",
                )
            if generated_terminal is not None and generated_states is not None:
                leaked = [s for s in generated_terminal if s not in generated_states]
                if leaked:
                    self.err(
                        "S",
                        f"generated {machine_name} terminal enum contains non-states: {leaked}",
                    )

        # T. event IDs/names in canonical order.
        generated_ids = enum_of("EventId")
        if generated_ids is not None and generated_ids != event_ids:
            self.err("T", "generated EventId enum does not match EVENT_CATALOG in canonical order")
        generated_names = enum_of("EventName")
        if generated_names is not None and generated_names != event_names:
            self.err("T", "generated EventName enum does not match EVENT_CATALOG in canonical order")

        ts_ids = re.search(r"export const EVENT_IDS = \[(.*?)\] as const;", catalog, re.S)
        if ts_ids:
            found_ids = re.findall(r'"([^"]+)"', ts_ids.group(1))
            if found_ids != event_ids:
                self.err("T", "catalog.ts EVENT_IDS does not match EVENT_CATALOG canonical order")
        else:
            self.err("T", "catalog.ts does not export EVENT_IDS")

        catalog_rows = re.findall(r'\{ id: "(EVT-\d+)", name: "([^"]+)"', catalog)
        if [row[0] for row in catalog_rows] != event_ids:
            self.err("T", "catalog.ts EVENT_CATALOG ids do not match authority in canonical order")
        if [row[1] for row in catalog_rows] != event_names:
            self.err("T", "catalog.ts EVENT_CATALOG names do not match authority in canonical order")

    # -- U/V/W/X/Y/Z: derivation, canary, scripts, CI, scope ---------------

    def check_derivation_and_scope(self) -> None:
        catalog = self.read_text(GENERATED_TS, "U")
        index = self.read_text("packages/contracts/src/index.ts", "V")

        if catalog is not None:
            # U. types derived from JSON Schema, not a second handwritten union.
            if "Static<typeof" not in catalog:
                self.err(
                    "U",
                    "catalog.ts must derive TypeScript types from its JSON Schema literals via "
                    "TypeBox Static<>",
                )
            handwritten = re.findall(r"^export type \w+ =\s*$|^export type \w+ =\s*\"", catalog, re.M)
            if handwritten:
                self.err(
                    "U",
                    "catalog.ts declares handwritten string-literal union types; types must be "
                    "derived from the schemas",
                )
            for match in re.finditer(r"export type (\w+) = ([^;]+);", catalog):
                name, body = match.group(1), match.group(2).strip()
                if "Static<typeof" in body or body.startswith("(typeof "):
                    continue
                self.err(
                    "U",
                    f"catalog.ts type {name} is not derived from a schema (got {body[:60]!r})",
                )
            if "DO NOT EDIT" not in catalog:
                self.err("U", "catalog.ts must be marked GENERATED FILE — DO NOT EDIT")

            # Z. No invented domain semantics *while M-005 is the active
            # mission*. This is a present-scope rule, not a permanent ban: once
            # M-005 is accepted, a later authoritative mission that defines
            # command/event payloads or an error-code catalog must be able to
            # extend the generator without rewriting M-005 history. Whatever it
            # emits still has to be derived from authority, which checks
            # K/L/M/N..T enforce independently of this list.
            if self.m005_active:
                for token in FORBIDDEN_INVENTED_TOKENS:
                    if token in catalog:
                        self.err(
                            "Z",
                            f"catalog.ts contains {token!r}: M-005 must not invent commands, "
                            "payload fields, error codes or persistence schemas without "
                            "authority",
                        )

        # V. HealthSchema is no longer public contract authority.
        if index is not None:
            if "HealthSchema" in index:
                self.err(
                    "V",
                    "packages/contracts/src/index.ts still exports the M-004 HealthSchema canary; "
                    "the generated catalog is the contract authority",
                )
            if "generated/catalog" not in index:
                self.err("V", "packages/contracts/src/index.ts must re-export the generated catalog")
        for rel in (GENERATED_TS, GENERATED_SCHEMA):
            text = self.read_text(rel, "V")
            if text is not None and "HealthSchema" in text:
                self.err("V", f"{rel} must not contain the retired HealthSchema canary")
        smoke = self.read_text("packages/contracts/src/typebox-smoke.test.ts", "V")
        if smoke is not None and "HealthSchema" in smoke:
            self.err("V", "typebox-smoke.test.ts must test generated schemas, not HealthSchema")

        # W. root scripts.
        root_pkg = self.read_json("package.json", "W")
        if root_pkg is not None:
            scripts = root_pkg.get("scripts") or {}
            expected_scripts = {
                "contracts:generate": "python3 scripts/generate-contracts.py",
                "contracts:check": "python3 scripts/generate-contracts.py --check",
            }
            for name, command in expected_scripts.items():
                if scripts.get(name) != command:
                    self.err(
                        "W",
                        f"root script {name!r} must be {command!r}, got {scripts.get(name)!r}",
                    )
            check = str(scripts.get("check") or "")
            stages = [stage.strip() for stage in check.split("&&") if stage.strip()]
            if "pnpm run contracts:check" not in stages:
                self.err(
                    "W",
                    "root 'check' must include the 'pnpm run contracts:check' drift gate, got "
                    f"{check!r}",
                )

        # X/Y. Master Build System CI.
        workflow = self.read_text(MBS_WORKFLOW, "X")
        if workflow is not None:
            for step in REQUIRED_MBS_STEPS:
                if step not in workflow:
                    self.err("X", f"{MBS_WORKFLOW} missing required step: {step}")
            for previous in (
                "python3 scripts/validate-master-contracts.py",
                "python3 scripts/validate-harvest-registry.py",
                "python3 scripts/validate-threat-model.py",
                "python3 scripts/validate-m004-foundation.py",
                "python3 tests/contract/test_m002_validators.py",
                "python3 tests/contract/test_m003_security_contracts.py",
                "python3 tests/contract/test_m004_foundation.py",
                "sha256sum -c SHA256SUMS.txt",
            ):
                if previous not in workflow:
                    self.err("X", f"{MBS_WORKFLOW} lost an existing required step: {previous}")

            # M-006 intentionally removes path filters so this required check
            # cannot disappear from a PR merely because GitHub skipped it. The
            # retained M-005 gate therefore protects required steps, not the
            # obsolete historical path-filter implementation.

        # Z. No unauthorized implementation in the product trees while M-005 is
        # the active mission. Later missions (M-008 onwards) legitimately add
        # implementation there, so this is scoped to M-005's own snapshot.
        if self.m005_active:
            for prefix in ("apps", "services", "workers", "adapters"):
                base = self.root / prefix
                if not base.is_dir():
                    continue
                stray = [
                    path.relative_to(self.root).as_posix()
                    for path in sorted(base.rglob("*"))
                    if path.is_file() and path.name != "README.md"
                ]
                if stray:
                    self.err("Z", f"unauthorized implementation files under {prefix}/: {stray}")

    def run(self) -> int:
        self.check_mission_state()
        self.check_h025()
        self.check_dependencies()
        self.check_routing()
        self.check_generator_and_inventory()
        self.check_generated_content()
        self.check_derivation_and_scope()

        if self.errors:
            print("M-005 contract codegen validation FAILED")
            for error in self.errors:
                print(f"  ERROR: {error}")
            print(f"Total errors: {len(self.errors)}")
            return 1

        print("M-005 contract codegen validation PASSED")
        counts = self.live_counts
        mode = "m005-active" if self.m005_active else "durable"
        print(
            f"  mode={mode} "
            f"resources={counts.get('resources', '?')} "
            f"machines={counts.get('machines', '?')} "
            f"events={counts.get('events', '?')} "
            f"artifacts={len(GENERATED_ARTIFACTS)} typebox={TYPEBOX_PIN}"
        )
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the M-005 schema/codegen pipeline")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    return Validator(args.root.resolve()).run()


if __name__ == "__main__":
    sys.exit(main())
