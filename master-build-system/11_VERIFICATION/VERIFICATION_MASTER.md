# Verification Master

Verification is a VibeFlow authority and differentiator.

## Pipeline

Policy selects the cheapest reliable proof appropriate to the changed risk while preserving fail-closed behavior.

1. capture candidate WorkspaceRevision/repository ref/hash,
2. reconcile workspace/repository state,
3. collect diff and classify affected/risk boundaries,
4. for material external technology usage, validate implementation against `04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml`,
5. run build/typecheck/lint as applicable,
6. run affected tests plus any risk-triggered regression suites,
7. run applicable security/supply-chain checks,
8. apply policy/approval requirements,
9. optionally capture preview/health/browser evidence,
10. emit immutable Evidence items,
11. evaluate VerificationChecks,
12. mark Verification PASSED/FAILED,
13. only then may Task/Execution project as VERIFIED.

Reference correctness and execution correctness are independent requirements when an external technology is involved. Official guidance does not override failing execution, and passing tests do not make unsupported or wrong-version API usage correct.

## Verification depth

- **PR-fast:** always run durable invariant checks, affected build/typecheck/tests and baseline security checks.
- **Risk-triggered:** dependency, container, workflow, security-policy, native/platform, schema/contract or other sensitive-boundary changes add the relevant deep scans, mutation/regression suites, runtime checks and SBOM evidence.
- **Full-system:** main, release and explicitly scheduled certification runs execute the complete applicable regression and evidence set.

Risk classification must be deterministic and centrally tested. Unknown paths, failed diff collection, or failed classification take the deeper path. Rename detection must not hide the original sensitive path. Required check contexts remain present even when irrelevant expensive steps are conditionally skipped.

## Development-image freshness

The development image is a development artifact, not a product release image. Exact dev-image runtime, Trivy and CycloneDX work is required on a pull request when a change can affect the dev image, its toolchain, its build/scan workflow, or the verification classifier. It is also required on every push to `main` as full-system verification, and the security workflow performs scheduled certification so newly disclosed image vulnerabilities are discovered even when no relevant pull request is open.

An ordinary product-only pull request may skip unchanged dev-image work, but the security workflow must emit candidate-bound machine-readable evidence stating that the check was not applicable/executed and why. A green required context on such a PR must never be represented as evidence that the image scan executed.

When dev-image verification runs, vulnerability scan and SBOM generation must consume the same frozen image artifact. Evidence records both the candidate head revision and the exact revision actually tested by CI, plus immutable image identity/content hash and SBOM hash. If image verification is classified applicable, missing or unsuccessful candidate-bound evidence fails verification.

## Durable invariants

A mission proves a capability at acceptance. Lasting requirements are then owned by the appropriate subsystem/domain validator. Historical mission-specific mutation suites remain regression assets and run when their governed boundary changes or during full-system verification; unrelated product changes do not need to replay the full construction history.

A change to the candidate revision invalidates stale verification according to check policy. Skipping an applicable check, weakening a threshold, or reusing evidence from a different candidate is not verification.
