# M-006 — CI, Security, and Dependency Gates

## Identity and acceptance boundary

| Field | Value |
| --- | --- |
| Starting `origin/main` | `76f2f2ae908cd728e337b64fe538cbd07a158945` |
| Verified branch start | `76f2f2ae908cd728e337b64fe538cbd07a158945` |
| Arena session branch | `arena/01a01281-vibeflow-greenfield` |
| Mission state | `M-001..M-005 DONE`; `M-006 REVIEW`; `M-007..M-151 LOCKED` |
| ADR | Not required — implementation stays inside the ratified M-006 policy |

Arena binds this session to `arena/01a01281-vibeflow-greenfield`; it cannot use
the requested `mission/m-006-ci-security-gates` name. Acceptance must bind to
the exact final pushed head reported in the PR/handoff, not to a SHA embedded in
this appendable evidence document. Any later push invalidates an earlier
exact-head review and requires all required checks again. M-006 is never marked
`DONE` here and must not be merged by the builder.

## Workflow-permission blocker

One push attempt was made with the intended workflow changes at candidate commit
`55a380b`. GitHub rejected it because the Arena GitHub App lacks permission to
create/update `.github/workflows/**`. No OAuth/device-code workaround was used
and no second workflow push was attempted. As required, workflow-only changes
were reverted from the commit that will be pushed. The exact complete intended
diff is preserved in:

`evidence/missions/M-006/INTENDED_WORKFLOWS.patch`

SHA-256: `fb415f076d49ae02c824b6432e0805f863eb5a476031aa3d28034f202ef54a15`

Until GPT applies that patch through a workflow-authorized connector, the
checked-in workflows remain the pre-M-006 files: the security workflow is
absent, Action tags are not hardened, path filters remain, and M-006 workflow
steps are absent. Consequently `validate-m006-security-gates.py`, the M-006
mutation suite's real-repository pass case, root `pnpm run check`, all four CI
scanner jobs, the aggregate gate, and SBOM upload cannot be green on the pushed
head. The intended-workflow implementation passed those static checks before
this required reversion; that result is historical implementation evidence, not
a claim that the pushed workflow state passes.

### Reviewer workflow resolution

The blocker above is preserved as historical evidence. GPT subsequently applied
the exact workflow change in reviewer commit
`4c1a237b8a767a93860e301f43d3451cb27d9f04`. The first real M-006 workflow run
then completed green. The SBOM artifact from that run was generated, but later
artifact inspection found incomplete dependency coverage; that result is
recorded separately below and is not rewritten as a complete-inventory pass.

## Dependency policy

`master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml` remains the one
technology authority. Its `package_coordinates` list supports multiple package
coordinates per harvest entry and currently maps:

| npm coordinate | Harvest ID | Approved direct use |
| --- | --- | --- |
| `typescript` | H-002 | development |
| `turbo` | H-004 | development |
| `typebox` | H-025 | production |
| `vitest` | H-028 | development |

Every external direct dependency/devDependency/optionalDependency/
peerDependency in every workspace manifest must map to one unique ratified
coordinate. `@vibeflow/*` dependencies are separately validated as existing
workspace edges using the `workspace:` protocol. M-004 continues to enforce
exact/non-exotic specs and the lockfile.

Install/build scripts default to deny. `install_build_script_policy.approvals`
is currently empty. A future `allowBuilds` key must match an explicit
`pnpm_matcher` whose harvest approval records the ratified package, harvest ID,
one exact package version, boolean approval, and non-empty rationale. The M-006
gate reconciles both direct manifests and resolved `pnpm-lock.yaml` versions;
dependency-version drift invalidates a stale approval. Active M-005 snapshots
still reject the key; durable M-005 accepts only matcher/version-reconciled
approvals. `dangerouslyAllowAllBuilds` is permanently forbidden. Review-required
licenses cannot be approved for production dependency use.

## Immutable security toolchain

All scanner distributions are CI tools, not npm application dependencies.

