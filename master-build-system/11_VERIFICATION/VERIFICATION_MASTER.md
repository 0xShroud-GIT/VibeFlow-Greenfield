# Verification Master

Verification is a VibeFlow authority and differentiator.

Pipeline (policy-selected):
1. capture candidate WorkspaceRevision/repository ref/hash,
2. reconcile workspace/repository state,
3. collect diff,
4. run build/typecheck/lint as applicable,
5. run tests,
6. run security/supply-chain checks,
7. apply policy/approval requirements,
8. optionally capture preview/health/browser evidence,
9. emit immutable Evidence items,
10. evaluate VerificationChecks,
11. mark Verification PASSED/FAILED,
12. only then may Task/Execution project as VERIFIED.

A change to the candidate revision invalidates stale verification according to check policy.
