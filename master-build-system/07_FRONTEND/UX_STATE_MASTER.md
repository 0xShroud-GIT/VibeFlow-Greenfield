# UX State Master

Every async surface must represent: loading, empty, ready, degraded, permission-required, approval-required, disconnected, reconnecting, resync-required, failed and recoverable states where applicable.

Agent/task-specific distinctions: planning, executing, waiting approval, interrupted, candidate complete, verifying, verified, verification failed, recovery in progress, execution lost.

Never display provider `done` as VibeFlow `verified`.
