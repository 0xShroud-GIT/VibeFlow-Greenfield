# scripts

Repository maintenance and validation scripts.

- `repo-sanitize.sh` — tracked-path and high-confidence secret sanitation.
- `validate-master-contracts.py` — stdlib master-contract, capability-ledger and generalized mission-progression consistency.
- `validate-harvest-registry.py` — stdlib harvest integrity, official-source, license, package-coordinate and deny-by-default build-approval policy.
- `validate-threat-model.py` — stdlib M-003 security-contract validator.
- `validate-m004-foundation.py` — retained monorepo/toolchain foundation gate.
- `generate-contracts.py` / `validate-m005-contract-codegen.py` — deterministic generated-contract pipeline and retained gate.
- `validate-m006-security-gates.py` — network-free static M-006 gate with exact active-snapshot assertions and durable capability/workflow/scanner/Action/Semgrep lock progression.
- `security/` — checksum/provenance-verified CI tool installer, exact-binary Gitleaks fixture smoke test, and deterministic Gitleaks, OSV-Scanner, Trivy, CycloneDX and Semgrep wrappers. Runtime scans are intentionally outside root `pnpm run check`.
