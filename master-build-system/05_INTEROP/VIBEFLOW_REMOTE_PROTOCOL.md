# VibeFlow Remote Protocol v1 — Required Semantics

Envelope fields: protocol_version, message_id, correlation_id, actor_session_id, project_id, resource_type/id, sequence/cursor where relevant, message_type, payload, sent_at.

Commands carry idempotency_key and expected_version when applicable. Server responses carry canonical resource version. Stream supports `event`, `ack`, `snapshot`, `resync_required`, `error`, `capabilities`.

A reconnect begins with last acknowledged cursor and current project/resource expectations. If the server cannot prove replay continuity, it requires a snapshot/reconciliation flow rather than guessing.
