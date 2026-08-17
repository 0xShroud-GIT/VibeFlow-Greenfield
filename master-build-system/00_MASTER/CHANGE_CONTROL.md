# Master Change Control

Changes are classified:

- **L0 implementation:** no master change; normal mission/PR.
- **L1 contract clarification:** backwards-compatible master clarification + tests.
- **L2 contract extension:** additive resource/API/event/provider capability; ADR required.
- **L3 architecture change:** changes authority, trust boundary, state machine, protocol ownership or V1 finish line; explicit human approval required.

A master change updates all affected traces: capability ledger, frontend/backend matrix, state/event schemas, mission DAG and tests.
