# M-015 — Project Lifecycle E2E (Profile, CapabilityProfile, Overview)

**Status:** REVIEW
**Phase:** 3 — Project Authority
**Branch:** `arena/01a02144-vibeflow-greenfield`
**Starting main:** `55cec7b93bd2f0f1cb41e7707a986eb9ff4792ef`

## Authority Model

Canonical authority remains:

```
Account
  -> Organization membership
  -> Project
  -> Artifact / ArtifactRelation
```

ProjectProfile and ProjectCapabilityProfile are **subordinate Project-domain state**, not new canonical authority roots.
ProjectOverview is a **read model / projection**, not a canonical resource.

## Persistence Schema

### `project_profiles`

| Column | Type | Notes |
|--------|------|-------|
| `project_id` | uuid PK | FK → projects(id) |
| `description` | text? | Nullable, max 5000 chars (implementation constant) |
| `cover_artifact_id` | uuid? | Nullable; composite FK (project_id, cover_artifact_id) → artifacts(project_id, id) |
| `version` | integer | Non-negative, starts at 1 after first insert |
| `created_at` | timestamptz | Server-controlled |
| `updated_at` | timestamptz | Server-controlled |

Database-level backstops:
- Composite FK ensures cover Artifact belongs to the **same canonical Project**
- One profile per Project (PK is project_id)

### `project_capabilities`

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | Server-generated |
| `project_id` | uuid | FK → projects(id) |
| `capability_key` | text | Open grammar: `^[a-z][a-z0-9]*(/[a-z][a-z0-9]*)+$`, max 200 chars |
| `version` | integer | Set-level EPOCH version, non-negative |
| `created_at` | timestamptz | Server-controlled |

Database-level backstops:
- UNIQUE (project_id, capability_key)
- Regex CHECK constraint on capability_key

## Project Profile (VF-PRJ-016 — IN_PROGRESS)

Implemented subset:
- `Project.name` remains the title/name authority
- Optional `description` (max 5000 chars)
- Optional `coverArtifactId` referencing a canonical same-Project Artifact
- Version-based optimistic concurrency with `expectedVersion`
- Cover Artifact same-Project enforcement at the database level (composite FK)

**Explicitly deferred (M-117+):**
- Sharing settings
- Collaboration/roles
- Public project state

### API

```
getProjectProfile({ accountId, projectId })
updateProjectProfile({ accountId, projectId, expectedVersion, description?, coverArtifactId? })
```

## ProjectCapabilityProfile (VF-PRJ-014 — IMPLEMENTED)

- Provider-neutral capability/trait manifest
- Open token grammar (not a closed taxonomy)
- Atomic replacement in one transaction
- Optimistic concurrency via expectedVersion
- Deterministic deduplication and sort ordering

### API

```
getProjectCapabilityProfile({ accountId, projectId })
replaceProjectCapabilityProfile({ accountId, projectId, expectedVersion, capabilities })
```

## ProjectOverview (Read Model)

- Authorizes Project read by opaque id first
- Returns: Project identity, Profile, CapabilityProfile, Artifacts, ArtifactRelations, import/clone provenance (when present)
- Does NOT fabricate: AgentBinding, ModelBinding, WorkspaceBinding, RepositoryBinding, DeploymentBinding, provider health, Task/Execution, Release, or Repository state

## No Project State Machine Added

The Master Build System defines no Project state machine (states: ACTIVE/ARCHIVED/DELETED). M-015 does not add one.

## No New Canonical Resource

ProjectProfile, ProjectCapabilityProfile, ProjectOverview, ArtifactType, ProjectLifecycle, Import, Template, and Clone are all subordinate Project-domain implementations, not new canonical authority roots.

## No New Event Family

M-015 does not invent `project.deleted`, `project.archived`, `project.profile_updated`, `project.capabilities_updated`, `artifact.*`, `import.*`, `clone.*`, or `template.*` events.

## Capability Ledger Transitions

| VF-ID | Capability | Previous | Current |
|-------|-----------|----------|---------|
| VF-PRJ-014 | ProjectCapabilityProfile | NOT_STARTED | **IMPLEMENTED** |
| VF-PRJ-016 | Project Profile | NOT_STARTED | **IN_PROGRESS** |

