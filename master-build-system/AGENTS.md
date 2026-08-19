# AGENTS.md — VibeFlow Engineering Contract

Read `00_MASTER/MASTER_OF_MASTERS.md` before changing architecture.

## Non-negotiable

- Build VibeFlow; Replit evidence is capability evidence only.
- Agent completion != verified completion.
- Reconnect != execution recovery. Replay != workspace reconciliation.
- Repository != workspace. Storage != workspace. Dev workspace != production runtime.
- Agent != model provider.
- Provider-specific code stays behind adapters.
- Raw provider/BYOK secrets never enter client-readable project state or the native-web bridge.
- Tool availability does not imply permission; use grants/policy/approval.
- Do not add a dependency unless it is approved in `06_HARVEST/OSS_HARVEST_REGISTRY.yaml` or an ADR approves it.
- Treat model implementation knowledge as non-authoritative for external technology: follow `04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml` and use the highest applicable version-matched authority before and after material external API/framework/platform/configuration changes.
- Prefer ADOPT → WRAP → BRIDGE → EXTEND → BUILD.
- Never invent a duplicate protocol when an approved standard covers the boundary.
- Every durable command is idempotent/deduplicated.
- Every status shown in UI maps to a canonical backend state.

## Mission discipline

Work only the current mission. Do not implement future phases “while here.”

Every mission must leave:
1. code,
2. tests,
3. evidence,
4. capability/mission status updates,
5. an ADR only if a master decision changed.

Keep diffs reviewable. Prefer boring, explicit code over clever abstraction.
