# M-007 — Local Development Environment Evidence

## Identity and acceptance boundary

| Field | Value |
| --- | --- |
| Starting `origin/main` / verified branch start | `f8b214a687944eb44b148997e6028044baf8b6b8` |
| Arena session branch | `arena/01a01576-vibeflow-greenfield` |
| Reviewer workflow-handoff head (pre-fix) | `16d79c5b705207af64c38303e168cdfb6ac81287` |
| Round-2 fix head (GPT applied imageName correction) | `3dbe9e84e21ffaf8eaac141395a9e17d039b4520` |
| Mission state at branch head | `M-001..M-006 DONE`; `M-007 REVIEW`; `M-008..M-151 LOCKED` |
| ADR | Not required — implementation stays inside the ratified M-004/M-006 policy and H-023 |

Round 3 (review ID 4963633347) is recorded below: the devcontainer bootstrap
no-TTY purge, the non-executable image wrappers, and the three durable-mode
gaps (feature registry freeze, silent runArgs expansion, user-field removal
fallback to root). No workflow edits were required this round; the round-2
imageName correction is fully applied at `3dbe9e8`.

This revision records the Arena response to GPT review request-changes
(review ID 4963221835): the exact-head CI workflow defect (`devcontainers/ci`
`imageName`), the active non-root validator gap, and durable-extension
ownership enforcement. All three fixes are implemented below in non-workflow
files plus a regenerated `INTENDED_WORKFLOWS.patch`; Arena did not modify
`.github/workflows/**`.

Arena binds this session to `arena/01a01576-vibeflow-greenfield`; it cannot use
a different branch name. Acceptance must bind to the exact final pushed head
reported in the PR/handoff, not to a SHA embedded in this appendable evidence
document. Any later push invalidates an earlier exact-head review and requires
all required checks again. M-007 is never marked `DONE` on the builder branch
and must not be merged by the builder.

## Successor consumption of M-006

M-006 was externally accepted and merged at `f8b214a`. Per the frozen M-007
packet, the M-007 branch consumes that acceptance: `MISSION_DAG.yaml`,
`MISSION_REGISTER.csv`, `.ai/ACTIVE_MISSION.md`, `README.md` and
`docs/WORKSPACE_BOOTSTRAP_STATUS.md` transition M-006 to `DONE` and M-007 to
`REVIEW`. The retained M-006 validator runs in its durable mode on this branch
(`RESULT: PASS`), and its mutation suite was made status-relative so the
accepted M-006 active-snapshot tests reconstruct the historical M-006-active
tree instead of depending on the current tree state.

## Dev-container image provenance (immutable)

| Field | Value |
| --- | --- |
| Semantic coordinate | `docker.io/library/node:24.19.0` |
| OCI index digest (pinned) | `sha256:934240a162082fd8b8a2f90cd5114446443f1eba1c5378f6687167ca405e6584` |
| Media type | `application/vnd.oci.image.index.v1+json` |
| amd64 image digest | `sha256:f6d02cf1353049cf3658e6ce9ec03c6877a6479495f122062d195e2279d01055` |
| arm64/v8 image digest | `sha256:7e4b2953088599075c288871d109e23bc7a33384b96ca443a7cfb7b5c318b099` |
| ppc64le image digest | `sha256:56c4cadee33f1eff8ace75854383652bcf9584319747bb2373e010ce86e00989` |
| Upstream source | https://github.com/nodejs/docker-node |
| License | MIT (docker-node project and Node.js runtime; Debian base under component licenses) |
| Registry publish date | 2026-08-05 |
| Contains | node `24.19.0`, corepack (bundled with the Node dist), git, yarn 1.22.22 (unused) |
| Python3 | Not present in the base image (confirmed from image layer history); provided by the pinned feature below |

The official Node image installs node from `nodejs.org` with GPG verification
inside its immutable build history (layer evidence recorded from the Docker Hub
API). Both x86-64 and arm64 manifests are present, so the environment is
supported on both architectures.

## Feature provenance (immutable)

