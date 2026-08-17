# GitHub Workspace Setup

Recommended initial repository: private `vibeflow` repository, default branch `main`.

Seed first commit with `AGENTS.md`, `.ai/`, `master-build-system/`, README and minimal empty package/skeleton files. Then create `bootstrap/m-001` branch; execute M-001 through a PR.

Recommended protections once CI exists: required PR, required checks (format/lint/typecheck/unit/contract/security/dependency), block force-push to main, secret scanning, Dependabot/Renovate-style controlled upgrades, CODEOWNERS for master contracts/security if team exists.

Do not give coding agents unrestricted merge-to-main; they should work in branches/PRs and return evidence.
