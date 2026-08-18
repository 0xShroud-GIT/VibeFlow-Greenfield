# Active Mission

**Mission:** M-005 — Establish schema/codegen pipeline

**Status:** REVIEW

**Phase:** 1 — Repository Foundation

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-005)

M-001 and M-002 were accepted and merged and are `DONE` (canonical terminal mission state per `10_IMPLEMENTATION/STATUS_PROTOCOL.md`).
M-003 was accepted and merged and is `DONE`.
M-004 was accepted, merged and post-merge verified and is `DONE`.

M-005 is the active mission. M-006..M-151 remain LOCKED per mission DAG.

Read before coding:
- `AGENTS.md`
- `master-build-system/00_MASTER/MASTER_OF_MASTERS.md`
- `master-build-system/00_MASTER/NON_NEGOTIABLE_INVARIANTS.yaml`
- `master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml`
- `master-build-system/02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml`
- `master-build-system/03_BACKEND/STATE_MACHINES.yaml`
- `master-build-system/03_BACKEND/EVENT_CATALOG.yaml`
- `master-build-system/09_CONTRACTS/CONTRACT_RULES.md`
- `master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml`
- `master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml`

## M-005 scope

Establish the deterministic schema/codegen pipeline that derives runtime
contracts from the Master Build System:

- `scripts/generate-contracts.py` (stdlib only; `--check` performs no writes)
- generated catalog in `packages/contracts` (JSON Schema first, TS types derived
  through TypeBox 1.x `Static<>`)
- `contracts:generate` / `contracts:check` root scripts, with `contracts:check`
  wired into root `check` for drift detection

M-005 does **not** invent domain authority: no command/event payload schemas, no
REST request/response shapes, no persistence schemas and no error-code catalog,
because the master pack does not yet define them.

Do not execute M-006 or any later mission.
M-005 may be marked REVIEW, never DONE, until independent acceptance.

Final branch mission state must be:
M-001 DONE · M-002 DONE · M-003 DONE · M-004 DONE · M-005 REVIEW · M-006+ LOCKED