| Field | Value |
| --- | --- |
| Feature | `ghcr.io/devcontainers/features/python` |
| Version | `1.8.0` (semantic tag `:1`) |
| Digest-pinned reference | `ghcr.io/devcontainers/features/python@sha256:fbcad6955caeecc5ad3f7886baf652e25cba5225a6c4c2287c536de2e5607511` |
| Upstream source | https://github.com/devcontainers/features/tree/main/src/python |
| License | MIT |
| Options | `{"version": "os-provided", "installTools": false}` |
| Purpose | Provides Debian-bookworm os-provided `python3` required by all repository-owned stdlib validators/tests. The feature release is immutable by digest; its install behavior is fixed by that release. |

The digest above matches the `devcontainer-lock.json` published by the official
`devcontainers/images` repository for the python feature at version 1.8.0.
Digest-pinned feature references (`ref@sha256:...`, tag-less) are valid OCI
feature references per the Dev Containers spec; the VS Code UI lints them as
suspicious but the devcontainer CLI builds them correctly. This is documented
rather than worked around, because the mission requires immutable feature
pinning.

## Environment shape (active M-007 snapshot)

`.devcontainer/devcontainer.json` (the single portable environment description)
plus `infrastructure/dev/dev-environment-policy.json` (the provenance/policy
lock — explicitly not a second environment-description protocol):

