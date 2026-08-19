# Active Mission

**Mission:** M-012 — Implement Project authority

**Status:** READY

**Phase:** 3 — Project Authority

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-012)

M-001 through M-011 are accepted and `DONE`. M-012 is the sole ready mission.
M-013 and all later missions remain `LOCKED` and remain required for V1.

## M-012 scope

Implement the smallest production-direction authoritative Project resource
required by the Greenfield architecture: server-generated Project identity,
canonical Organization ownership, server-controlled timestamps, integrity and
FK constraints, indexes for canonical tenant/project lookup, tenant-safe reads
and tenant-safe mutations. Project authority must derive from trusted
server-side VibeFlow state. All authorization must pass through the existing
M-010 authorization boundary extended to make Project a first-class protected
resource. Cross-tenant Project access must fail closed. Revoked/stale
membership must not retain Project access. Audit integration must use canonical
server-side actor, tenant, and Project resource identity.

Do not implement Artifact/ArtifactRelation (M-013), imports/templates lifecycle
(M-014), full Project lifecycle E2E beyond M-012, provider bindings,
AgentBinding, ModelBinding, WorkspaceBinding, RepositoryBinding, DataBinding,
ObjectStorageBinding, DeploymentBinding, OpenHands integration, workspace
provisioning, GitHub repo management, Monaco/web IDE, task/execution engine,
Temporal, deployment, billing, collaboration roles/groups, enterprise SSO/SCIM,
broad external authorization engine, or later mobile/UI work.
