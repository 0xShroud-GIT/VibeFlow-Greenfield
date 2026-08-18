# Active Mission

**Mission:** M-006 — Establish CI/security/dependency gates

**Status:** REVIEW

**Phase:** 1 — Repository Foundation

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-006)

M-001 through M-005 were independently accepted, merged, and are `DONE`.
M-006 is the active mission in `REVIEW`; it must not be self-marked `DONE`.
M-007..M-151 remain `LOCKED`.

## M-006 scope

M-006 owns only CI, security scanner, dependency-policy, workflow-hardening,
SBOM, and associated deterministic conformance gates. It does not establish the
M-007 local-development environment or add product/runtime services.

Branch protection remains an external acceptance control. Main is not claimed
protected by repository files; the required reviewer-applied settings and check
contexts are recorded in M-006 evidence.
