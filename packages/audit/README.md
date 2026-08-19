# @vibeflow/audit

M-011's VibeFlow-owned audit baseline is durable, append-only PostgreSQL security
and control-plane evidence. It is not an application log or raw payload store.

Narrow server integrations record canonical account/session/organization and
authorization facts. There is no generic client-facing authoritative-write API.
Metadata is bounded structured JSON: authority-shaped fields are rejected,
secret-named fields are omitted, and secret-looking values are redacted.
Required session audit writes share the session transaction; authorization
allows fail closed to `audit_unavailable` if their required audit write fails.

Baseline reads are account-private. Organization-filtered reads also resolve the
requester's current canonical membership. Cross-account and cross-tenant reads
fail closed. Pagination is stable by `(occurred_at DESC, id DESC)`.

This baseline does not implement activity feeds, analytics, OpenTelemetry/SIEM
export, admin roles, Project authority (M-012), cryptographic non-repudiation,
or a generic observability platform.
