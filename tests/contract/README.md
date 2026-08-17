# tests/contract

Provider and system contract tests.

- `validate-master-contracts.sh` — wrapper for `scripts/validate-master-contracts.py` (no-dependency master-contract consistency check, generalized mission-progression validation since M-002).
- `validate-harvest-registry.sh` — wrapper for `scripts/validate-harvest-registry.py` (M-002 dependency/harvest registry check).
- `test_m002_validators.py` — deterministic stdlib unittest suite proving the M-002 registry/mission validators reject malformed provenance, policy-contract drift, multiline-rule corruption, and invalid mission progression.
- `test_m003_security_contracts.py` — 18 deterministic stdlib mutation tests proving the M-003 security validator rejects missing/duplicate threats, invalid asset/boundary refs, uncovered boundaries, invariant-crosswalk loss, secret/workspace-policy weakening, provider-authority weakening, and fail-open security drift.
