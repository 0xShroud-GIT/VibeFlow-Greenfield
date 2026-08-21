# Active Mission

**Mission:** M-015 — Implement project lifecycle E2E

**Status:** REVIEW

**Phase:** 3 — Project Authority

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-015)

M-001 through M-014 are accepted and `DONE`. M-015 is the sole active mission
and implementation is complete. M-016 and all later missions remain
`LOCKED` and remain required for V1.

## M-015 scope

Implemented:
- Project Profile subordinate state (VF-PRJ-016 IN_PROGRESS)
- ProjectCapabilityProfile (VF-PRJ-014 IMPLEMENTED), with independent durable set epoch
- ProjectOverview read model from one PostgreSQL snapshot
- Creation-mode E2E parity (empty, archive-import, clone)
- Full authorization/IDOR ordering compliance
- Optimistic concurrency and transactional semantics
- PostgreSQL integrity backstops

Explicitly out of scope:
- M-016+ provider bindings
- GitHub/Bitbucket/Vercel/Figma provider implementations
- workspace provisioning
- agent/model integrations
- execution/task/deployment
- UI/mobile/Canvas
- Collaboration/sharing (M-117+)
- later mission scope

## Current validation pointer

Historical mission evidence remains under `evidence/missions/M-014/` and
`evidence/missions/M-015/`; it records the candidate state when authored and is
not current-head CI proof.

Current post-audit remediation evidence:
`evidence/audits/2026-08-21_POST_AUDIT_RESIDUAL_REMEDIATION.md`.

Before any M-015 acceptance transition, verify the required GitHub Actions runs
for the **exact** candidate/main SHA. `CHECKPOINT.md` contains the handoff rule.
