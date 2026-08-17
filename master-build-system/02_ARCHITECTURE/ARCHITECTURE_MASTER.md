# Architecture Master

## Logical topology

```text
Mobile app ─┐
            ├── VibeFlow Gateway / Remote Layer ─── Control Plane
Workspace ──┘                                  │
                                               ├── Project / Binding Authority
                                               ├── Policy / Grants / Approval
                                               ├── Task / Execution (Temporal-backed)
                                               ├── Evidence / Verification
                                               ├── Release / Billing / Audit
                                               └── Provider Registry

Gateway/Adapters ── ACP ── Coding Agents
Agent/Adapters   ── MCP ── Tools/Data
Delegation       ── A2A ── External Agents (when needed)
Optional UI      ── AG-UI compatibility

Bindings → Model providers / Workspaces / Git hosts / Data / Storage / Deployment / Observability providers
```

## Deployment shape: start boring

Logical modules are not microservices by default. Phase 1 should deploy a modular TypeScript control plane, a gateway/streaming edge, PostgreSQL, Temporal and object storage. Split services only when scale, isolation or independent failure domains justify it.

## Authority pattern

Every provider resource is attached through a VibeFlow binding. External IDs never replace VibeFlow Project/Task/Execution/Release identity.

## Data pattern

PostgreSQL stores durable product state and immutable metadata. Blob evidence/artifacts may live in S3-compatible storage by content hash. Provider secrets are referenced through SecretRef and encrypted/brokered; never stored in ordinary client-readable rows.
