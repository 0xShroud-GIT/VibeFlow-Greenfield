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

M-001 through M-011 are accepted and `DONE` after independent verification and merge. The sole active mission is `M-012` (Implement Project authority), in `IN_PROGRESS`. M-013 and later missions remain `LOCKED` and remain required for V1.

M-006 added machine-enforced harvest-to-package reconciliation, deny-by-default install/build-script approvals, immutable scanner and GitHub Action pins, local Semgrep rules, full-history secret scanning, dependency/repository vulnerability gates, and an ephemeral CycloneDX repository SBOM. The active `VibeFlow main protection` repository ruleset protects `main`: pull requests and resolved review threads are required, force-pushes and deletion are blocked, branches must be current, and the established `verify`, `foundation`, `sanitize`, and `security-gate` contexts are required.

M-007 adds a reproducible, secure, provider-neutral development environment: a Dev Containers descriptor (`.devcontainer/devcontainer.json`) pinned to the official `node:24.19.0` image by immutable digest, one digest-pinned registered python feature, a provenance/security policy lock (`infrastructure/dev/dev-environment-policy.json`), stdlib-only doctor/bootstrap/runtime-smoke commands (`pnpm run dev:doctor`, `pnpm run dev:bootstrap`), and a retained static validator plus adversarial mutation suite. The accepted M-007 repository dev container is deliberately boring: non-root user, no privileges, no host networking, no Docker socket, no forwarded product ports, and no product services. The repository development environment is not the VibeFlow Workspace product.

`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` is authoritative for mission status; this section is a pointer to it.

## Contracts

`packages/contracts` publishes the canonical contract catalog — resource names, state machines and event catalog metadata — generated from the Master Build System. Generated files are derived artifacts marked DO NOT EDIT.

```bash
pnpm run contracts:generate   # regenerate from master authority
pnpm run contracts:check      # fail on missing/stale/unexpected generated output
```

Command/event payload schemas, REST payloads, persistence schemas and error codes are intentionally absent until an authoritative domain mission defines them. See `packages/contracts/README.md`.
