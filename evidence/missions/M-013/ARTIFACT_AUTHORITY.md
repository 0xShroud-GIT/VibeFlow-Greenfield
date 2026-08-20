# M-013 — Artifact / ArtifactRelation authority evidence

## Identity and state

- Starting authoritative `main`: `6b54232ce6d105693fde9c72cd34fdde96f0f88f` (PR #18 merge)
- M-013 start commit: `0328541` (chore: start M-013 — READY → IN_PROGRESS)
- M-013 implementation commit: `585f52f19ede1bc2ca55d093db99d9ac3e0334f2` (feat: implement authoritative Artifact/ArtifactRelation)
- Arena branch: `arena/01a01c7d-vibeflow-greenfield` (session-fixed)
- Final mission state: `M-001..M-012 DONE`, `M-013 REVIEW`, `M-014..M-151 LOCKED`
- Capability advanced: `VF-PRJ-013 Artifact` → `IMPLEMENTED`

Machine-readable evidence in `ARTIFACT_AUTHORITY.json` is canonical. Final PR head and exact-head Actions runs are recorded in PR/final handoff because a commit cannot contain its own SHA.

## Authority chain

`Account -> Organization membership -> Project -> Artifact -> ArtifactRelation`

No client, agent, repository, workspace, blob store or provider may assert canonical Project/Organization ownership for an Artifact or relation. External/provider identities are reference-only.

## Artifact architecture

Implemented as canonical VibeFlow metadata only (blob/provider still owns bytes):

- `id`: server-generated canonical UUID
- `project_id`: required FK to canonical `projects.id`
- `type`: bounded, syntax-validated typed-output token (non-empty, trimmed, ≤ 200 chars)
- server-owned `created_at` / `updated_at`

The master proves Artifacts are typed outputs but defines **no closed canonical enum**, so M-013 did not invent a taxonomy. `type` is a bounded syntax-validated token; the normalized type registry (`VF-PRJ-017`) remains deferred.

## ArtifactRelation architecture

Directed `subject_artifact <relation_kind> object_artifact`, with `relation_kind` restricted to the exact canonical resource-model semantics: `lineage`, `variant`, `derived-from`, `contains`.

Minimum fields: server UUID `id`, `project_id`, `subject_artifact_id`, `object_artifact_id`, `relation_kind`, server-owned `created_at`.

### Database integrity (mandatory)

The DB makes a cross-Project edge impossible even if application code is bypassed:

- `artifacts` exposes a unique `(project_id, id)` key (`artifacts_project_id_id_uidx`)
- `artifact_relations(project_id, subject_artifact_id)` references `artifacts(project_id, id)`
- `artifact_relations(project_id, object_artifact_id)` references `artifacts(project_id, id)`
- `subject != object` self-edge CHECK
- duplicate `(project_id, subject, relation_kind, object)` edges rejected by unique constraint
- indexes for project/subject/object graph lookup

No client-provided `project_id` is accepted when creating a relation: the owning Project is derived from the canonical endpoint Artifacts and both endpoints must resolve to the same Project.

## Persistence

Migration `0005_artifact_authority.sql` creates `artifacts` and `artifact_relations` as above. `@vibeflow/persistence` gained `ArtifactRepository` with `createArtifact`, `getArtifactById`, `listArtifactsForProject`, `createArtifactRelation`, `getArtifactRelationById`, `listArtifactRelationsForProject`. Server authority via `newId()`, `now()`, `requireId`, `requireBoundedToken`, canonical relation-kind guard, and `rejectProviderAuthority`.

New errors: `CrossProjectArtifactRelationError`, `DuplicateArtifactRelationError`.

## Authorization integration

`RESOURCE_TYPES = ["organization", "project", "artifact", "artifact_relation"]`.

`authorizeArtifactResource` resolves Artifact → Project → Organization → membership; `authorizeArtifactRelationResource` resolves relation → Project → Organization → membership. Unknown resource, cross-tenant, forged actor, and revoked membership all fail closed.

## Service boundary

`@vibeflow/project` gained `ArtifactService` (`artifact-service.ts`):

- `createArtifact`, `getArtifact`, `listArtifacts`
- `createArtifactRelation`, `getArtifactRelation`, `listArtifactRelations`

No transform, publish, export, import, version, archive, delete or lifecycle behavior was added.

## Audit integration

`@vibeflow/audit` `recordAuthorizationDecision` resolves canonical Organization scope by joining through Project ownership:

- artifact: `SELECT p.organization_id FROM artifacts a JOIN projects p ON p.id = a.project_id WHERE a.id = $1`
- relation: `SELECT p.organization_id FROM artifact_relations r JOIN projects p ON p.id = r.project_id WHERE r.id = $1`

Database/scope-resolution errors propagate; an otherwise-allowed decision becomes `DENY / audit_unavailable`. Unknown resources may produce unscoped denied audit rows; a database failure is never silently converted to `organization_id = null` for an allowed decision.

## Event policy

No new durable `artifact.*` event names were invented. `EVENT_CATALOG.yaml` defines no Artifact event; the frontend/backend matrix's `artifact.*` is a UI projection, not an independent authoritative vocabulary (confirmed by the master-contracts validator notes).

## Testing

Unit:

- `decision.test.ts` updated to assert inclusion of the canonical resource types (organization, project, artifact, artifact_relation) rather than an exact list, so a later mission's registration does not break a retained M-010/M-012 assertion.
- `metadata.test.ts`, `authority.test.ts` retained and PASS.

Contract:

- `test_m008` … `test_m012` retained and PASS; `test_m013_artifact.py` 8 tests PASS.

Live PostgreSQL (requires `DATABASE_URL`, skipped locally, must run in CI exact-head):

- `packages/persistence/src/artifact.live.test.ts`: canonical creation, type token, tenant-safe list, unknown UUID, provider authority rejection, forged FK, same-project relation, unknown endpoint, cross-project relation, self-edge, duplicate edge, invalid kind, DB composite-FK backstop, indexes.
- `packages/authorization/src/artifact.live.test.ts`: same-tenant read, cross-tenant read, forged actor, unknown UUID, revoked membership, canonical persistence, relation read success/cross-tenant/unknown.
- `packages/project/src/artifact.live.test.ts`: creation, same-tenant read, cross-tenant read/create, forged project/actor, unknown UUID, revoked membership, canonical persistence + audit scoping, same-project relation, unknown endpoint, cross-project same-org relation, cross-tenant relation, forged relation id, tenant-safe list.
- `packages/audit/src/artifact-scope.live.test.ts`: forced canonical Artifact/ArtifactRelation audit-scope query failure must return `audit_unavailable` and persist no false `allowed` audit row.

`scripts/run-m013-artifact-integration.py` runs the persistence/authorization/project suites explicitly; `pnpm run check` executes all package Vitest suites and the new contract/integration steps. `packages/audit/tsconfig.json` excludes `artifact-scope.live.test.ts` from the production build (mirroring the M-012 `project-scope.live.test.ts` isolation) while Vitest still executes it.

## Local checks

- `pnpm install --frozen-lockfile` — PASS (no new dependencies)
- `pnpm run typecheck` — 16/16 PASS
- `pnpm run test` — 16/16 PASS (live skipped without DB, expected)
- `python3 tests/contract/test_m013_artifact.py` — 8 PASS
- retained `test_m008..m012` — PASS
- `pnpm run contracts:check` — PASS
- `python3 scripts/validate-m004-foundation.py` — PASS
- `python3 scripts/validate-master-contracts.py` — PASS
- `pnpm run reference:validate` — PASS
- `pnpm run security:validate` — PASS
- `pnpm run dev:validate` — PASS
- `git diff --check` — PASS

## Repository hygiene

`packages/project/tsconfig.tsbuildinfo` (a TypeScript composite build artifact) was removed from tracking and `*.tsbuildinfo` added to `.gitignore` so `pnpm run build` does not reintroduce a non-seed file into the implementation tree.

## Capability ledger

- `VF-PRJ-013 Artifact` NOT_STARTED → IMPLEMENTED
- `VF-PRJ-001 Artifact Registry`, `VF-PRJ-002 ArtifactVersion`, `VF-PRJ-003 ArtifactGraph`, `VF-PRJ-017 Typed Artifact Graph` remain NOT_STARTED/DEFER

`CAPABILITY_CONTRACT_TRACE.csv` updated for `VF-PRJ-013`.

## Known limitations / explicitly deferred

- `type` is a bounded token, not a normalized registry (`VF-PRJ-017` deferred)
- No ArtifactVersion (`VF-PRJ-002`), ArtifactGraph (`VF-PRJ-003`), Artifact Registry product behavior (`VF-PRJ-001`)
- No imports/templates (M-014), full Project lifecycle E2E (M-015), provider bindings (M-016+)
- No durable `artifact.*` event contract
- PostgreSQL live not executed locally; CI must run exact-head

## Overclaim check

M-013 is REVIEW, not DONE. `VF-PRJ-013` is IMPLEMENTED, not VERIFIED/COMPLETE. PostgreSQL live not claimed locally. M-014+ remain LOCKED. No Artifact event contract was invented.
