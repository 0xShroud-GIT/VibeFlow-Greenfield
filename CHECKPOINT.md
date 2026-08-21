# VibeFlow Checkpoint

Updated: 2026-08-21
Canonical source inspected: `main` @ `cbc7767b9e9cf389f8bff77bf86013ddec62ae19`

## Current phase

Phase 3 — Project Authority.

`M-001` through `M-014` are `DONE` in the authoritative mission DAG.

`M-015 — Implement project lifecycle E2E` is the sole active mission and remains `REVIEW` in `master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml`.

M-015 implementation was merged to `main` by PR #24 at merge commit `f337c1428b91f0c1ab58dce2f419ad89b68f393e`. That merge does **not** by itself change the mission from `REVIEW` to `DONE`. `M-016` and later work remains locked until the required M-015 review/acceptance transition occurs.

## M-015 implemented scope

- Project Profile subordinate state
- ProjectCapabilityProfile
- ProjectOverview read model
- empty/archive-import/clone creation-mode parity
- authorization/IDOR ordering
- optimistic concurrency and transactional semantics
- PostgreSQL integrity backstops

Explicitly not implemented by M-015: provider bindings, workspace provisioning, agent/model integration, execution/task/deployment, UI/mobile/Canvas, collaboration/sharing, project deletion/archive state, and later-mission features.

## Validation state

The retained M-015 evidence records:

- `packages/project/src/exports.test.ts` M-015 unit sections: PASS (6)
- `tests/contract/test_m015_project_lifecycle.py`: PASS (18)
- PostgreSQL live M-015 suites: NOT RUN in that evidence because local PostgreSQL was unavailable

Do not describe the full repository as freshly green from this checkpoint alone. A fresh broad validation should run in the canonical development environment before accepting M-015.

## Next action

1. Independently review the merged M-015 implementation against its mission contract.
2. Run the required validation, including PostgreSQL-backed integration/live gates with `DATABASE_URL` where required.
3. Fix defects within M-015 scope only.
4. If acceptance gates pass, transition M-015 through the repository's established mission protocol and update this checkpoint in the same change.
5. Only then consider the next unlocked mission. Do not start M-016 while M-015 remains `REVIEW`.

## Important architecture boundaries

- Account → Organization membership → Project → Artifact/ArtifactRelation remains canonical Project authority.
- ProjectProfile and ProjectCapabilityProfile are subordinate Project-domain state, not new canonical roots.
- ProjectOverview is a projection/read model.
- No Project state machine or new event family was introduced by M-015.
- Provider-specific concerns must remain outside Project authority.

## Repository context note

The repository intentionally retains `master-build-system/`, `.ai/` compatibility/index files, `reference/`, mission `evidence/`, placeholder surfaces, and validators because current code generation/verification contracts reference them. They are not all startup context for an AI agent.

The normal startup path is only:

1. `AGENTS.md`
2. `CHECKPOINT.md`
3. relevant code/tests

Load deeper authority or evidence only when the task requires it.