Capabilities deliberately NOT advanced:

- VF-PRJ-001 Artifact Registry — NOT_STARTED
- VF-PRJ-002 ArtifactVersion — NOT_STARTED
- VF-PRJ-003 ArtifactGraph — NOT_STARTED
- VF-PRJ-006 Project Collection/Labels — NOT_STARTED
- VF-PRJ-008 Repository Import Adapter — NOT_STARTED
- VF-PRJ-009 Builder Migration Adapter — NOT_STARTED
- VF-PRJ-010 Design Import Adapter — NOT_STARTED
- VF-PRJ-011 Deployment-to-Repo Helper — NOT_STARTED
- VF-PRJ-012 RepositoryBinding import — NOT_STARTED
- VF-PRJ-017 Typed Artifact Graph — **NOT_STARTED** (VF-PRJ-017 boundary preserved)

Existing IMPLEMENTED statuses unchanged: VF-PRJ-004, VF-PRJ-005, VF-PRJ-007, VF-PRJ-013, VF-PRJ-015.

## Test Results (TBD until CI run)

| Suite | Type | Tests |
|-------|------|-------|
| `profile.live.test.ts` | Live PostgreSQL 18.4 | 10 |
| `capability-profile.live.test.ts` | Live PostgreSQL 18.4 | 10 |
| `overview.live.test.ts` | Live PostgreSQL 18.4 | 3 |
| `exports.test.ts` (M-015 sections) | Unit | 5 |
| `test_m015_project_lifecycle.py` | Contract | 16 |

Retained suites from M-012, M-013, M-014 remain green.

## Known Limitations

- Project Profile sharing settings deferred to M-117+ (Collaboration phase)
- ProjectCapabilityProfile is provider-neutral; provider capability discovery is M-016+
- ProjectOverview does not include future resources (bindings, tasks, executions)
- No durable event emitted for profile/capability changes (M-026 owns event infrastructure)
- No provider binding, collaboration, deletion, or archive functionality

## Explicit Non-Goals

- Project deletion/archive/soft-delete
- Sharing/invitations/collaboration
- Provider bindings (Agent, Model, Workspace, Repository, Deployment, Data, Storage)
- Provider capability discovery
- GitHub/Bitbucket/Vercel/Figma integrations
- Workspace provisioning
- Tasks/Executions/Temporal
- Event/outbox/replay infrastructure
- Mobile/web UI

## Files Changed

- `migrations/0007_project_lifecycle.sql`
- `packages/persistence/src/schema.ts`
- `packages/persistence/src/repositories.ts`
- `packages/persistence/src/errors.ts`
- `packages/persistence/src/ids.ts`
- `packages/persistence/src/index.ts`
- `packages/persistence/src/lifecycle-repository.ts`
- `packages/project/src/profile-service.ts`
- `packages/project/src/capability-profile-service.ts`
- `packages/project/src/overview-service.ts`
- `packages/project/src/errors.ts`
- `packages/project/src/index.ts`
- `packages/project/src/exports.test.ts`
- `packages/project/src/import-service.ts`
- `packages/project/src/clone-service.ts`
- `scripts/run-m015-lifecycle-integration.py`
- `tests/contract/test_m015_project_lifecycle.py`
- `evidence/missions/M-015/PROJECT_LIFECYCLE_E2E.json`
- `evidence/missions/M-015/PROJECT_LIFECYCLE_E2E.md`
- Master build system files

## Authorization Ordering Proof

For all M-015 operations:
1. Validate syntax only
2. Authorize opaque resource id first (before loading canonical details)
3. Only after authorization, load canonical rows
4. Derive Project/Organization scope from persistence
5. Perform same-Project/same-tenant checks
6. Mutate transactionally
7. Return canonical state

Cross-tenant probes fail closed without revealing existence.

## Handoff

M-015 status: **REVIEW** (not DONE).
M-016+ status: **LOCKED**.
Pull request is open, unmerged, not self-approved.