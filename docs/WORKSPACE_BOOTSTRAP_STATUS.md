# Workspace Bootstrap Status

- Repository seed: READY
- Product implementation: IN_PROGRESS (M-014 imports/templates lifecycle)
- Active mission: M-014 — Implement imports/templates lifecycle (IN_PROGRESS, handed off at REVIEW)
- Accepted missions: M-001..M-013 (DONE)
- Locked missions: M-015..M-151 (deferred non-J1 missions remain required for V1)
- Master Build System: `master-build-system/`
- Capability ledger: 405 VibeFlow capabilities
- Mission register: 151 missions / 33 phases
- Canonical resources: 35
- Dev environment descriptor: `.devcontainer/devcontainer.json` (Dev Containers, H-023)
- Dev environment policy lock: `infrastructure/dev/dev-environment-policy.json`

The seed contains no harvested third-party source code. Direct npm coordinates
are reconciled to ratified harvest entries. Package install/build scripts are
deny-by-default and require an explicit harvest-side package approval and
rationale.

M-004 repository foundation remains Node 24.19.0, pnpm 11.4.0, TypeScript 6.0.3,
Turborepo 2.10.6, Vitest 4.1.7, and TypeBox 1.3.6. M-005's deterministic
schema/codegen pipeline and M-006's CI/security/dependency gates remain
retained and checked.

M-007 established the repository development environment and is `DONE`.
`VF-ENV-005 Environment Definition` remains `IN_PROGRESS`: existing M-007
evidence records the repository Dev Container, not the product Environment
Definition verification gate (`Environment parsing/port/dependency
reproducibility tests`), and explicitly forbids claiming
IMPLEMENTED/VERIFIED/COMPLETE. A product-container scan remains N/A because no
product image exists. The active `VibeFlow main protection` repository ruleset
protects `main` with pull-request, review-thread, update-branch, deletion,
force-push, and established required-status-check enforcement.

M-014 implements the project import/template lifecycle: `VF-PRJ-004 Project
Archive Import` (ZIP/tar intake behind a structural archive scanner, with a
deterministic server-derived manifest) and `VF-PRJ-007 Project Clone Plan`
(template instantiation as a new canonical Project cloned from an authorized
source Project). Both advance to `IMPLEMENTED` only; neither is claimed
VERIFIED or COMPLETE, and no other PRJ capability advances. M-014 adds no
canonical `Import`/`Template`/`Clone` resource, no new authorization resource
type, no new event family, and no new public state machine — the lifecycle
lives in project-domain internal records and reuses canonical `project.created`
semantics. Provider/Git/workspace scope (VF-PRJ-008..012, RepositoryBinding,
WorkspaceBinding) remains deferred and unimplemented.
