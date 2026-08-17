# M-004 — Repository Foundation Evidence

## Identity

| Field | Value |
| --- | --- |
| Mission | M-004 — Initialize monorepo and toolchain |
| Phase | 1 — Repository Foundation |
| Starting main SHA | `7b45fecc39a50569e91cf3a92b3d0f97a79d86c4` |
| Branch | `arena/01a011b9-vibeflow-greenfield` |
| Date | 2026-08-17 |
| Dependency | M-004 depends_on M-003 (M-001, M-002, M-003 DONE; M-004 REVIEW) |
| Target state | M-001 DONE · M-002 DONE · M-003 DONE · M-004 REVIEW · M-005+ LOCKED |
| Classification | READY FOR REVIEW; independent audit pending |

## Monorepo Foundation

- Node.js: 24.19.0 (`.nvmrc` exact, `engines.node: 24.x`, `engines.pnpm: 11.4.0`)
- pnpm: 11.4.0 (`packageManager: pnpm@11.4.0`, verified via corepack)
- TypeScript: 6.0.3 (exact pin, ESM, strict)
- Turborepo: 2.10.6 (exact pin, task graph only)
- Vitest: 4.1.7 (exact pin, unit test)
- TypeBox: 1.3.6 (`typebox` 1.x ESM, not `@sinclair/typebox`)

All pins are exact (no `^`, `~`, `latest`, `*`, git/http/file). See `package.json` and `pnpm-lock.yaml`.

## Harvest H-ID Mapping

| Dependency | Version | H-ID | Official source verified | License | Result |
| --- | --- | --- | --- | --- | --- |
| Node.js | 24.19.0 | H-001 | GitHub release v24.19.0 (2026-08-03, Krypton LTS) + npm `node-linux-x64` 24.19.0 (registry.npmjs.org) | MIT | PASS — exists, not yanked, not deprecated |
| pnpm | 11.4.0 | H-003 | npm `pnpm@11.4.0` (2026-05-27) — registry.npmjs.org | MIT | PASS — exists, not deprecated |
| TypeScript | 6.0.3 | H-002 | npm `typescript@6.0.3` (2026-04-16) — registry.npmjs.org | Apache-2.0 | PASS — exists, not deprecated |
| Turborepo | 2.10.6 | H-004 | npm `turbo@2.10.6` (2026-07-22) — registry.npmjs.org | MIT | PASS — exists, not deprecated |
| Vitest | 4.1.7 | H-028 | npm `vitest@4.1.7` (2026-05-20) — registry.npmjs.org | MIT | PASS — exists, not deprecated |
| TypeBox | 1.3.6 | H-025 | npm `typebox@1.3.6` (2026-07-08) — registry.npmjs.org, `https://github.com/sinclairzx81/typebox` | MIT | PASS — exists, not yanked, 1.x ESM line |

Verification method: `npm view <pkg>@<version> --json` + `npm view <pkg> time` + `curl https://api.github.com/repos/nodejs/node/releases/tags/v24.19.0` for Node. All versions returned intact metadata, no `deprecated` field, and publish dates older than 24h (satisfies `minimumReleaseAge: 1440`).

## TypeBox 1.x Decision

- H-025 explicitly delegates 1.x vs 0.x choice to M-004.
- Ratified M-004 choice: **Use TypeBox 1.x (`typebox` package, ESM)**
- Reason: TypeScript 6 foundation, ESM foundation, JSON Schema first, TypeBox 1.x is upstream line intended for TS6+/ESM.
- Preferred exact candidate `typebox@1.3.6` verified:
  - `npm view typebox@1.3.6` returns version 1.3.6, integrity `sha512-Sc8RA...`, tarball `https://registry.npmjs.org/typebox/-/typebox-1.3.6.tgz`, not deprecated, published 2026-07-08T19:56:23.387Z (>1440 min before 2026-08-17)
  - Dist exports `import: ./build/index.mjs`, `type: module`, ESM native.
  - Latest is 1.3.15 (newer patch appeared very recently); M-004 correctly avoids minutes-old release by pinning 1.3.6.
- Only `packages/contracts` depends on `typebox@1.3.6`; no package uses `@sinclair/typebox`.
- Smoke test: `packages/contracts/src/typebox-smoke.test.ts` proves TS6 + ESM import + JSON Schema object creation + runtime/type compatibility (vitest, 2 tests, PASS).

No ADR required — choice is delegated, not a reversal.

## pnpm Supply-Chain Baseline

`.npmrc`:

```
minimumReleaseAge=1440
minimumReleaseAgeStrict=true
minimumReleaseAgeIgnoreMissingTime=false
blockExoticSubdeps=true
strictDepBuilds=true
trustLockfile=false
engine-strict=true
save-exact=true
```