- non-root dev user `node` (`remoteUser`/`containerUser`);
- `privileged: false`, no `runArgs`, no `containerEnv`/`remoteEnv`;
- one canonical container-local volume mount:
  `source=vibeflow-node-modules,target=${containerWorkspaceFolder}/node_modules,type=volume`
  (shadows the host checkout's `node_modules` so
  `pnpm install --frozen-lockfile` runs non-interactively against a fresh
  container-local modules dir — fixes `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`
  — without mutating the host developer's `node_modules`);
- no other mounts (no Docker-in-Docker, no docker-socket or host-credential
  mounts, no SSH-agent/cloud-credential forwarding, no extra capabilities,
  no securityOpt weakening);
- no forwarded ports, no `dockerComposeFile`, no `.devcontainer/Dockerfile`;
- no product/service ports or containers started by this mission;
- `postCreateCommand: python3 scripts/dev-bootstrap.py`.

## Toolchain parity

Node.js `24.19.0`, pnpm `11.4.0` (corepack path), TypeScript `6.0.3`,
Turborepo `2.10.6`, Vitest `4.1.7`, TypeBox `1.3.6`; python3 (os-provided),
git and corepack required. No repin/upgrade of any ratified version; no new
package manager or application dependency.

## Bootstrap and doctor

- `pnpm run dev:doctor` → `python3 scripts/dev-doctor.py`: fast, network-free
  precondition report (no environment modification).
- `pnpm run dev:bootstrap` → `python3 scripts/dev-bootstrap.py`: single
  repository-owned bootstrap — verify required tools, enable the corepack path
  (user-writable fallback for the non-root `node` user), verify exact
  node/pnpm versions, `pnpm install --frozen-lockfile`, `pnpm run check`.
- `scripts/dev-runtime-smoke.py`: exact runtime smoke proving
  `node --version == v24.19.0`, `pnpm --version == 11.4.0`, `python3` works,
  `git` works; runnable inside the dev container (and in CI via
  `devcontainers/ci`).
- All three scripts are stdlib-only and invoke subprocesses with explicit argv
  (never `shell=True`); the retained validator enforces this with AST checks.
- `pnpm run check` remains network-free and deterministic; container pulls,
  vulnerability-DB downloads and runtime image scans belong to CI/runtime
  wrappers only.

## Retained validator: active snapshot vs durable policy

`scripts/validate-m007-local-dev.py` (retained after M-007) auto-selects:

- **Active M-007 snapshot** (M-007 READY/IN_PROGRESS/REVIEW): exact accepted
  initial environment shape — both `remoteUser == "node"` and
  `containerUser == "node"` are **required** (missing or wrong value fails),
  the canonical node_modules volume is **required** (its removal or any extra
  mount fails), zero durable extensions allowed, exactly the python feature,
  exact image/feature/toolchain provenance, no ports/privilege/host-network,
  exact 405-capability status snapshot (only `VF-ENV-005` advances),
  mission/ledger synchronization (M-001..M-006 DONE, M-007 active, M-008+
  LOCKED), master-pack hash integrity.
- **Durable later-mission mode** (M-007 DONE): later owning missions may add
  ports, additional digest-pinned registered features, benign env metadata,
  mounts, runArgs, service containers, or a different explicit non-root dev
  user **only** through explicit `durable_extension_policy` extension entries
  (mission_id + rationale + exact declared values) **owned by the actually
  active later mission** — an entry belonging to another mission authorizes
  nothing, and historical extensions from already-completed later missions
  remain valid. Both user fields must remain explicitly present and non-root
  (missing/null/empty/root/UID-0 always fail; declarations never override the
  permanent root ban). Permanently retained: immutable provenance, no raw
  secrets, no privileged/docker-socket/host-network expansion, exact toolchain
  agreement, frozen-lockfile installation, mission/ledger synchronization, Dev
  Containers as the adopted descriptor.

This intentionally avoids the earlier M-006 mistake of freezing the entire
future workflow/environment shape.

## Workflow-permission blocker (Arena handoff rule)

Arena cannot write `.github/workflows/**`. GPT applied the three original
workflow handoff commits (`4896433`, `c977c15`, `16d79c5`) on the branch,
which are the current workflow state.

### Exact-head CI defect and the workflow correction

Exact-head CI on `16d79c5` failed in both dev-container build steps:

- Repository Foundation run `32158344344`: job `foundation` failed at
  "Build dev container and run runtime smoke inside the exact image".
- Security & Dependency Gates run `32158344311`: jobs `vulnerabilities` and
  `sbom` failed at "Build exact dev container image"; aggregate
  `security-gate` failed closed as required.

Root cause verified from the pinned devcontainers/ci source
(`513af61f4de4f75d37e4438f184ba4358f0fc1ca`, `github-action/dist/index.js`):
when `imageTag` is unset it defaults to `'latest'` and `buildImageNames`
returns `` `${imageName}:${tag}` ``, so `imageName: vibeflow-dev:smoke`
becomes the invalid reference `vibeflow-dev:smoke:latest`
(`invalid reference format`). The digest pull before the build succeeded.

Correction (exact intended workflow diff preserved at
`evidence/missions/M-007/INTENDED_WORKFLOWS.patch`, regenerated from the
current workflow state):

- `repository-foundation.yml` and `security-and-dependency-gates.yml`:
  `imageName: vibeflow-dev:smoke` → `imageName: vibeflow-dev`
  (devcontainers/ci then tags the local image `vibeflow-dev:latest`).
- `security-and-dependency-gates.yml`: explicit
  `env: DEV_IMAGE: vibeflow-dev:latest` on the Trivy scan and dev-image SBOM
  steps so the wrappers and workflow agree on the exact resulting local tag.
- No floating base image (the base stays digest-pinned in `devcontainer.json`);
  no weakened security settings; no registry push (`push: never`).

New patch SHA-256: `af48f2445516229bb91d23c38a9086daaf0979df1ca3c7fd122194089457ecf6`
(`git apply --check` passes against the current tree). The wrappers now default
`DEV_IMAGE=${DEV_IMAGE:-vibeflow-dev:latest}`.

Until GPT applies this correction, the pushed tree intentionally keeps the
pre-correction workflows (Arena cannot write workflows), so the dev-image CI
evidence below is **intended** — validated statically, against the
devcontainers/ci source, and against the patched tree in a sandbox — not yet
executed on the pushed head.

### Intended CI evidence (under existing jobs, no new required contexts)

- `Master Build System Integrity / verify`: `validate-m007-local-dev.py` and
  `test_m007_local_dev.py` steps.
- `Repository Foundation / foundation`: `docker pull` of the exact base image
  by digest; `devcontainers/ci@513af61f4de4f75d37e4438f184ba4358f0fc1ca`
  (`v0.3.1900000450`, `push: never`, `imageName: vibeflow-dev`) builds the dev
  container from the digest-pinned descriptor (local tag `vibeflow-dev:latest`)
  and runs `scripts/dev-runtime-smoke.py` inside it.
- `Security & Dependency Gates / vulnerabilities`: rebuild the exact dev
  image, then `scripts/security/scan-dev-image.sh` (`DEV_IMAGE:
  vibeflow-dev:latest`) — locked Trivy image scan (`--scanners vuln,misconfig
  --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`), same policy as
  the M-006 repository scan.
- `Security & Dependency Gates / sbom`: rebuild the exact dev image, then
  `scripts/security/generate-dev-image-sbom.sh` (`DEV_IMAGE:
  vibeflow-dev:latest`) — ephemeral CycloneDX dev-image SBOM (separate from
  the repository dependency SBOM) plus content SHA-256, uploaded with the
  already-pinned `actions/upload-artifact`.
- Retained evidence remains green: full-history Gitleaks, Semgrep, dependency
  policy, repository dependency SBOM, and the four protected contexts
  (`verify`, `foundation`, `sanitize`, `security-gate`).

`devcontainers/ci` is registered in `security/ci-toolchain.lock.json`
(commit SHA `513af61f4de4f75d37e4438f184ba4358f0fc1ca`, version
`0.3.1900000450`, rationale recorded) so the patched tree passes the retained
M-006 durable gate. The intended correction was validated by applying it to a
sandbox copy of the branch: M-006 validator `RESULT: PASS` (action_uses 8),
master contracts `RESULT: PASS`, M-007 validator `RESULT: PASS`.

## Round 3 review fixes (review ID 4963633347)

Exact-head CI at `3dbe9e8` (Repository Foundation run `32162692250`, Security &
Dependency Gates run `32162692252`) proved three runtime defects; the durable
validator had three forward-compatibility gaps. All five blockers were fixed
in non-workflow files; no workflow edits were required.

### Blocker 1 — devcontainer bootstrap fails in CI (no TTY purge)

`postCreateCommand` (`scripts/dev-bootstrap.py`) ran `pnpm install
--frozen-lockfile` inside the container while the host checkout's
`node_modules` (with pnpm store symlinks pointing at host paths) was visible
through the workspace bind mount; pnpm decided the modules dir was
incompatible, attempted to purge/recreate it, and aborted non-interactively
with `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`.

Fix (smallest standards-compliant arrangement, canonical in both local and CI
Dev Containers usage): the dev container now declares one container-local
volume that shadows `node_modules` —

```json
"mounts": [
  "source=vibeflow-node-modules,target=${containerWorkspaceFolder}/node_modules,type=volume"
]
```

Inside the container, pnpm installs against a fresh container-local modules
dir (no host-store symlinks, no removal decision, no TTY needed); the host
developer's `node_modules` is never touched. Frozen-lockfile install and the
canonical bootstrap are unchanged; the postCreate bootstrap and the runtime
smoke then execute non-interactively.

### Blocker 2 — security wrappers not executable

`scripts/security/scan-dev-image.sh` and
`scripts/security/generate-dev-image-sbom.sh` were tracked mode `100644`; CI
failed with exit 126 / Permission denied. Both are now `100755`, and the
retained validator fails any future mode regression (`os.access X_OK`).

### Blocker 3 — durable feature extensions were impossible

The durable policy check required exactly one (python) feature registration,
freezing the M-007 feature shape. Now: active M-007 still requires exactly the
python feature and zero extensions; durable mode retains python and allows
additional Dev Container Features only when each is registered in the
policy/provenance structure, digest-pinned with exact options, and owned by a
durable extension entry whose `mission_id` is the active later mission or an
already-completed later mission (historical extensions remain; an unrelated or
future mission authorizes nothing).

### Blocker 4 — durable runArgs could expand silently

Durable mode now requires any non-empty `runArgs` to be declared by an
extension owned by the active later mission (exact value + rationale).
Permanent bans (`--privileged`, host networking, `--cap-add`/`--security-opt`,
docker-socket/host-credential/ssh-agent) are enforced independently and can
never be authorized by a declaration.

### Blocker 5 — durable user-field removal could fall back to root

Durable mode now requires both `remoteUser` and `containerUser` to remain
explicitly present and non-root (missing, null, empty, `root` or `0` always
fail); changing either away from `node` requires an exact owning-active-mission
declaration; the permanent root ban is never overridable.

### Round-3 mutation coverage added (M-007 suite 53 → 78)

- Blocker 1: active requires exactly the node_modules volume (removal/extra
  mount fails); real repo carries the canonical volume.
- Blocker 2: non-executable wrapper fails; real repo wrappers executable.
- Blocker 3: active extra feature fails; durable feature without declaration
  fails; durable feature owned by wrong mission fails; floating feature fails;
  unregistered feature fails; correctly registered + digest-pinned + correctly
  owned extra feature passes.
- Blocker 4: undeclared safe runArgs fail; wrong-mission declaration fails;
  declared `--privileged` / `--network=host` / docker-socket runArgs still
  fail; owned safe runArgs pass.
- Blocker 5: missing/null/empty/root/UID-0 user fields fail in durable; user
  change declared by wrong mission fails; both-user change with correct owning
  declaration passes.

A synthetic combined durable tree (M-007 DONE, M-008 REVIEW with git feature +
safe runArgs + non-root user change, all declared and owned by M-008) passes
the M-007 durable validator, the retained M-006 durable gate, and master
contracts — demonstrating the forward-compatibility contract.

## Capability ledger transitions

- `VF-ENV-005 Environment Definition`: `NOT_STARTED` → `IN_PROGRESS`
  (CSV and YAML synchronized).

Rationale: M-007 establishes the adopted Dev Containers environment-definition
foundation; provider/Nix mapping and WorkspaceBinding integration remain
future work. Unchanged at `NOT_STARTED`: `VF-ENV-001..004`, `VF-REL-006..011`
and all unrelated release/product capabilities; the M-006 REL baselines
(`VF-REL-002..005`) are unchanged. No capability is claimed `IMPLEMENTED`,
`VERIFIED` or `COMPLETE` in M-007.

## Master pack changes

| Master file | Old SHA-256 | New SHA-256 |
| --- | --- | --- |
| `01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv` | `5c4324f418afb6b7d069e103007d05e79b5bdb9c0e21ad5253cd9b37c7c92a79` | `f84dd0e25ec345da0c392e9ca9e31c83bc19269d1c5f9b1d1d887fa87100babd` |
| `01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml` | `a1907508cc5ecd40d779cfac843f47868a1f1fd307684a7f26aa640fdab3d40b` | `7e5cf12ffb6cae0be98b72a7620f362862dd8952145266055574705045e906a9` |
| `10_IMPLEMENTATION/MISSION_DAG.yaml` | `afd8e637ec0f96c8aedc748bf196dbf8d1b3977fb28ebd9f0bbbd8655491ac2a` | `fa14b5d514715fa309e8ab921b480fac468bd22117b8be1c464371f50d14ffd7` |
| `10_IMPLEMENTATION/MISSION_REGISTER.csv` | `8970ef31164ba8dbfd47d102e44fe151a6c44dcc493af7d35787d15b537e66f6` | `7dc173d2853c36d374d12e7703a7d20cf1a3767544210e2198ed4d8a1c362961` |

All 72 authoritative pack hashes verify on the branch
(`sha256sum -c SHA256SUMS.txt`).

## Deterministic test counts

| Suite | Tests | Result |
| --- | ---: | --- |
| M-002 | 44 | PASS |
| M-003 | 18 | PASS |
| M-004 | 82 | PASS |
| M-005 retained | 92 | PASS |
| M-006 retained (status-relative) | 41 | PASS |
| M-007 | 78 | PASS |
| Total | 355 | PASS |

Round 3 grew the M-007 suite from 53 to 78 tests: Blocker-1 node_modules
volume exactness (removal/extra-mount fail), Blocker-2 wrapper exec-bit
regression, Blocker-3 durable feature ownership (5 FAIL + 1 PASS), Blocker-4
durable runArgs ownership (6 FAIL + 1 PASS), and Blocker-5 durable user-field
presence (6 FAIL + 1 PASS). The counts are recorded after the local run on
this branch; the exact-head CI run re-executes all retained suites.

## Actual verification recorded before this push

No expected CI result is represented as actual CI. At this evidence revision:

- Exact-head CI on `16d79c5` (runs `32158344344`, `32158344311`) failed as
  recorded above: the dev-container build steps rejected
  `vibeflow-dev:smoke:latest`. All other jobs in those runs (secrets,
  dependency-policy, sast; pull-by-digest, repository scans) succeeded.
- Static validators on the branch: M-007 (`RESULT: PASS`, mode active),
  master contracts, M-004 foundation, M-005 codegen, M-006 security gates,
  harvest registry, threat model, and `contracts:check` — all PASS.
- Mutation suites: M-002 44, M-003 18, M-004 82, M-005 92, M-006 41,
  M-007 53 — all PASS (330 total).
- `scripts/repo-sanitize.sh`: PASS.
- `pnpm install --frozen-lockfile` and `pnpm run check` on the Arena host:
  PASS (host runs node v22.22.3; pnpm warns "Unsupported engine node 24.x"
  as expected. CI runs node 24.19.0, so the warning does not appear there).
- `pnpm run dev:doctor` / `python3 scripts/dev-runtime-smoke.py` on the
  Arena host: FAIL closed on `node v22.22.3` (expected — the host does not
  reproduce the ratified toolchain; the scripts prove exactness rather than
  reporting a pass).
- The workflow correction was validated statically: root cause confirmed from
  the pinned devcontainers/ci source; the intended corrected workflows pass
  the retained M-006 durable gate, master contracts and the M-007 validator
  in a sandbox.
- Round-3 local re-run: all validators and suites above re-executed on the
  round-3 tree (M-007 suite 78); `pnpm install --frozen-lockfile` and
  `pnpm run check` PASS; synthetic combined durable tree passes M-007 durable,
  M-006 durable and master contracts.
- Exact dev-image pull, in-container runtime smoke, Trivy dev-image scan and
  dev-image CycloneDX SBOM: **not claimed until exact-head CI executes them**
  on the round-3 head. The round-2 `INTENDED_WORKFLOWS.patch` correction was
  fully applied by GPT at `3dbe9e8`; round 3 requires no workflow change.

## Deviations and recorded risks

- **Round-3 CI defects (now fixed)**: (1) devcontainer bootstrap aborted with
  `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY` because the host checkout's
  `node_modules` was visible through the workspace bind mount; fixed with the
  canonical container-local `vibeflow-node-modules` volume (container-only,
  host files untouched). (2) both image-evidence wrappers were tracked
  `100644` and failed with exit 126; fixed to `100755` with validator
  enforcement.
- **Exact-head CI defect (workflow `imageName`)**: devcontainers/ci defaults
  `imageTag` to `latest` and joins `` `${imageName}:${tag}` ``, so the
  original `imageName: vibeflow-dev:smoke` produced `vibeflow-dev:smoke:latest`
  (`invalid reference format`). Corrected to `imageName: vibeflow-dev`
  (local tag `vibeflow-dev:latest`) with explicit wrapper agreement. This
  correction is workflow-only and preserved as exact evidence for GPT.
- **Python feature digest-ref lint**: VS Code's devcontainer JSON linter flags
  tag-less digest feature references as invalid characters although the
  devcontainer CLI builds them correctly (upstream
  microsoft/vscode-remote-release#11241). Documented; immutable pinning wins.
- **Trivy image misconfig on root default**: the official node image's default
  user is root; the dev container runs as `node` through `remoteUser`/
  `containerUser`. The intended dev-image scan uses `--scanners vuln,misconfig`
  and the same HIGH/CRITICAL/actionable thresholds as the M-006 repository
  scan. If the image-level misconfiguration gate flags the image default user
  at exact-head CI, the finding is reported as-is rather than weakening the
  threshold; the runtime non-root posture is the control and remediation is
  selected per the mission's stop-and-report rule.
- **Runtime evidence is CI-bound**: docker, the exact dev image, Trivy and the
  devcontainer CLI are unavailable in the Arena sandbox, so image pull,
  runtime smoke, Trivy image scan and dev-image SBOM results become actual
  only when exact-head CI executes them on the round-3 head. No scanner/image
  result is claimed before that.
- **Durable security posture**: privileged mode, docker-socket mounts, host
  networking and raw secrets are permanently banned in both validator modes;
  a later mission that genuinely requires them must amend this lock and the
  validator through explicit reviewed authority.

## External branch-protection acceptance control

Unchanged from M-006: workflow files do not protect `main`; protection and the
"require actions to be pinned to a full-length commit SHA" setting remain
pending external reviewer application. The four required stable contexts are
unchanged: `Master Build System Integrity / verify`,
`Repository Foundation / foundation`, `Repository Sanitation / sanitize`,
`Security & Dependency Gates / security-gate`.
