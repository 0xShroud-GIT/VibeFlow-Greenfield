# VibeFlow Master of Masters

## Product thesis

VibeFlow is the **mobile-first control, policy, durability, recovery and independent-verification layer** that makes independently owned coding agents, AI/model providers, development workspaces, repositories, tools/data connections and deployment providers behave like one integrated development environment.

VibeFlow supports:

- **BYOA** — Bring Your Own Agent
- **BYOK** — Bring Your Own Key / AI provider
- **BYOW** — Bring Your Own Workspace

The phone is a control/approval/inspection surface. It is not the execution owner.

## What VibeFlow owns

VibeFlow is authoritative for product identity/organizations/projects, bindings, grants, policy, approvals, durable Task/Execution state, normalized events, reconciliation records, checkpoint manifests, evidence, verification, releases, entitlements/usage attribution, notifications and audit.

## What VibeFlow normally does not own

A coding agent runtime, foundation model inference, Git hosting, arbitrary workspace compute, application database bytes, application object storage bytes, or deployment cloud runtime. These are integrated through bindings/adapters and may later have first-party implementations only when evidence justifies ownership.

## North-star user experience

A user can create/open a project, select/connect an agent/model/workspace, ask for work, watch a durable task continue remotely, inspect/edit files, use a terminal and preview, review diffs/checkpoints, approve privileged actions, connect tools/services, verify the candidate independently, and release/deploy — from phone and web workspace — without needing one provider to own the entire stack.

## Trust rule

**Agent says done → candidate completion. VibeFlow independently verifies → VERIFIED.**

## Architecture rule

The canonical resources and state machines are the cross-surface contract. Frontend, backend, agent adapters and providers do not invent parallel status vocabularies.

## Standards rule

Use open standards/official SDKs first: ACP for coding-agent client interoperability, MCP for tools/data, A2A when real agent-to-agent delegation is needed, AG-UI only as optional frontend compatibility, Dev Containers for environment descriptions, OpenTelemetry for telemetry. VibeFlow owns the missing authority/recovery/verification semantics.

## Build rule

The complete destination is visible from day one, but only one bounded mission is implemented at a time. The mission DAG is authoritative for build order.

## Sources of truth

- Product: `01_PRODUCT/PRODUCT_MASTER.md`
- Architecture/resources: `02_ARCHITECTURE/ARCHITECTURE_MASTER.md`, `CANONICAL_RESOURCE_MODEL.yaml`
- Backend/events/states: `03_BACKEND/`
- AI/agents: `04_AI_AGENT/`
- Protocols: `05_INTEROP/`
- OSS/SDK choices: `06_HARVEST/`
- Frontend: `07_FRONTEND/`
- Security: `08_SECURITY/`
- Frontend/backend binding: `09_CONTRACTS/`
- Build missions: `10_IMPLEMENTATION/`
- Verification/test/release: `11_VERIFICATION/`
- Research provenance: `99_REFERENCE/`
