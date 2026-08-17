# Repository Seed Tree

```text
vibeflow/
├── AGENTS.md
├── .ai/
├── master-build-system/        # this pack, versioned
├── apps/
│   ├── mobile/
│   ├── workspace-web/
│   └── web/
├── services/
│   ├── control-plane/
│   └── gateway/
├── workers/
│   └── execution/
├── packages/
│   ├── core/
│   ├── contracts/
│   ├── remote/
│   ├── bridge/
│   ├── provider-sdk/
│   ├── verification/
│   └── ui/
├── adapters/
│   ├── agents/
│   ├── models/
│   ├── workspaces/
│   ├── repositories/
│   ├── connections/
│   └── deployments/
├── migrations/
├── infrastructure/
├── tests/{contract,integration,e2e,security,parity}/
├── docs/
└── evidence/
```

Do not create one deployable service per logical module on day one.
