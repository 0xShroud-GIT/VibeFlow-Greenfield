# scripts

Repository maintenance and validation scripts.

- `repo-sanitize.sh` — tracked-path and high-confidence secret sanitation.
- `validate-master-contracts.py` — no-dependency master-contract consistency validator with generalized mission-progression validation (M-002 removed the M-001 bootstrap hard-coding).
- `validate-harvest-registry.py` — no-dependency dependency/harvest registry validator introduced by M-002 (35-entry integrity, exact official-source identity, decision/integration vocabulary, license classification, DO_NOT_INVENT coherence).
- `validate-threat-model.py` — no-dependency M-003 security-contract validator for 12 asset IDs, 24 threat IDs, 13 trust-boundary IDs, cross-references, invariant coverage, secret/workspace protections, and fail-closed authority markers.
