# Bootstrap / Repository Creation Mission

This mission prepares the workspace but does not build user features.

1. Create private GitHub repository `vibeflow` (or approved name) with main branch.
2. Seed root `AGENTS.md`, `.ai/INDEX.yaml`, master-build-system directory and empty architecture-directed monorepo skeleton.
3. Add branch protection/required CI when permissions allow.
4. Create bootstrap branch `bootstrap/m-001` and execute M-001 from the mission register.
5. Do not create speculative product code.

Initial repo skeleton:

```text
apps/mobile
apps/workspace-web
apps/web
services/control-plane
services/gateway
workers/execution
packages/core
packages/contracts
packages/remote
packages/bridge
packages/provider-sdk
packages/verification
packages/ui
adapters/agents
adapters/models
adapters/workspaces
adapters/repositories
adapters/deployments
adapters/connections
infrastructure
migrations
tests/contract
tests/integration
tests/e2e
tests/security
tests/parity
docs
evidence
.ai
```

Logical module boundaries are more important than deployment count; most backend modules may initially live inside `services/control-plane`.
