# Contract Rules

Frontend and backend share resource IDs, enum/state definitions, command/event schemas and error codes from generated contract packages. No frontend-local copy of server enums.

Provider adapters translate provider events/errors/capabilities into canonical contracts. Provider-specific fields live in `provider_metadata` diagnostic envelopes and never control authorization/state transitions directly.
