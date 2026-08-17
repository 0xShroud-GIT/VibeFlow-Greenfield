# Agent Provider Contract

Every Agent adapter must expose normalized capabilities and lifecycle operations:

- discoverCapabilities
- createSession / attachSession / closeSession
- sendPrompt / sendControl
- streamNormalizedEvents
- cancel
- requestPlanMode / requestBuildMode when supported
- report provider session ID as reference metadata
- enumerate tool/workspace expectations

Adapter output maps into VibeFlow Execution events. Provider-specific finish/status values map to `CANDIDATE_COMPLETE`, never `VERIFIED`.

Certification must test disconnects, duplicate control messages, cancellation, malformed events, unsupported capabilities and provider session loss.
