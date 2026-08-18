# VibeFlow OSS Routing — Human Review

Status: **accepted advisory reference layer**. This guide summarizes the accepted routing map; `ROUTING_MANIFEST.json`, reference shards, and `BEHAVIORAL_CONTRACTS.json` are the machine-readable records.

## Guardrails

- Research evidence is advisory; Master Build System contracts remain authoritative.
- A reference is loaded only when the active mission intersects its `owning_missions`.
- Reference usefulness does not approve a dependency or source reuse.
- Direct source reuse requires mission-owned exact revision, file/license, transitive/vendored, security, and interface-boundary review.
- No reference is routed to M-007 by default.
- Repository != workspace; storage != workspace; agent != model provider; tool availability != permission.

## Inventory

- 104 repository references.
- 25 behavioral/adversarial contracts.
- 19 primary references, 42 secondary references, 32 tertiary/historical, 3 standards/official SDKs, 3 remove/reverify, 5 discovery-only.
- Agora is the only deep-pinned reference at landing.

## Primary references

| ID | Project | Disposition | Routes | Pin |
|---|---|---|---|---|
| `REF-001` | CC Pocket | REFERENCE / selective code candidate | `REMOTE_LAYER`, `MOBILE_SHELL`, `CONNECTIONS_GRANTS`, `REPOSITORY_GIT`, `RECOVERY`, `NOTIFICATIONS_AUTOMATIONS` | `required at promotion` |
| `REF-002` | Harness Remote | REFERENCE / BRIDGE pattern | `AGENT_INTEGRATION`, `REMOTE_LAYER`, `MOBILE_SHELL`, `PROVIDER_BINDINGS` | `required at promotion` |
| `REF-003` | Agent of Empires | REFERENCE | `AGENT_INTEGRATION`, `MOBILE_SHELL`, `CONNECTIONS_GRANTS`, `WORKSPACE_INTEGRATION`, `REPOSITORY_GIT` | `required at promotion` |
| `REF-004` | Agent Orchestrator | REFERENCE | `DURABLE_EXECUTION`, `WORKSPACE_INTEGRATION`, `REPOSITORY_GIT`, `VERIFICATION`, `RECOVERY` | `required at promotion` |
| `REF-005` | WarpForge | REFERENCE | `AGENT_INTEGRATION`, `WORKSPACE_INTEGRATION`, `WORKSPACE_WEB_IDE`, `PROVIDER_BINDINGS` | `required at promotion` |
| `REF-006` | Agora | PINNED REFERENCE | `DURABLE_EXECUTION`, `REMOTE_LAYER`, `AGENT_INTEGRATION`, `MODEL_INTEGRATION`, `CONNECTIONS_GRANTS`, `RECOVERY`, `MCP_TOOLS` | `38147fca345565649e8f4971d6cad974bc858b1b` |
| `REF-008` | Happier | REFERENCE | `REMOTE_LAYER`, `MOBILE_SHELL`, `RECOVERY`, `NOTIFICATIONS_AUTOMATIONS` | `required at promotion` |
| `REF-009` | Happy | REFERENCE | `REMOTE_LAYER`, `MOBILE_SHELL`, `RECOVERY`, `NOTIFICATIONS_AUTOMATIONS` | `required at promotion` |
| `REF-011` | Cline | REFERENCE / selective SDK study | `AGENT_INTEGRATION`, `CONNECTIONS_GRANTS`, `MCP_TOOLS`, `DURABLE_EXECUTION`, `VERIFICATION` | `required at promotion` |
| `REF-012` | OpenHands | ADAPTER TARGET + REFERENCE | `AGENT_INTEGRATION`, `WORKSPACE_INTEGRATION`, `DURABLE_EXECUTION`, `VERIFICATION`, `RECOVERY` | `required at promotion` |
| `REF-013` | Yep Anywhere | REFERENCE ONLY until licensed | `REMOTE_LAYER`, `MOBILE_SHELL`, `CONNECTIONS_GRANTS`, `NOTIFICATIONS_AUTOMATIONS`, `RECOVERY` | `required at promotion` |
| `REF-020` | assistant-ui | EVALUATE WRAP for web UI | `MOBILE_SHELL`, `WORKSPACE_WEB_IDE` | `required at promotion` |
| `REF-046` | Paseo | REFERENCE ONLY | `AGENT_INTEGRATION`, `MODEL_INTEGRATION`, `REMOTE_LAYER`, `MOBILE_SHELL` | `required at promotion` |
| `REF-059` | Rootshell | PRODUCT/UX REFERENCE ONLY | `MOBILE_SHELL`, `NOTIFICATIONS_AUTOMATIONS`, `WORKSPACE_WEB_IDE` | `required at promotion` |
| `REF-063` | SwiftNIO SSH | ADOPT/WRAP if native Apple SSH is required | `WORKSPACE_INTEGRATION`, `WORKSPACE_WEB_IDE`, `NATIVE_APP_DEV` | `required at promotion` |
| `REF-064` | XcodeBuildMCP | EXTERNAL MCP INTEGRATION CANDIDATE | `MCP_TOOLS`, `NATIVE_APP_DEV`, `EXTERNAL_ECOSYSTEM` | `required at promotion` |
| `REF-065` | mobile-mcp | EXTERNAL MCP INTEGRATION CANDIDATE | `MCP_TOOLS`, `NATIVE_APP_DEV`, `EXTERNAL_ECOSYSTEM` | `required at promotion` |
| `REF-076` | Superset | COMPETITIVE/ARCHITECTURE REFERENCE ONLY | `DURABLE_EXECUTION`, `WORKSPACE_INTEGRATION`, `WORKSPACE_WEB_IDE`, `REPOSITORY_GIT`, `REMOTE_LAYER`, `MOBILE_SHELL` | `required at promotion` |
| `REF-078` | AionUi | REFERENCE / selective code candidate | `AGENT_INTEGRATION`, `MCP_TOOLS`, `WORKSPACE_WEB_IDE`, `DURABLE_EXECUTION` | `required at promotion` |

