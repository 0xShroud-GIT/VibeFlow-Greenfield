# M-012 — Project authority evidence

## Identity and state

- Starting authoritative `main`: `b9f68c7c9062298e2be7d07cdd2c1d0976f5c13f` (PR #16 merge)
- M-011 closure commit: `83f01bbbbb16007b1f0e50c24539f2ddbef8b682` (chore: close M-011 and ready M-012)
- M-012 start commit: `caffe9c484a033c219402e8bd83709164d490f30` (chore: start M-012)
- M-012 implementation commits: `256a54e265bd7455128e81418dc00326f937e824` (feat: implement authoritative Project) and `8d8a26ae2d3d665c55d8ac73e1272cd4a92f15fc` (docs: mark REVIEW and advance ledger)
- Retained-test stabilization commits: `b0d1c2f63c4ec94292f90d82cbe09c3f450e42fe`, `89c5b13e07221743c4e55a096053d5c604f4bbce`, `a26985990505fea2cb08334f1efc827965a145b0`, `bcd4f07beddc107a1a3ae9a457e8f3d9a75f2619`
- Independent-review remediation commits: `3bf6b815d4117c5e7434144382cfc4b13ef6e61c` (propagate canonical audit scope-resolution errors) and `fc8ce5938c2ab4d0e86c80c3386d3e24fdc83373` (PostgreSQL fail-closed regression)
- Arena branch: `arena/01a01bbd-vibeflow-greenfield` (session-fixed)
- Final mission state: `M-001..M-011 DONE`, `M-012 REVIEW`, `M-013..M-151 LOCKED`
- Capabilities advanced: `VF-IAM-010`, `VF-PRJ-005`, `VF-PRJ-015` → `IMPLEMENTED`

Machine-readable evidence in `PROJECT_AUTHORITY.json` is canonical. Final PR head and exact-head Actions runs are recorded in PR/final handoff because a commit cannot contain its own SHA.

## Retained-test stabilization

M-012 exposed several retained tests that encoded historical current-state details instead of durable invariants. Those tests were corrected without weakening security behavior:

- M-005 no longer permanently asserts that M-011 is the active mission. It verifies the durable M-001..M-005 `DONE` baseline, exactly one active mission, DAG/register parity, and active-mission pointer parity.
- Retained authorization unknown-resource-type tests use `__vibeflow_test_unknown_resource_type__` rather than names such as `project`, `workspace`, or `task` that may become canonical resources in later missions.
- The historical M-007 fixture reconstructs the complete accepted capability snapshot in one pass: every capability returns to `NOT_STARTED` except `VF-REL-002/003/004=IMPLEMENTED`, `VF-REL-005=IN_PROGRESS`, and `VF-ENV-005=IN_PROGRESS`. Later mission capability progress can no longer leak into the historical fixture.
- Fail-closed, cross-tenant, malformed-input, unknown-resource, mutation, and security assertions remain enforced; only time-coupling was removed.

These changes add the following candidate-scope files to the M-012 evidence set: `packages/authorization/src/tenant.live.test.ts`, `tests/contract/test_m005_contract_codegen.py`, and `tests/contract/test_m007_local_dev.py`.

## Independent-review remediation

Independent review found that Project audit tenant-scope lookup errors were being swallowed, allowing an otherwise-valid Project authorization to remain `ALLOW` even if the audit layer could not resolve canonical `organization_id`. The remediation removes that error swallowing for both canonical Organization and Project scope lookups:

- a missing resource still produces zero rows and may be recorded as account-scoped denial evidence;
- a database/query failure now propagates from `AuditService.recordAuthorizationDecision`;
- `TenantAuthorizationService.recordRequiredAudit` converts an otherwise-allowed decision to `DENY / audit_unavailable`;
- `packages/audit/src/project-scope.live.test.ts` injects a failure into `SELECT organization_id FROM projects WHERE id = $1`, proves `audit_unavailable`, and proves no false Project `allowed` audit row is persisted.

This adds `packages/audit/src/project-scope.live.test.ts` to the exact changed-file scope.

## Protection pre-flight

Before edits, GitHub ruleset `21053541` (`VibeFlow main protection`) was `active` for `refs/heads/main`, with strict update-branch required checks `verify`, `foundation`, `sanitize`, `security-gate`; pull request and resolved-thread requirements; deletion/non-fast-forward blocking; and no bypass. Verified via `gh api repos/.../rulesets`. No mutation needed.

- main is exactly `b9f68c7c9062298e2be7d07cdd2c1d0976f5c13f` — confirmed via `git fetch origin main && git rev-parse origin/main`
- PR #16 is MERGED — verified via `gh pr view 16`
- No other M-012 branch/PR active — `gh pr list --state open` empty
- Ruleset still protects main with required checks `verify`, `foundation`, `sanitize`, `security-gate`

## Persistence

Migration `0004_project_authority.sql` creates `projects`:

```sql
CREATE TABLE projects (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations (id),
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT projects_name_non_empty CHECK (char_length(trim(name)) > 0)
);
CREATE INDEX projects_organization_id_idx ON projects (organization_id);
CREATE INDEX projects_organization_id_created_at_idx ON projects (organization_id, created_at DESC);
```

- Server-generated id via `newId()`
- Canonical Organization ownership via FK `organization_id -> organizations.id`
- Server-controlled timestamps via `now()`
- Integrity: FK, CHECK non-empty name, provider authority rejection
- Indexes for canonical tenant/project lookup
- Tenant-safe reads: `listProjectsForOrganization` scoped to `organization_id`
- Tenant-safe mutations: `createProject` requires org existence + membership via authz; `updateProject` requires project membership via authz
- No client/provider identifier ever establishes authority (`rejectProviderAuthority`)

`@vibeflow/persistence` README updated to reflect M-012.

## Authorization integration

`@vibeflow/authorization` extended:

- `RESOURCE_TYPES = ["organization", "project"]`
- `MembershipAuthority` now has `getProjectById(projectId): ProjectRow`
- `authorize()` dispatches to `authorizeProjectResource`
- `authorizeProjectResource`:
  - Gets `ProjectRow` by id, else `unknown_resource`
  - Gets its canonical `organizationId`, else `unknown_resource`
  - Requires `organization_memberships` row for `accountId` + `organizationId`, else `no_membership`
  - Returns `ALLOW` only when proven

This satisfies:

- same-tenant authorized read succeeds
- cross-tenant read fails `no_membership`
- cross-tenant mutation fails `no_membership`
- forged organization id fails (tenant resolved from persistence, not client claim)
- forged project ownership claim fails (same)
- random/unknown project UUID fails `unknown_resource`
- revoked/stale membership fails `no_membership`
- stale tenant info supplied by client ignored
- Project authorization uses canonical persistence
- authoritative audit failure converts an otherwise-valid allow to `audit_unavailable`

README updated to describe project authority, cross-tenant fail closed, no external engine.

## Project service boundary

New package `@vibeflow/project`:

- `ProjectService` with `tenants: TenantRepository`, `projects: ProjectRepository`, `authz: TenantAuthorizationService`
- Methods:
  - `createProject({ accountId, organizationId, name })`: validates UUIDs, authorizes against `organization` resource `create`, ensures org exists, then creates project with server id/timestamps
  - `getProject({ accountId, projectId })`: authorizes `project` read, then returns row; failures are `ProjectNotFoundError` or `ProjectAuthorizationError` (both fail closed)
  - `listProjects({ accountId, organizationId })`: authorizes org read, then lists scoped projects
  - `updateProject({ accountId, projectId, name })`: authorizes project update, then updates name + `updatedAt`

- Server owns authoritative IDs, tenant association, timestamps, security context.
- Does not expose delete/archive/lifecycle beyond M-012; does not implement Artifact, bindings, etc.
- Errors: `ProjectInputError`, `ProjectNotFoundError`, `ProjectAuthorizationError`

## Audit integration

`@vibeflow/audit` `recordAuthorizationDecision`:

- For `organization` type: looks up `organizations` table for `organization_id`
- For `project` type: `SELECT organization_id FROM projects WHERE id = $1` → sets `organization_id` for tenant-scoped audit
- Actor, tenant, project resource identity all server-resolved; metadata cannot override authority keys
- Database failures during canonical Organization/Project scope resolution propagate; they are not silently converted to `organizationId = null`
- Because authorization requires durable audit for an allow, such a failure produces `DENY / audit_unavailable`
- Secret handling preserved: `sanitizeAuditMetadata` omits secret-named keys, redacts secret-looking values
- Reads fail closed across tenant/account boundaries; `UPDATE/DELETE` on `audit_events` rejected by trigger

## API / service boundary

Minimal coherent surface: create, read, list, update (name). No delete/archive, no Artifact, no bindings, no workspace provisioning, no UI.

## Testing

Unit:

- `decision.test.ts` 13/13 PASS after adding project type
- `authority.test.ts` 5 PASS
- `metadata.test.ts` 4/4 PASS

Contract:

- `test_m008...` 7 PASS
- `test_m009...` 6 PASS
- `test_m010...` 8 PASS (updated README expectation)
- `test_m011...` 8 PASS
- `test_m012_project.py` 9 PASS

Live PostgreSQL (requires DATABASE_URL, skipped locally, must run in CI exact-head):

- `packages/persistence/src/project.live.test.ts` 8 cases: canonical creation, ownership, FK forged org fail, tenant-safe list scoped, random UUID fail, tenant-safe mutation timestamps, indexes, provider authority rejection
- `packages/authorization/src/project.live.test.ts` 10+ cases: same-tenant read success, cross-tenant read/mutation fail, forged org/actor, unknown UUID, revoked membership, canonical persistence, non-member, unauthenticated malformed
- `packages/project/src/project.live.test.ts` 11 cases: same plus stale tenant, audit scoping, tenant-safe list, etc.
- `packages/audit/src/project-scope.live.test.ts` 1 case: forced canonical Project audit-scope query failure must return `audit_unavailable` and persist no false `allowed` Project audit row

Foundation CI supplies `postgres:18.4` via `DATABASE_URL`/`VIBEFLOW_DATABASE_URL`; `pnpm run check` executes all package Vitest suites, and `run-m012-project-integration.py` executes the persistence/authorization/project suites explicitly.

Local checks:

- `pnpm install --no-frozen-lockfile` — PASS (lock updated for new dep)
- `pnpm run typecheck` — 16/16 PASS
- `pnpm run test` — 16/16 PASS (live skipped)
- `python3 tests/contract/*.py` — PASS
- `python3 scripts/validate-m004-foundation.py` — PASS
- `python3 scripts/validate-master-contracts.py` — PASS
- `python3 scripts/validate-m006-security-gates.py` — PASS
- `python3 scripts/validate-m007-local-dev.py` — PASS
- `git diff --check` — PASS

## Evidence bundle

- `evidence/missions/M-012/PROJECT_AUTHORITY.json` machine-readable (canonical)
- `evidence/missions/M-012/PROJECT_AUTHORITY.md` human-readable

## Capability ledger

- `VF-IAM-010 Project ownership` NOT_STARTED → IMPLEMENTED
- `VF-PRJ-005 Unbound/empty Project` NOT_STARTED → IMPLEMENTED
- `VF-PRJ-015 Project` NOT_STARTED → IMPLEMENTED
- `VF-PRJ-016 Project Profile` remains NOT_STARTED (only name in M-012, full profile beyond)
- Others remain NOT_STARTED

Trace file `CAPABILITY_CONTRACT_TRACE.csv` also updated for those three.

## Known limitations / explicitly deferred

- No Artifact/ArtifactRelation (M-013)
- No imports/templates lifecycle (M-014)
- No full Project lifecycle E2E beyond M-012 (M-015)
- No provider bindings: AgentBinding, ModelBinding, WorkspaceBinding, RepositoryBinding, DataBinding, ObjectStorageBinding, DeploymentBinding (M-016+)
- No OpenHands integration, workspace provisioning, GitHub repo management, Monaco/web IDE, task/execution engine, Temporal, deployment, billing, collaboration roles/groups, enterprise SSO/SCIM, broad external authorization engine, later mobile/UI
- Project update only supports name; no state machine beyond existence
- Audit for project is via authorization audit; no dedicated Project audit catalog beyond
- PostgreSQL live not executed locally; CI must run exact-head

## Overclaim check

M-012 is REVIEW, not DONE. Capabilities are IMPLEMENTED, not VERIFIED/COMPLETE. PostgreSQL live not claimed locally. M-013+ remain LOCKED.
