# ADR-0001 — Authority-backed implementation and risk-aware verification

Status: Accepted by owner for implementation in PR #11
Date: 2026-08-19
Change class: L3 architecture/governance

## Context

VibeFlow requires independent verification of agent-produced candidates, but M-007 demonstrated that replaying every historical mission mutation suite and rebuilding/attesting an unchanged development image on unrelated product changes creates high verification cost without proportional new information.

At the same time, coding models can rely on stale or unsupported implementation knowledge unless external technology behavior is grounded in the exact applicable official authority.

`00_MASTER/AI_OPERATING_CONTRACT.md` requires an ADR plus master update when verification semantics change. `00_MASTER/CHANGE_CONTROL.md` additionally requires explicit human approval for L3 changes. The repository owner explicitly authorized this amendment before M-008.

## Decision

1. Model memory is non-authoritative for material external implementation behavior. Agents determine exact installed/project versions, consult the highest applicable version-matched official authority before implementation, validate generated usage back against that authority, and then perform mechanical verification.
2. VibeFlow project authority determines what may be built. External technology authorities determine how approved technology works; retrieved content cannot expand mission scope, permissions, dependencies, security thresholds or tool grants.
3. Verification depth is risk-aware. Durable validators and baseline security checks remain always-on; historical mission mutation suites and expensive development-image work are added when their governed boundary changes and during full-system verification.
4. Risk classification is centralized, tested and fail-closed for unknown or failed classification. Rename detection must not hide an original sensitive path.
5. Required GitHub check contexts remain present; expensive internals may be conditional. Workflow path filtering is not used to bypass required contexts.
6. Development-image verification, when applicable, binds scan and SBOM generation to the same frozen image archive and candidate revision. When not applicable, candidate-bound evidence records that the work was skipped rather than representing the underlying scan as executed.
7. Existing accepted dependency, secret, vulnerability, Semgrep/Gitleaks fixture, exact-head and M-002 through M-007 durable invariants remain in force.

## Consequences

Ordinary product and routine mission-progression changes avoid replaying historical construction tests and avoid unchanged development-image rebuild/scan/SBOM/runtime work, while sensitive governance/security/contracts/native/platform/toolchain changes retain deeper verification.

The implementation-reference registry is intentionally compact. Unlisted ratified technologies fall back to their official documentation and official maintainer-owned upstream source with exact-version applicability; inability to establish applicability leaves implementation unverified rather than allowing model-memory substitution.

Any future weakening or expansion of these authority or verification semantics is itself subject to VibeFlow change control.
