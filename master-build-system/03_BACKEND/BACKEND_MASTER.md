# Backend Master

## Initial logical modules

- identity
- project
- provider-registry
- connection
- policy/approval
- execution
- gateway/remote
- repository
- verification/evidence
- release/deployment
- notification
- billing
- audit/observability

Most start inside one control-plane deployment. `gateway` and Temporal workers may deploy separately early because their scaling/failure characteristics differ.

## Command model

Mutations are commands with authenticated actor, tenant/project scope, idempotency key and expected resource version where concurrency matters. Commands produce durable state transitions and events through an outbox/transactional pattern.

## API model

Prefer boring HTTP JSON/OpenAPI-style commands/queries plus versioned WebSocket remote stream. Do not introduce GraphQL simply because Replit used it.

## Persistence

PostgreSQL is source of VibeFlow truth. Temporal stores workflow execution mechanics, but control-plane resource rows remain the product authority. Object storage holds hashed Evidence payloads/artifacts. Provider systems remain authoritative only for their own external resources.
