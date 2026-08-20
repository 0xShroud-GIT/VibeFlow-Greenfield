# Active Mission

**Mission:** M-013 — Implement Artifact/ArtifactRelation

**Status:** REVIEW

**Phase:** 3 — Project Authority

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-013)

M-001 through M-012 are accepted and `DONE`. M-013 is the sole active mission
in `REVIEW`. M-014 and all later missions remain `LOCKED` and remain
required for V1.

## M-013 scope

Implement the authoritative Artifact and ArtifactRelation resource layer within
Project Authority. Artifact authority must remain rooted in canonical Project
ownership and trusted server-side VibeFlow state, with tenant/resource
authorization and durable audit preserving the accepted M-010 through M-012
fail-closed boundaries. Relationships must be established from canonical
server-side resources rather than client/provider ownership claims.

Do not implement imports/templates lifecycle (M-014), full Project lifecycle E2E
(M-015), provider bindings (M-016+), workspace/repository provisioning, agent or
model integrations, deployment, task/execution, mobile/UI, or other later
mission scope.
