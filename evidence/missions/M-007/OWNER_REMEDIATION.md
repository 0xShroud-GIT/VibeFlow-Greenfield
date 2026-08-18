# M-007 Owner Remediation Decision

**Parent candidate:** `10d7db0d9659ce276169ed1fa4ba5ae6625af1ca`  
**Mission state:** M-007 remains `REVIEW`; M-008+ remain `LOCKED`.  
**Security threshold:** unchanged.

Arena Round 5 exhausted the official Node 24.19.0 Debian full/slim candidate matrix and stopped because every otherwise-acceptable image retained the same bundled npm findings (6 HIGH + 1 CRITICAL). The selected `trixie-slim` + pinned Python/Git Features candidate had zero Debian HIGH/CRITICAL findings, so the only failing surface was unused npm bundled by the official Node image.

The repository owner/integrator authorizes the narrow remediation explicitly contemplated by packet section 8 (`select/remediate the image instead`): wrap the already-selected immutable `node:24.19.0-trixie-slim` digest in one exact Dockerfile that removes unused bundled npm/yarn and their shims by filesystem deletion only.

The remediation is intentionally constrained:

- exact immutable upstream base digest is unchanged;
- no `apt`, `apt-get`, `apk`, package upgrade, package install, or new package manager;
- no `curl`, `wget`, network download, or floating reference;
- no new tool or product dependency;
- Node 24.19.0 and Corepack remain;
- pnpm remains exactly 11.4.0 through the existing Corepack path;
- Python and Git remain the existing digest-pinned official Dev Container Features;
- final container remains non-root (`USER node` plus `remoteUser`/`containerUser`);
- Trivy HIGH/CRITICAL policy is unchanged;
- exact-head CI must prove runtime smoke, full retained tests, Trivy and CycloneDX again.

This decision resolves only the Round-5 stop-report. It does not authorize general Dockerfile/package mutation in M-007 or later missions. `LOCAL_DEV_ENVIRONMENT.md/.json` remain the Arena builder history through Round 5; this owner evidence records the integrator-only remediation that follows it. `INTENDED_WORKFLOWS.patch` is historical handoff evidence and is superseded operationally by the workflow edits applied on the same PR branch.
