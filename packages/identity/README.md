# `@vibeflow/identity`

M-009's VibeFlow Identity boundary wraps ratified `better-auth@1.6.30` email/
password and session mechanics. It is server-only product code, not a browser,
mobile, provider, authorization, or OpenFGA boundary.

## Authority split

- Better Auth owns credential hashing, credential records, session tokens, and
  secure cookie mechanics.
- VibeFlow owns the durable `Account` resource and the server-side
  `identity_users.vibeflow_account_id` foreign-key link to that Account. A
  PostgreSQL `BEFORE INSERT` trigger creates the Account inside Better Auth's
  Kysely-backed signup transaction, so a later credential/session failure rolls
  both records back rather than leaving an orphan Account.
- A validated session yields **identity proof only**: a canonical Account ID,
  session ID, expiry, and freshness. It never yields an Organization, Project,
  role, grant, policy, or permission.

The public API deliberately exposes secure `Set-Cookie` values for an HTTP
adapter to return, but does not persist or expose a session token as ordinary
product state. Session cookie caching is disabled so revocation is checked
against PostgreSQL.

## Scope limits

M-009 does not implement tenant/resource authorization or roles (M-010),
OpenFGA, audit (M-011), Project authority (M-012), enterprise SSO/SCIM,
federated login, MFA, mobile UI, or an HTTP route surface.

## Verification

`session.live.test.ts` requires `DATABASE_URL` or
`VIBEFLOW_DATABASE_URL` and exercises Better Auth against PostgreSQL. In CI a
missing database URL fails rather than silently treating skipped integration
coverage as verification. The Foundation workflow supplies PostgreSQL 18.4.