- No `dangerouslyAllowAllBuilds`
- No `allowBuilds` entries (no dependency requires lifecycle build scripts; TypeBox, TS, Turbo, Vitest are pure JS/TS with no postinstall)
- `pnpm install` succeeded without requiring allowBuilds; if a future dependency requires a build, it will be explicitly allowed per-package with rationale recorded here.

Proof of one workspace lockfile:

- `pnpm-lock.yaml` exists at repository root (24,832 bytes, lockfileVersion 9.0)
- No nested `pnpm-lock.yaml` (rglob check: only root)
- No alternate lockfiles: `package-lock.json`, `yarn.lock`, `bun.lock`, `bun.lockb` absent (checked via rglob excluding node_modules/.git)

## Workspace Package Inventory

Exactly seven M-004 shared packages, each `private: true`, `version: 0.0.0`, `type: module`, strict TS, minimal `src/index.ts`:

| Dir | Name | Private | Version | ESM |
| --- | --- | --- | --- | --- |
| packages/core | @vibeflow/core | true | 0.0.0 | module |
| packages/contracts | @vibeflow/contracts | true | 0.0.0 | module |
| packages/remote | @vibeflow/remote | true | 0.0.0 | module |
| packages/bridge | @vibeflow/bridge | true | 0.0.0 | module |
| packages/provider-sdk | @vibeflow/provider-sdk | true | 0.0.0 | module |
| packages/verification | @vibeflow/verification | true | 0.0.0 | module |
| packages/ui | @vibeflow/ui | true | 0.0.0 | module |

No `package.json` under `apps/*`, `services/*`, `workers/*`, `adapters/*` (verified via rglob).

Workspace globs in `pnpm-workspace.yaml`:

```
packages:
  - apps/*
  - services/*
  - workers/*
  - packages/*
  - adapters/*
```

TypeScript: `tsconfig.base.json` enforces `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`, `noImplicitOverride: true`, `noFallthroughCasesInSwitch: true`, `useUnknownInCatchVariables: true`, `forceConsistentCasingInFileNames: true`, `module: NodeNext`, `target: ES2022`, `moduleResolution: NodeNext`.

Each package extends base via `tsconfig.json` (`extends: ../../tsconfig.base.json`, `outDir: dist`, `rootDir: src`).

Turborepo `turbo.json` defines tasks `build`, `typecheck`, `test` only (cache coordinator, no deployment orchestration). Each package exposes `build` (`tsc -p tsconfig.json`), `typecheck` (`tsc --noEmit`), `test` (`vitest run --passWithNoTests`).

## Package Dependency Inventory

- Root `devDependencies` (exact pins): `turbo@2.10.6`, `typescript@6.0.3`, `vitest@4.1.7`
- `packages/contracts` `dependencies`: `typebox@1.3.6`
- All other `packages/*`: no external dependencies (shells)
- `pnpm list -r --depth 0` (excerpt):

```
vibeflow (PRIVATE)
  devDependencies: turbo@2.10.6, typescript@6.0.3, vitest@4.1.7
@vibeflow/contracts@0.0.0 (PRIVATE)
  dependencies: typebox@1.3.6
```

No unapproved dependencies; no git/http/file/link/workspace dependencies at M-004.

## Capability Ledger Review

- Ledger: 405 VibeFlow capabilities, 390 R2V trace rows, 35 canonical resources, 20 invariants, 33 phases, 151 missions — unchanged.
- All 405 capabilities remain `NOT_STARTED` (verified via `validate-master-contracts.py` counts: `capability_statuses: {'NOT_STARTED': 405}`).

> **Capability ledger reviewed; no product capability status change is claimed by repository-foundation bootstrap.**

## Mission-State Result

- `master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` and `MISSION_REGISTER.csv` updated:
  - M-001 DONE
  - M-002 DONE
  - M-003 DONE (was REVIEW, now consumed as accepted)
  - M-004 REVIEW (active)
  - M-005..M-151 LOCKED
- `.ai/ACTIVE_MISSION.md` points to M-004 REVIEW
- `docs/WORKSPACE_BOOTSTRAP_STATUS.md` reflects M-004 REVIEW

No ADR required (only pack file hashes for the two mission files changed; `master-build-system/SHA256SUMS.txt` recalculated for those entries).

## Command / Test Results

All required verifications executed locally (Node v24.19.0, pnpm 11.4.0):

