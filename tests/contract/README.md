# tests/contract

Provider and system contract tests.

- `validate-master-contracts.sh` — wrapper for `scripts/validate-master-contracts.py` (no-dependency master-contract consistency check, generalized mission-progression validation since M-002).
- `validate-harvest-registry.sh` — wrapper for `scripts/validate-harvest-registry.py` (M-002 dependency/harvest registry check).
- `test_m002_validators.py` — deterministic stdlib unittest suite proving both validators fail for duplicate IDs, missing fields, invalid/non-official sources, unsupported decision/integration classifications, missing/unresolved license classifications, and mission dependency progression violations (run: `python3 tests/contract/test_m002_validators.py`).
