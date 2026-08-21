# VibeFlow

VibeFlow is an open, mobile-first control, policy, recovery, and verification layer for agentic software development.

This repository builds from the **VibeFlow Greenfield Master Build System v1.0**. The build system is the authoritative product/architecture/implementation contract. Replit research is retained only as clean-room capability evidence; it is not source code or an implementation input.

## Start here

Human or AI contributor:
1. Read `AGENTS.md`.
2. Read `master-build-system/00_MASTER/MASTER_OF_MASTERS.md`.
3. Read `.ai/ACTIVE_MISSION.md`.
4. Load only the mission-specific context required by the active mission and `.ai/INDEX.yaml`.
5. Work on a branch and open a PR. Never silently widen scope.

## Mission state

The current authoritative active/reviewable mission is **M-016**. This pointer exists because retained integrity validation requires human-facing entry points to name the mission selected by the DAG; do not infer broader status or acceptance from this README.

- Current mission packet: `.ai/ACTIVE_MISSION.md`
- Authoritative mission status/dependencies: `master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml`
- Human-readable mission register: `master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv`
- Historical acceptance evidence: `evidence/missions/`

Update the M-016 pointer in this README only in the same mission-progression change that updates the authoritative DAG. If a historical document or evidence file disagrees with current mission authority, the Master Build System and mission DAG win.

## Repository map

- `master-build-system/` — authoritative product, architecture, security, mission, and verification contracts.
- `packages/` — shared product/domain packages, including contract-tested seed surfaces for later missions.
- `apps/`, `services/`, `workers/`, `adapters/` — mission-owned implementation surfaces; placeholders are retained intentionally until their missions activate.
- `migrations/` — durable persistence migrations introduced by accepted missions.
- `evidence/` — retained historical acceptance and verification evidence; not live implementation direction.
- `reference/oss-harvest/` — clean-room implementation-reference evidence governed by the harvest policy.
- `docs/` — implementation-facing documentation and ADRs; not mission-status authority except the validator-required mission pointer file.
- `scripts/`, `tests/`, `security/`, `infrastructure/` — retained repository, verification, security, and environment tooling.

## Contracts

`packages/contracts` publishes the canonical contract catalog — resource names, state machines and event catalog metadata — generated from the Master Build System. Generated files are derived artifacts marked DO NOT EDIT.

```bash
pnpm run contracts:generate   # regenerate from master authority
pnpm run contracts:check      # fail on missing/stale/unexpected generated output
```

Command/event payload schemas, REST payloads, persistence schemas and error codes are introduced only when an authoritative domain mission defines them. See `packages/contracts/README.md`.