## Agora deep pin

- Repository: `newo-ether/Agora`
- Commit: `38147fca345565649e8f4971d6cad974bc858b1b`
- Tree: `1c08de6d29ca462eed03dbd12899c77b81fb789d`
- Highest-value harvest: identity-fenced reducers; durable external-job observation/reconciliation; partial observation vs authoritative result; non-destructive context compaction.
- Explicit reject: plaintext secret fallback; custom Conch crypto/protocol; discovered tools enabled by default as permission.

## Mission routing domains

| Route | Missions |
|---|---|
| `PROVIDER_BINDINGS` | `M-016`, `M-017`, `M-018`, `M-019` |
| `CONNECTIONS_GRANTS` | `M-020`, `M-021`, `M-022`, `M-023` |
| `DURABLE_EXECUTION` | `M-024`, `M-025`, `M-026`, `M-027`, `M-028` |
| `REMOTE_LAYER` | `M-029`, `M-030`, `M-031`, `M-032` |
| `MOBILE_SHELL` | `M-033`, `M-034`, `M-035`, `M-036`, `M-037` |
| `AGENT_INTEGRATION` | `M-038`, `M-039`, `M-040`, `M-041`, `M-042` |
| `MODEL_INTEGRATION` | `M-043`, `M-044`, `M-045`, `M-046` |
| `WORKSPACE_INTEGRATION` | `M-047`, `M-048`, `M-049`, `M-050`, `M-051` |
| `WORKSPACE_WEB_IDE` | `M-052`, `M-053`, `M-054`, `M-055`, `M-056` |
| `NATIVE_WEB_BRIDGE` | `M-057`, `M-058`, `M-059`, `M-060`, `M-061` |
| `REPOSITORY_GIT` | `M-062`, `M-063`, `M-064`, `M-065`, `M-066` |
| `CHECKPOINTS` | `M-067`, `M-068`, `M-069`, `M-070`, `M-071` |
| `VERIFICATION` | `M-072`, `M-073`, `M-074`, `M-075`, `M-076` |
| `RECOVERY` | `M-077`, `M-078`, `M-079`, `M-080`, `M-081` |
| `MCP_TOOLS` | `M-082`, `M-083`, `M-084`, `M-085`, `M-086` |
| `OBSERVABILITY` | `M-097`, `M-098`, `M-099`, `M-100`, `M-101` |
| `SECURITY_PRODUCT` | `M-102`, `M-103`, `M-104`, `M-105`, `M-106` |
| `NOTIFICATIONS_AUTOMATIONS` | `M-107`, `M-108`, `M-109`, `M-110`, `M-111` |
| `NATIVE_APP_DEV` | `M-125`, `M-126`, `M-127`, `M-128` |
| `EXTERNAL_ECOSYSTEM` | `M-129`, `M-130`, `M-131`, `M-132`, `M-133` |
| `RELIABILITY` | `M-142`, `M-143`, `M-144`, `M-145`, `M-146` |

## Behavioral contract use

`BEHAVIORAL_CONTRACTS.json` contains the 25 cross-project tests. Future mission packets should import only contracts whose owning mission/domain intersects the active mission, then restate them as VibeFlow-owned acceptance tests rather than copying competitor implementation.

## Promotion rule

When an owning mission promotes a reference beyond advisory study, create a pinned extraction dossier first. The dossier must establish exact upstream revision, license/reuse boundary, files/behaviors being harvested, security/trust implications, applicable VibeFlow invariant(s), and deterministic tests. Only actual ADOPT/WRAP technology decisions belong in `master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml`.