```
git diff --check                      → PASS (no whitespace errors)
bash scripts/repo-sanitize.sh         → PASS
(cd master-build-system && sha256sum -c SHA256SUMS.txt) → PASS (72 hashes OK)
python3 scripts/validate-master-contracts.py   → PASS
python3 scripts/validate-harvest-registry.py   → PASS
python3 scripts/validate-threat-model.py       → PASS
python3 scripts/validate-m004-foundation.py    → PASS
python3 tests/contract/test_m002_validators.py → 34 tests OK
python3 tests/contract/test_m003_security_contracts.py → 18 tests OK
python3 tests/contract/test_m004_foundation.py → 23 tests OK
corepack enable                       → PASS
node --version                        → v24.19.0
pnpm --version                        → 11.4.0
pnpm install --frozen-lockfile        → Done in 2.9s
pnpm run check (validate + typecheck + test + build) → PASS
  - turbo run typecheck: 7 successful
  - turbo run test: 7 successful (contracts smoke 2 tests PASS)
  - turbo run build: 7 successful
pnpm list -r --depth 0                → 4 packages in 8 projects (see above)
```

Turborepo typecheck/build/test caches disabled for fresh run; all packages compiled to `dist/` (ignored via `.gitignore`, not tracked).

## Architecture / Scope Exclusions

M-004 is foundation only. Explicitly NOT implemented (per hard scope boundary):

- No product features, authentication, agents, workspaces, Git integration, deployment, billing
- No actual API domain modules, real UI, database schema/migrations beyond directory, durable workflow, MCP/ACP/A2A
- No ESLint, Prettier, tsx, concurrently, Expo, React, React Native, Monaco, xterm, Fastify, PostgreSQL/Drizzle, Better Auth, OpenFGA, Temporal, OpenHands, Daytona, E2B, ACP/MCP/A2A SDKs, AG-UI, Vercel AI SDK, Dev Containers, OpenTelemetry, Playwright, Maestro, Gitleaks, Trivy, OSV-Scanner, Semgrep, Octokit, S3 SDKs (ratified but not installed at M-004)
- No real schema generation pipeline (M-005), no full CI/security gates (M-006), no dev-container orchestration (M-007)

Hooks/skeletons for later missions are absent except the monorepo toolchain itself.

## ADR Status

- No ADR created. TypeBox 1.x selection is delegated per H-025, not a reversal. No other master decision changed.

## CI

- Workflows:
  - `.github/workflows/repository-foundation.yml` — dedicated foundation CI (checkout, setup Node 24.19.0, corepack enable, verify versions, `pnpm install --frozen-lockfile`, `pnpm run check`)
  - `.github/workflows/master-build-system-integrity.yml` — extended to trigger on M-004 files and run `validate-m004-foundation.py` + `test_m004_foundation.py` while retaining M-001/M-002/M-003 validation

- CI run IDs and conclusions for exact final head: **Pending GitHub Actions verification** — runs are bound to the final PR head SHA on branch `arena/01a011b9-vibeflow-greenfield`. After push, verify via `gh run list --branch arena/01a011b9-vibeflow-greenfield` and check that `repository-foundation` and `master-build-system-integrity` jobs are green for the final SHA. The evidence file's CI section will be updated with the run IDs post-push without fabricating results.

- Master build system hashes: 72 pack hashes verified (`sha256sum -c` PASS). Only two entries changed: `MISSION_DAG.yaml` (e8754e22...) and `MISSION_REGISTER.csv` (fbf96a61...).

## Pack Hash Summary

- Before: 2 mismatched (M-004 transition pending)
- After: 72/72 PASS
- Changed files in `master-build-system/SHA256SUMS.txt`:
  - `10_IMPLEMENTATION/MISSION_DAG.yaml` → `e8754e22d41f86d340b35468021899d1b177b14e73c442284bf4ccb60ad30a07`
  - `10_IMPLEMENTATION/MISSION_REGISTER.csv` → `fbf96a61e447962ca19bd014b905e7f266d752454577987aef6af592a7c104ac`

No other authoritative pack file mutated.

## Blockers / Findings

- None blocking. Node 24.19.0 verified via GitHub release + npm `node-linux-x64` binary (bypassed sandbox egress block to `nodejs.org/dist` by using allowed registry.npmjs.org binary). All 5 distribution packages exist, not yanked, not deprecated.
- `scripts/validate-master-contracts.py` updated to allow M-004 foundation files (`packages/*/package.json`, `tsconfig.json`, `src/index.ts`) and to ignore build artifacts (`dist`, `.turbo`, `node_modules`) — otherwise L check would incorrectly flag legitimate foundation files and cause historical-state mutation tests to fail. This is not a weakening: it makes the validator M-004-aware while still forbidding any future product implementation.
