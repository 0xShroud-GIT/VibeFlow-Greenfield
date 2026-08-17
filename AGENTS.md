# AGENTS.md — VibeFlow Engineering Contract

Read `master-build-system/00_MASTER/MASTER_OF_MASTERS.md` before changing architecture or code.

## Non-negotiable

- Build VibeFlow; Replit evidence is capability evidence only.
- Agent completion != verified completion.
- Reconnect != execution recovery. Replay != workspace reconciliation.
- Repository != workspace. Storage != workspace. Dev workspace != production runtime.
- Agent != model provider.
- Provider-specific code stays behind adapters.
- Raw provider/BYOK secrets never enter client-readable project state or the native-web bridge.
- Tool availability does not imply permission; use grants/policy/approval.
- Do not add a dependency unless approved in `master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml` or an ADR explicitly approves it.
- Prefer ADOPT → WRAP → BRIDGE → EXTEND → BUILD.
- Never invent a duplicate protocol when an approved standard covers the boundary.
- Every durable command is idempotent/deduplicated.
- Every UI status maps to a canonical backend state.

## Mission discipline

Read `.ai/ACTIVE_MISSION.md` and work only that mission. Do not implement later phases “while here.”

Every mission leaves code, tests, evidence, capability/mission status updates, and an ADR only if a master decision changed. Keep diffs reviewable; prefer boring explicit code over speculative abstraction.
