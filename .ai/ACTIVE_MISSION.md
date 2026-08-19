# Active Mission

**Mission:** M-010 — Implement tenant/resource authorization

**Status:** REVIEW

**Phase:** 2 — Identity & Tenant Authority

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-010)

M-001 through M-009 are accepted and `DONE`. M-010 is the active mission in
`REVIEW`. M-011 and all later missions remain `LOCKED` and remain required for
V1.

## M-010 scope

Build the production tenant/resource authorization boundary on M-008 canonical
Account/Organization/Membership persistence and M-009 authenticated Account
identity: a server-side, deny-by-default typed authorization decision boundary
that resolves Organization membership and resource relationships from canonical
VibeFlow persistence on every decision and never trusts client/provider org
ids, roles, permissions, ownership claims, or resource relationships. P0
negative tests must prove IDOR and cross-tenant reads and mutations fail
closed.

Do not implement Project persistence/lifecycle (M-012), audit baseline (M-011),
roles/group binding, enterprise SSO/SCIM, MFA, OAuth breadth, ConnectionGrant,
approvals, provider policy, or an external authorization engine for this slice.
Authentication proves only Account identity (M-009); it never implicitly
authorizes an Organization/resource.
