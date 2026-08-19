# Active Mission

**Mission:** M-009 — Implement authentication/session flows

**Status:** REVIEW

**Phase:** 2 — Identity & Tenant Authority

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-009)

M-001 through M-008 are accepted and `DONE`. M-009 is the active mission in
`REVIEW`. M-010 and all later missions remain `LOCKED` and remain required for
V1.

## M-009 scope

Implement VibeFlow authentication/session mechanics only: canonical Account
linkage, session creation/validation/revocation, secure session persistence,
logout, and negative/replay/stale-session tests. Authentication proves identity;
it does not grant tenant, project, or resource authority.

Do not implement authorization/roles/OpenFGA (M-010), audit (M-011), projects
(M-012), enterprise SSO/SCIM, broad MFA/federated login, or UI/mobile work.
