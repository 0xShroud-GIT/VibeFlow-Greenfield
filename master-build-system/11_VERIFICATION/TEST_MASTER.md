# Test Master

Layers:
- unit: deterministic local logic,
- contract: schemas/state transitions/provider adapter contracts,
- integration: DB/Temporal/gateway/provider sandbox,
- security: negative tenant/grant/secret/bridge cases,
- recovery/chaos: disconnect/crash/provider loss/replay/resync,
- web E2E: Playwright,
- mobile E2E: Maestro,
- parity/product journeys: provider-neutral user outcomes,
- provider certification: each Tier-1 adapter.

A feature is not done without tests at the layer appropriate to its authority/risk.
