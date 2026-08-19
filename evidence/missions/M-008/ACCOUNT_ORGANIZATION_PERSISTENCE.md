# M-008 — Account/Organization persistence evidence

## Identity and acceptance boundary

| Field | Value |
| --- | --- |
| Starting `origin/main` | `5b9ca460d300abdc626aa581d1bf2d6c533a0fd1` |
| Arena session branch | `arena/01a018ab-vibeflow-greenfield` |
| Mission state at branch head | `M-001..M-007 DONE`; `M-008 REVIEW`; `M-009..M-151 LOCKED` |
| ADR | Not required — no architecture/resource/state/event change |

Arena binds this session to `arena/01a018ab-vibeflow-greenfield`; it cannot use
a different branch name. Acceptance must bind to the exact final pushed head
reported in the PR/handoff. Any later push invalidates an earlier exact-head
review. M-008 is never marked `DONE` on the builder branch and must not be
merged by the builder.

## What was implemented

`@vibeflow/persistence` is the VibeFlow-owned control-plane repository for:

- **Account** — product identity (display name + timestamps). Not a provider account.
- **Organization** — tenant boundary. `kind` is `personal` or `standard`.
- **organization_memberships** — relation only. Unique `(organization_id, account_id)`.
  No roles, grants, OpenFGA tuples, or authorization semantics.

Committed SQL `migrations/0001_account_organization.sql` is the migration
authority. `applyCommittedSqlMigrations` records applied files in
`vibeflow_schema_migrations` and is idempotent.

Tenant relationships are canonical server-side rows. `rejectProviderAuthority`
rejects `providerId` / `externalId` / `clientTenantId` and related keys before
any insert. Repository IDs must be UUIDs. There is no unscoped membership catalog.

## Harvest / runtime pins (exact)

Inspected installed versions and official 0.45.2-applicable sources:

| Package | Pin | License | Source |
| --- | --- | --- | --- |
| `drizzle-orm` | `0.45.2` | Apache-2.0 | npm + `github.com/drizzle-team/drizzle-orm` tag `0.45.2` |
| `pg` | `8.23.0` | MIT | npm + `github.com/brianc/node-postgres` |
| `@types/pg` | `8.23.1` | MIT | npm / DefinitelyTyped |

Official `drizzle-orm@0.45.2` node-postgres driver (`drizzle-orm/node-postgres`)
accepts a `pg.Pool` and optional `{ schema }`. Peer range is `pg: '>=8'`.
Query failures are wrapped as `DrizzleQueryError` with the driver error on
`cause`; `mapDatabaseError` unwraps PostgreSQL `23505` / `23503`.

**Not installed:** `drizzle-kit`. There is no `drizzle-kit@0.45.2` release
(latest stable kit is `0.31.10`). Kit pulls `esbuild` install scripts, which
are deny-by-default (`strictDepBuilds: true`). Committed SQL is the migration
authority.

**Not selected:** `postgres` (postgres.js) `3.4.9` is Unlicense, outside the
green license token set (MIT, Apache-2.0, BSD, ISC, PostgreSQL).

H-011 `package_coordinates` now record `drizzle-orm` (production), `pg`
(production), and `@types/pg` (development). Harvest entry count remains 35.

TypeScript 6.0.3 with repo-wide `skipLibCheck: false` cannot typecheck
drizzle-orm 0.45.2 `.d.ts` files that import optional driver types. The
persistence package sets `"skipLibCheck": true` only.

## Tests

Always-on (no database):

- `packages/persistence/src/authority.test.ts` — no provider/role/session
  columns; provider IDs rejected; UUID boundary; drizzle-wrapped SQLSTATE map
- `packages/persistence/src/migrate.test.ts` — committed SQL shape, FKs, unique
  membership, no provider/authz columns
- `tests/contract/test_m008_account_org_persistence.py` — contract surface

Live PostgreSQL (`VIBEFLOW_DATABASE_URL` or `DATABASE_URL`):

- `packages/persistence/src/persistence.live.test.ts` — create/read account and
  org (including personal), membership + duplicate rejection, FK integrity,
  cross-org listing isolation, provider/unscoped ID rejection, personal-org
  transaction, migration idempotency

Those live cases are `describe.skipIf` when no connection string is present.
This Arena workspace and the retained CI foundation have no PostgreSQL 18
service. Arena cannot write `.github/workflows/**` to add one. Live durability
is therefore **not claimed** from this environment.

Retained mutation suites after successor-package / ledger reconstruction:

- M-002 48 OK
- M-004 82 OK (`strip_later_packages`)
- M-005 92 OK (historical snapshot strips later package manifests)
- M-006 41 OK (durable external direct deps = 7)
- M-007 90 OK (historical active snapshot restores IAM-006/016 to NOT_STARTED)

## Capability ledger

Only rows directly proven by this mission:

- `VF-IAM-006` VibeFlow Account Identity → `IN_PROGRESS`
- `VF-IAM-016` Organization + Membership → `IN_PROGRESS`

Not claimed: `VERIFIED`, `IMPLEMENTED`, `COMPLETE`. AuthN/AuthZ tenant-isolation
plus audit evidence remain later missions.

Unchanged: `VF-IAM-005` session, `VF-IAM-010+` project/policy/roles, `VF-ENV-005`.

## Explicit non-goals

This mission does **not** implement:

- authentication / sessions / Better Auth (M-009)
- authorization roles, OpenFGA, policy (M-010)
- audit ledger (M-011)
- Project persistence (M-012)
- UI / mobile / Fastify control-plane HTTP
- billing, deletion orchestration, enterprise roles, provider identities

Membership persistence is a relation. It is not authorization.
