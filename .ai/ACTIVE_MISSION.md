# Active Mission

**Mission:** M-014 — Implement imports/templates lifecycle

**Status:** REVIEW

**Phase:** 3 — Project Authority

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-014)

M-001 through M-013 are accepted and `DONE`. M-014 is the sole active mission
and is `REVIEW`: implementation and verification are complete and handed off for
independent review. It is deliberately NOT `DONE` — only an independent reviewer
may accept it. M-015 and all later missions remain `LOCKED` and remain required
for V1.

M-014 delivered `VF-PRJ-004 Project Archive Import` and `VF-PRJ-007 Project
Clone Plan` at `IMPLEMENTED`. Evidence:
`evidence/missions/M-014/IMPORT_CLONE_LIFECYCLE.{json,md}`.

## M-014 scope

Establish the authoritative Project import/template lifecycle on top of accepted
Project and Artifact authority. Preserve canonical Organization/Project
ownership, tenant authorization, durable audit and provider-neutral trust
boundaries. Provider-specific repository/design/deployment import adapters remain
later capabilities and must not become Project authority.

Explicitly out of scope:

- M-015 full Project lifecycle E2E
- M-016+ provider bindings
- GitHub/Bitbucket/Vercel/Figma provider implementations
- workspace provisioning
- agent/model integrations
- execution/task/deployment
- UI/mobile/Canvas
- later mission scope
