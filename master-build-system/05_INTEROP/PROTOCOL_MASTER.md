# Protocol Master

## Adopted boundaries

- **ACP**: VibeFlow client/gateway ↔ coding agent interoperability.
- **MCP 2026-07-28**: agent/application ↔ tools/resources/prompts/data services.
- **A2A 1.0**: independent agent ↔ agent delegation/interoperation when actually needed.
- **AG-UI**: optional compatibility bridge for generic agent/frontend event ecosystems; not VibeFlow's source of UI truth.
- **Dev Containers**: portable environment description.
- **OpenTelemetry**: trace/metric/log propagation.

## VibeFlow-owned protocols

Only gaps not covered above:
1. Remote mobile/web durability: auth, project binding, sequence, cursor, replay, resync, idempotent commands.
2. Native↔workspace bridge: versioned local app/web bridge with origin/project/session binding and device actions.
3. Provider adapter contracts and certification profiles.

These protocols must be narrow and versioned.
