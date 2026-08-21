# Active Mission

**Mission:** M-016 — Implement binding resource family

**Status:** READY

**Phase:** 4 — Provider Bindings

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-016)

M-001 through M-015 are accepted and `DONE`. M-016 is the sole active mission
and is `READY` for implementation. M-017 and all later missions remain
`LOCKED` and remain required for V1.

## M-016 scope

Authoritative mission scope:
- Agent/Model/Workspace/Repo/Data/Storage/Deployment binding resource family
- preserve VibeFlow-owned binding metadata/policy while external providers remain authoritative for their runtimes, repositories, data and objects
- canonical binding resources: AgentBinding, ModelBinding, WorkspaceBinding, RepositoryBinding, DeploymentBinding, DataBinding and ObjectStorageBinding
- preserve canonical Project/Organization authority and tenant isolation across every binding

Implementation guardrails:
- external/provider IDs are references and never become VibeFlow Project/Organization authority
- M-017 provider capability discovery remains a separate locked mission
- M-020+ Connection, ConnectionGrant and SecretRef broker/grant semantics remain later scope
- provider-specific adapters, workspace provisioning, task/execution, deployment execution, UI/mobile/Canvas and later mission scope must not be inferred from this READY pointer
- exact implementation and acceptance semantics must be derived from the Master Build System before code changes begin

At implementation start, transition M-016 from `READY` to `IN_PROGRESS` in
the authoritative mission files and update the synchronized human-facing
mission pointers in the same change.
