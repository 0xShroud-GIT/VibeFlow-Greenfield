# M-010 — Tenant/resource authorization evidence

## Identity and acceptance boundary

| Field | Value |
| --- | --- |
| Starting `origin/main` | `6c1b74fa9eba410823a7f2e5608e777ee3e30761` (M-009 merge) |
| Arena session branch | `arena/01a01a93-vibeflow-greenfield` |
| Mission state at branch head | `M-001..M-009 DONE`; `M-010 REVIEW`; `M-011..M-151 LOCKED` |
| ADR | Not required — no architecture/resource/state/event change |

Arena binds this session to `arena/01a01a93-vibeflow-greenfield`; it cannot use
a different branch name. Acceptance must bind to the exact final pushed head
reported in the PR/handoff. Any later push invalidates an earlier exact-head
review. M-010 is never marked `DONE` on the builder branch and must not be
merged by the builder.

## What was implemented

`@vibeflow/authorization` is the M-010 server-side tenant/resource authorization
boundary, built on M-008 canonical Account/Organization/Membership persistence
and M-009 authenticated Account identity.

- **Authentication proves only Account.** M-009's `SessionValidation` yields a
  canonical `accountId` and nothing else. The authorization boundary consumes
  that proof as a precondition and never extends it into a grant.
- **Authorization is server-side and deny-by-default.** `authorize()` always
  returns an explicit `AuthorizationDecision`; every malformed, unknown, or
  unauthorized request is an explicit deny with a typed `DenyReason`
  (`malformed_request`, `invalid_identifier`, `unknown_resource_type`,
  `unknown_action`, `unknown_resource`, `no_membership`).
- **Canonical persistence is authoritative.** Membership and resource
  relationships are resolved from `organization_memberships` (via
  `TenantRepository.getMembership` / `getOrganizationById`) on every decision.
  Client/provider-supplied organization ids, roles, permissions, ownership
  claims, and resource relationships are never trusted.
- **Typed, resource-type-agnostic boundary.** `ResourceRef { type, id }`,
  `AuthorizationRequest { accountId, action, resource }`, registered
  resource-type and action tokens. Only `organization` is registered in M-010
  (its tenant is the organization itself). Later resources (Project, Task,
  Connection, Workspace, repository, deployment, ...) register their own tenant
  resolution in their owning mission; until then they are denied by default.
- **Canonical UUIDs only.** `isUuid` (exported from `@vibeflow/persistence`)
  rejects client/provider/scoped identifiers.

**No external authorization engine** is added. OpenFGA and peers remain
candidate/reference only; this slice does not need one, so none is introduced.

## Coverage (mapped to requirements)

| Requirement | Behavior |
| --- | --- |
| allowed canonical membership | member of Org A read Org A → `ALLOW` |
| no membership | account with no membership → `no_membership` |
| wrong tenant | member of A, resource in B → `no_membership` |
| forged/swapped org/resource id | non-existent id → `unknown_resource`; real-but-foreign id → `no_membership` |
| deleted/stale membership | membership row deleted → `no_membership` |
| malformed/unknown resource/action | empty/slug ids → `malformed_request`/`invalid_identifier`; unknown type/action → `unknown_resource_type`/`unknown_action` |
| cross-tenant access | read and create/update/delete on a foreign tenant → deny (P0 IDOR) |

## Capability status updates (ledger + trace + YAML)

- `VF-IAM-010` Project ownership — `NOT_STARTED` (requires canonical Project
  authority in M-012; explicitly **not** claimed).
- `VF-IAM-011` Resource policy — `IN_PROGRESS` (typed deny-by-default tenant
  isolation boundary implemented and negative-tested; full resource policy
  pending).
- `VF-IAM-012` Role/Group binding — `NOT_STARTED` (no roles/groups).
- `VF-IAM-016` Organization + Membership — `IN_PROGRESS` (unchanged; it is the
  canonical authority this boundary relies on).

## Tests

Always-on (no database):

- `packages/authorization/src/decision.test.ts` — 12 tests: registered tokens,
  malformed/unknown resource/action deny, canonical-UUID rejection, allowed
  membership, no-membership, cross-tenant, forged id, service-level unknown
  type/action.

Live PostgreSQL (`VIBEFLOW_DATABASE_URL` or `DATABASE_URL`):

- `packages/authorization/src/tenant.live.test.ts` — 9 tests against PostgreSQL
  18.4 covering allowed membership, no membership, cross-tenant read and
  mutation (IDOR) denial, forged/swapped ids, deleted/stale membership, and
  malformed/unknown inputs.

Contract:

- `tests/contract/test_m010_authz.py` — 8 tests asserting the boundary shape,
  deny-by-default posture, canonical-UUID enforcement, no external engine, no
  overclaiming of later missions, and CI wiring.

The local Arena workspace has no PostgreSQL, so the live suite is skipped here
(an explicit non-verification notice, matching M-008/M-009). In CI the
`run-m010-authz-integration.py` runner (invoked by `pnpm run check` in the
repository-foundation workflow, which supplies PostgreSQL 18.4 via
`DATABASE_URL`) runs the M-010 live suite against PostgreSQL. No workflow file
is edited by M-010; the builder GitHub App lacks `workflows` permission, and the
runner needs no workflow change.
