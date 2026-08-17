# Remote / Durability Master

The Remote Layer exists because mobile and browser sessions are ephemeral while work is durable.

Required semantics:
- server-issued session grant bound to actor/project/client capabilities,
- monotonically ordered per-resource/event sequence,
- client acknowledgement cursor,
- replay after reconnect,
- explicit `resync_required` when replay cannot prove continuity,
- state snapshot/reconciliation after resync,
- idempotent command IDs,
- transport reconnect never marks an interrupted Execution recovered.

Temporal may resume workflow logic, but provider process survival must be independently observed. An execution can honestly terminate `LOST`.
