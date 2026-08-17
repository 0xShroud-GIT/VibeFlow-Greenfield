# M-004 — Repository Foundation Evidence

## Identity

- Mission: `M-004 — Initialize monorepo and toolchain`
- Phase: `1 — Repository Foundation`
- Starting main: `7b45fecc39a50569e91cf3a92b3d0f97a79d86c4`
- Branch: `arena/01a011b9-vibeflow-greenfield`
- PR: `#5`
- Mission state: `M-001 DONE · M-002 DONE · M-003 DONE · M-004 REVIEW · M-005+ LOCKED`
- Final head and CI are bound externally to PR #5 after this evidence commit; this file does not claim a self-referential final SHA.

## Foundation

Exact direct pins:

- Node.js `24.19.0` — H-001
- pnpm `11.4.0` — H-003
- TypeScript `6.0.3` — H-002
- Turborepo `2.10.6` — H-004
- Vitest `4.1.7` — H-028
- TypeBox `1.3.6` — H-025, package `typebox`, ESM 1.x line

TypeBox 1.x is the M-004 choice delegated by H-025. Only `packages/contracts` depends on it. The compatibility smoke test is `packages/contracts/src/typebox-smoke.test.ts`.

Exactly seven shared package shells are initialized:

`@vibeflow/core`, `@vibeflow/contracts`, `@vibeflow/remote`, `@vibeflow/bridge`, `@vibeflow/provider-sdk`, `@vibeflow/verification`, `@vibeflow/ui`.

Each is private, version `0.0.0`, ESM, strict TypeScript, and exposes only cross-platform `build`, `typecheck`, and `test` foundation scripts. No product implementation or runtime/service package manifests were introduced under `apps/*`, `services/*`, `workers/*`, or `adapters/*`.

## Independent audit correction

Arena's initial implementation placed project pnpm policy in `.npmrc`. During review this was rejected: pnpm 11 project settings are enforced from `pnpm-workspace.yaml`; `.npmrc` is retained only for registry/authentication concerns.

The corrected `pnpm-workspace.yaml` enforces:

```yaml
minimumReleaseAge: 1440
minimumReleaseAgeStrict: true
minimumReleaseAgeIgnoreMissingTime: false
blockExoticSubdeps: true
strictDepBuilds: true
trustLockfile: false
```

`dangerouslyAllowAllBuilds` is absent. `allowBuilds` is absent because M-004 has no approved dependency build-script exception. The M-004 validator and mutation suite explicitly fail if these project settings are moved into `.npmrc`, weakened, or bypassed.

The review also removed `rm -rf dist` package scripts so the repository foundation does not depend on a Unix-only convenience command.

## Dependency and lockfile policy

- One root `pnpm-lock.yaml`; no nested pnpm lockfiles.
- No npm/yarn/bun lockfiles.
- Direct dependencies use exact pins; no `^`, `~`, dist-tags, git/http/file/link sources.
- No dependency beyond the M-004-approved set is installed.
- Internal workspace package dependencies are intentionally absent at M-004.

## CI / enforcement

M-004 adds `.github/workflows/repository-foundation.yml` and extends `.github/workflows/master-build-system-integrity.yml`.

Repository Foundation performs exact Node/pnpm checks, `pnpm install --frozen-lockfile`, and `pnpm run check`.

Master Build System Integrity retains all prior M-001/M-002/M-003 enforcement and adds:

- `python3 scripts/validate-m004-foundation.py`
- `python3 tests/contract/test_m004_foundation.py`

Exact-head GitHub Actions run IDs and conclusions are intentionally not fabricated here; they must be read from PR #5 after the final branch head is pushed.

## Capability / scope

Capability ledger reviewed; repository foundation does not claim completion of any product capability. All 405 capability statuses remain `NOT_STARTED`.

M-004 does not implement schema/codegen (M-005), full security/dependency CI gates (M-006), full local/dev-container orchestration (M-007), or product features such as auth, agents, workspaces, Git, deployment, billing, database schema, Temporal, MCP/ACP/A2A, or provider integrations.

No ADR is required: the TypeBox line choice was explicitly delegated to M-004 and no ratified architecture decision was reversed.

## Pack integrity

Only the M-004 mission transition changes authoritative pack content: `MISSION_DAG.yaml` and `MISSION_REGISTER.csv`, with their entries updated in `master-build-system/SHA256SUMS.txt`. All authoritative hashes must pass on the exact PR head before acceptance.