| Tool | Harvest | Version | Exact distribution | Immutable identity |
| --- | --- | ---: | --- | --- |
| Gitleaks | H-029 | 8.30.1 | `gitleaks_8.30.1_linux_x64.tar.gz` official GitHub release | SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` |
| Trivy | H-030 | 0.72.0 | `trivy_0.72.0_Linux-64bit.tar.gz` official GitHub release | SHA-256 `bbb64b9695866ce4a7a8f5c9592002c5961cab378577fa3f8a040df362b9b2ea` |
| OSV-Scanner | H-031 | 2.4.0 | `osv-scanner_linux_amd64` official GitHub release | SHA-256 `15314940c10d26af9c6649f150b8a47c1262e8fc7e17b1d1029b0e479e8ed8a0` |
| Semgrep CE | H-032 | 1.172.0 | `docker.io/semgrep/semgrep` | OCI index digest `sha256:65dcd4408adda7c183a6b4550cb1e9b19f7f627a6fbb7e0559bd466bedc44d7b` |

Trivy's official checksum manifest is locked at SHA-256
`ebe9d19a774b950e240b1017a038e9b5a002ea068e02023369ff6d241c10c580`.
Its release Sigstore bundle is locked at SHA-256
`fccbe7d4877af44f27e205528626dfeb3ff6efac57c22061f1fccb59e8a80007`.
The installer verifies the archive, the official manifest binding, the bundle
identity, and that the bundle subject digest equals the archive digest. This
explicitly addresses H-030's recorded malicious-release incident history.

The active M-006 snapshot still asserts the four exact scanner versions above.
After M-006 acceptance, scanner validation is harvest/lock-driven: retained
scanner keys cannot disappear, but a later exact version is valid only when its
CI-tool harvest entry, official source, immutable distribution identity, and
lock version agree. Semgrep rule IDs/severities/config and fixture paths are
likewise driven by `semgrep_policy`; active M-006 preserves the exact six-rule
snapshot while durable mode permits locally configured, fixture-backed locked
rules.

## GitHub Action pins and workflow progression

The M-006 active snapshot requires exactly these Action lock entries and pins:

- `actions/checkout` v7.0.1 — `3d3c42e5aac5ba805825da76410c181273ba90b1`
- `actions/setup-node` v7.0.0 — `820762786026740c76f36085b0efc47a31fe5020`
- `actions/upload-artifact` v7.0.1 — `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`

The four M-006 baseline workflows permanently retain unfiltered PR/main-push
coverage, required jobs, exact least-privilege `contents: read`, finite timeouts,
and fail-closed scanner aggregation. Durable mode does not pretend every future
workflow has the same trigger or permission needs: an additional workflow must
be explicitly registered under `workflow_policy.additional_workflows` with its
required jobs, exact permissions, allowed secrets, cache/write/continue policy,
and rationale. Every external Action remains full-SHA pinned and must match a
provenanced `github_actions` lock entry. This permits later authorized workflows
and Actions without weakening the baseline or accepting unregistered expansion.

## Scan commands and policy

```text
python3 scripts/security/install-ci-tool.py gitleaks
scripts/security/test-gitleaks.sh
  -> exact installed version; generated negative repo must pass; generated
     positive repo must fail and redact the runtime-only synthetic token
scripts/security/run-gitleaks.sh
  -> full reachable history (`--log-opts="--all"`), findings fail, 100% redaction

python3 scripts/security/install-ci-tool.py osv-scanner
scripts/security/run-osv-scanner.sh
  -> recursive source/resolved lockfile scan, any known vulnerability fails

python3 scripts/security/install-ci-tool.py trivy
scripts/security/run-trivy.sh
  -> filesystem vulnerability + misconfiguration scan across production,
     development, build and test dependencies (`--include-dev-deps`);
     actionable/fixed HIGH/CRITICAL findings fail

scripts/security/test-semgrep-rules.sh
scripts/security/run-semgrep.sh
  -> Semgrep CE 1.172.0 by digest; only security/semgrep.yml; ERROR findings fail

