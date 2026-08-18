# scripts

Repository maintenance and validation scripts.

- `repo-sanitize.sh` — tracked-path and high-confidence secret sanitation.
- `validate-master-contracts.py` — stdlib master-contract, capability-ledger and generalized mission-progression consistency.
- `validate-harvest-registry.py` — stdlib harvest integrity, official-source, license, package-coordinate and deny-by-default build-approval policy.
- `validate-threat-model.py` — stdlib M-003 security-contract validator.
- `validate-m004-foundation.py` — retained monorepo/toolchain foundation gate.
- `generate-contracts.py` / `validate-m005-contract-codegen.py` — deterministic generated-contract pipeline and retained gate.
- `validate-m006-security-gates.py` — network-free static M-006 gate with exact active-snapshot assertions and durable capability/workflow/scanner/Action/Semgrep lock progression.
- `validate-m007-local-dev.py` — retained M-007 dev-environment gate: active M-007 snapshot vs durable later-mission mode; digest-pinned dev-container provenance, security posture, toolchain agreement, capability/ledger sync and master hash integrity.
- `dev-doctor.py` — fast network-free dev-environment precondition report (no modifications).
- `dev-bootstrap.py` — single repository-owned bootstrap: verify tools, enable the corepack path, verify exact Node/pnpm, `pnpm install --frozen-lockfile`, `pnpm run check`.
- `dev-runtime-smoke.py` — exact runtime smoke for node 24.19.0 / pnpm 11.4.0 / python3 / git, runnable inside the dev container.
- `security/` — checksum/provenance-verified CI tool installer, exact-binary Gitleaks fixture smoke test, and deterministic Gitleaks, OSV-Scanner, Trivy, CycloneDX and Semgrep wrappers, plus dev-image Trivy scan (`scan-dev-image.sh`) and dev-image CycloneDX (`generate-dev-image-sbom.sh`) wrappers. Runtime scans are intentionally outside root `pnpm run check`.
