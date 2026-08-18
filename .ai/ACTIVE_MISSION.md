# Active Mission

**Mission:** M-007 — Establish local dev environment

**Status:** REVIEW

**Phase:** 1 — Repository Foundation

Authoritative mission row:
`master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml` (M-007)

M-001 through M-006 are accepted and `DONE`; M-006 acceptance was consumed
by this successor mission. M-007 is the active mission in `REVIEW`; it must
not be self-marked `DONE`. M-008..M-151 remain `LOCKED`.

## M-007 scope

M-007 establishes the ratified Dev Containers repository development
environment: a digest-pinned `node:24.19.0` official image plus one
digest-pinned registered python feature, a provenance/security policy lock
under `infrastructure/dev/`, stdlib-only doctor/bootstrap/runtime-smoke
scripts, a retained static validator and adversarial mutation suite, and
CI evidence for pulling the exact image, running the runtime smoke inside
it, scanning it with the locked Trivy toolchain, and generating an ephemeral
dev-image CycloneDX SBOM.

M-007 is infrastructure for building VibeFlow. It is not the VibeFlow
Workspace product, a hosted sandbox, a deployment environment, or a product
runtime descriptor implementation.
