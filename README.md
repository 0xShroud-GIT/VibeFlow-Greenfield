# VibeFlow

VibeFlow is an open, mobile-first control, policy, recovery, and verification layer for agentic software development.

This repository begins from the **VibeFlow Greenfield Master Build System v1.0**. The build system is the authoritative product/architecture/implementation contract. Replit research is retained only as clean-room capability evidence; it is not source code or an implementation input.

## Start here

Human or AI contributor:
1. Read `AGENTS.md`.
2. Read `master-build-system/00_MASTER/MASTER_OF_MASTERS.md`.
3. Read `.ai/ACTIVE_MISSION.md`.
4. Load only the mission-specific context listed by that mission.
5. Work on a branch and open a PR. Never silently widen scope.

## Current state

Repository foundation established; product implementation has not started. The active mission is `M-005` (establish schema/codegen pipeline), in `REVIEW`. `M-001`, `M-002`, `M-003` and `M-004` are `DONE` after acceptance and merge. `M-006` and later remain `LOCKED`; do not start them until M-005 is independently accepted.

`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` is authoritative for mission status; this section is a pointer to it.

## Contracts

`packages/contracts` publishes the canonical contract catalog — resource names, state machines and event catalog metadata — generated from the Master Build System. Generated files are derived artifacts marked DO NOT EDIT.

```bash
pnpm run contracts:generate   # regenerate from master authority
pnpm run contracts:check      # fail on missing/stale/unexpected generated output
```

Command/event payload schemas, REST payloads, persistence schemas and error codes are intentionally absent until an authoritative domain mission defines them. See `packages/contracts/README.md`.
