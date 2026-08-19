# M-011 — Audit baseline evidence

## Identity and state

- Starting authoritative `main`: `3800772ec963a4776f1c84881f93455dc7bf4a48`
- M-010 closure commit: `179312a89251165c16975ee48273b05b60fc3d9b`
- M-011 implementation commit: `7dbb75cd9a140e164a53c2a965673c11be1e795c`
- Arena branch: `arena/01a01b69-vibeflow-greenfield` (session-fixed)
- Final mission state: `M-001..M-010 DONE`, `M-011 REVIEW`, `M-012..M-151 LOCKED`
- Capability: `VF-IAM-004 Audit Event Ledger` → `IMPLEMENTED`, not
  `VERIFIED`/`COMPLETE`

The machine-readable evidence in `AUDIT_BASELINE.json` is canonical. The final
PR head and exact-head Actions runs are recorded in the PR/final handoff because
a commit cannot contain its own SHA.

## Protection pre-flight

Before repository edits, GitHub ruleset `21053541` (`VibeFlow main protection`)
was already `active` for `refs/heads/main`, with strict update-branch required
checks `verify`, `foundation`, `sanitize`, and `security-gate`; pull request and
resolved-thread requirements; deletion/non-fast-forward blocking; and no current
user bypass. The legacy branch-protection endpoint returned integration HTTP
403, while the repository-ruleset endpoint supplied complete readable proof.
No ruleset mutation was necessary or claimed.

## Architecture and schema

`@vibeflow/audit` is separate from authentication, authorization, and
application logging. Migration `0003_audit_event_ledger.sql` creates durable
`audit_events` with server-generated UUID/time, canonical actor/subject Account
FKs, optional canonical Organization scope, normalized action/resource/outcome,
request correlation, source, and bounded safe JSON metadata.

Indexes support account-private and organization+account descending queries.
Pagination is stable on `(occurred_at DESC, id DESC)`. A PostgreSQL trigger
rejects ordinary `UPDATE`/`DELETE`, so history is append-only under ordinary
application operations. There is no generic client audit-create surface.

## Authentication/session behavior

PostgreSQL session triggers insert `session.created` and `session.revoked` in
the same transaction as Better Auth's session insert/delete. Failure of this
required write rolls back the session operation. Attributable invalid-credential
attempts produce `authentication.login_failed` scoped to a canonical subject
Account with no forged actor. Unknown-email attempts cannot be assigned a
canonical Account and are not promoted into authoritative account audit.
Passwords, cookies, session tokens, and submitted emails are not copied into
audit metadata.

## Authorization behavior

M-010 authorization uses a narrow injected recorder. Every registered
Organization decision records canonical actor, existing Organization/resource,
action, outcome, and deny reason. Unknown UUID resources remain account-scoped
rather than becoming tenant authority. If an allow's required audit write
fails, the authorization result becomes `audit_unavailable`; denials remain
fail closed.

Audit reads require the authenticated Account to equal the requested Account.
Organization-filtered reads additionally resolve current canonical membership.
Cross-account and cross-tenant reads fail closed. Organization-admin/role-wide
reads are intentionally absent until their authority exists.

## Secret and metadata controls

Metadata is plain bounded JSON only (depth, key, array, string, and 4096-byte
limits). Actor/account/tenant/organization/resource/time/event authority-shaped
keys are rejected. Secret-named fields are omitted and common credential-shaped
values are replaced with `[REDACTED]`. Typed narrow producers and no raw payload
dumping remain the primary defense.

## Local verification

Node `24.19.0`, pnpm `11.4.0`:

- `pnpm install --frozen-lockfile` — PASS
- `pnpm run check` — PASS
- M-011 contract — 8/8 PASS
- audit metadata unit — 4/4 PASS
- M-010 authorization unit regression — 13/13 PASS
- M-009 identity unit regression — 3/3 PASS
- typecheck/build — PASS
- `git diff --check` — PASS

No local `DATABASE_URL` exists. M-008/M-009/M-010/M-011 PostgreSQL suites were
explicitly **NOT EXECUTED** locally and are not claimed as passes. Protected
`Repository Foundation` supplies `postgres:18.4`; the explicit M-011 runner must
execute the 9-case live suite on the exact PR head.

## Limitations and exclusions

No Project/M-012 authority, roles/groups, enterprise IAM, SSO/SCIM, MFA breadth,
OpenFGA, grants/approvals, Temporal, gateway/protocol work, observability/SIEM,
analytics/activity feed, cryptographic non-repudiation, retention platform,
billing, or deployment was added. M-012 remains locked. M-011 remains `REVIEW`
and requires independent exact-head CI/review before `DONE`.