scripts/security/generate-sbom.sh "$RUNNER_TEMP/vibeflow-repository.cdx.json"
  -> ephemeral CycloneDX JSON plus content SHA-256; inventory includes all pnpm
     production, development, build and test dependency scopes
```

The local Semgrep configuration has six high-confidence Python/JS/TS dynamic
execution and unsafe shell/process rules. Exact positive rule IDs and zero
negative findings are asserted. No remote Registry config (`p/...`, URL, or
other floating config) is used.

**Product-container vulnerability scan: N/A.** No product image exists in M-006;
no container scan pass is claimed. Repository Dockerfile/IaC misconfiguration
scanning activates through Trivy when such files appear.

## Actual verification recorded before first CI push

No expected CI result is represented as actual CI. At this evidence revision:

- Node `v24.19.0` / pnpm `11.4.0` frozen install: PASS.
- `pnpm run check`: PASS (static security validation included; scanner downloads excluded).
- Historical Semgrep positive/negative fixture run at candidate `55a380b`: PASS —
  6 expected rule IDs / 0 negative findings. The generalized lock-driven fixture
  wrapper was not re-executed locally after this response because the exact
  distribution is unavailable in the reset Arena environment; no new scanner
  pass is claimed.
- Semgrep repository scan at committed candidate `55a380b`: PASS — 6 rules,
  17 applicable source targets, 0 findings. Positive fixtures were excluded.
- The new exact-binary Gitleaks positive/negative smoke test was not executed
  locally because the exact release binary could not be downloaded through
  Arena release-asset egress. No Gitleaks fixture pass is claimed.
- Gitleaks repository scan, OSV-Scanner, Trivy, and Trivy SBOM: not run locally because Arena's
  egress terminates TLS to GitHub release-assets; no pass is claimed. Their
  exact commands were intended to run in the PR workflow, but the workflow
  permission rejection prevents that until GPT applies `INTENDED_WORKFLOWS.patch`.
  No scanner or SBOM pass is claimed for those tools.

The updated deterministic tests and `pnpm run check` result below are recorded
against the complete intended workflow tree before the required workflow-only
reversion. On the pushed non-workflow tree, M-006 static validation and root
`check` were expected to fail closed on the absent/unhardened workflows. GPT's
later reviewer commit resolved that historical workflow state.

## First real CI and historical incomplete SBOM

The first real M-006 CI run executed against reviewer head
`4c1a237b8a767a93860e301f43d3451cb27d9f04` (Security & Dependency Gates run
`32095582384`) and all required jobs, including `security-gate`, completed
successfully. OSV-Scanner covered all 77 lockfile packages. Trivy's first run,
however, used its default behavior that suppresses development/test
dependencies, so its green job is not evidence of complete build/test dependency
coverage.

The first CycloneDX artifact is preserved as historical real evidence:

- artifact name: `vibeflow-repository-cyclonedx`;
- artifact ID: `9309810695`;
- artifact archive size: 1,039 bytes;
- artifact API digest: `sha256:e63e363ab577a2d9762615f6ad5a791ccc0924e3d393c5c4289bf88f3a3f3bbb`;
- generated successfully;
- inspected component count: **2**;
- components: `pnpm-lock.yaml` application and `typebox@1.3.6`;
- completeness verdict: **INCOMPLETE** because direct development/build/test
  dependencies were omitted by Trivy's default suppression.

The correction adds `--include-dev-deps` independently to both the Trivy
vulnerability wrapper and CycloneDX wrapper. Static validation and two mutation
tests enforce each command location separately. The corrected intended scope is
all pnpm production, development, build and test dependencies. No corrected
SBOM artifact or corrected Trivy result is claimed until CI runs the new head.

## Deterministic test counts

| Suite | Tests | Result |
| --- | ---: | --- |
| M-002 | 44 | PASS |
| M-003 | 18 | PASS |
| M-004 | 82 | PASS |
| M-005 retained | 92 | PASS |
| M-006 | 39 | PASS |
| Total | 275 | PASS |

M-005's appended acceptance reconciliation separately preserves the accepted
historical count of 87 and explains the four later build-progression tests.

## Capability ledger transitions

- `VF-REL-002 DependencyPolicy`: `NOT_STARTED` → `IMPLEMENTED`
- `VF-REL-003 ConformanceSuite`: `NOT_STARTED` → `IMPLEMENTED`
- `VF-REL-004 SBOM/DependencyRegistry`: `NOT_STARTED` → `IMPLEMENTED`
- `VF-REL-005 SBOM/Dependency Evidence`: `NOT_STARTED` → `IN_PROGRESS`

None is marked `VERIFIED` or `COMPLETE` in the M-006 snapshot. Repository-level
CycloneDX evidence is not mobile/APK release evidence. Active M-006 requires all
`VF-ENV-*` rows to remain `NOT_STARTED`. Durable mode instead enforces only that
the four accepted REL baselines do not regress and permits a successor-selected
ENV row to progress. A real M-007 REVIEW fixture advancing `VF-ENV-001` to
`IN_PROGRESS` passes CSV/YAML coherence and the retained M-006 validator.

## Authoritative pack changes

| Master file | Old SHA-256 | New SHA-256 |
| --- | --- | --- |
| `01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv` | `436f0fae02c5eb5a51ebb3819dc09f831d4d58baa3fb145fa3141706105a5036` | `5c4324f418afb6b7d069e103007d05e79b5bdb9c0e21ad5253cd9b37c7c92a79` |
| `01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml` | `79a7eb8bc5ed7d9b154ddcb5068bfcca5d86c52b0543167a606db642fa74650c` | `a1907508cc5ecd40d779cfac843f47868a1f1fd307684a7f26aa640fdab3d40b` |
| `06_HARVEST/OSS_HARVEST_REGISTRY.yaml` | `8a1611047b7584160350e47c29539670b10a9bcf97f2fd47a701f799bdd27351` | `79b491bba51ee91bdc107c67af35537b9673ff308204678cad227991c5687d60` |
| `10_IMPLEMENTATION/MISSION_DAG.yaml` | `8392c8df62225a3253027581417c361a5d459780c816661324dc3c79e4cdf6de` | `afd8e637ec0f96c8aedc748bf196dbf8d1b3977fb28ebd9f0bbbd8655491ac2a` |
| `10_IMPLEMENTATION/MISSION_REGISTER.csv` | `4dc3fc8a477711de89bd7b3fa4ab143584543e4ba3242b70b1ca1a0b6e65e3fc` | `8970ef31164ba8dbfd47d102e44fe151a6c44dcc493af7d35787d15b537e66f6` |
| `SHA256SUMS.txt` | `eea08a123e0b0db79cedcb1c57380c4c612e687eb5b29e30ba652d28a618f474` | `d3b0d74faab2db2744c26e6ab6b1983531683f86ba2454a643bb175ee91117bb` |

All 72 authoritative pack hashes verify.

## External branch-protection acceptance control

Workflow files do not protect `main`. Protection remains pending external
reviewer application after the first exact-head green M-006 run:

- require PR before merge and one approval;
- dismiss stale approvals after pushes;
- require conversation resolution;
- require status checks and branch up to date;
- forbid force pushes and deletion;
- enforce/no bypass for administrators if plan/UI supports it;
- do **not** require linear history (merge commits are intentional);
- do **not** add signed-commit requirements in M-006.

Required stable contexts:

1. `Master Build System Integrity / verify`
2. `Repository Foundation / foundation`
3. `Repository Sanitation / sanitize`
4. `Security & Dependency Gates / security-gate`

The GitHub App receives HTTP 403 for repository Actions settings and branch
protection settings, so it cannot determine whether the private-repository UI
offers “Require actions to be pinned to a full-length commit SHA” and cannot
apply protection. The GPT/user reviewer must check/enable that setting if
available. If the repository plan refuses protected branches, M-006 is
`BLOCKED`; no protection is claimed here.
