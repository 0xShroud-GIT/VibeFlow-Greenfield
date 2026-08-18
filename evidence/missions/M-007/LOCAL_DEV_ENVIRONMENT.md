# M-007 — Local Development Environment Evidence

## Identity and acceptance boundary

| Field | Value |
| --- | --- |
| Starting `origin/main` / verified branch start | `f8b214a687944eb44b148997e6028044baf8b6b8` |
| Arena session branch | `arena/01a01576-vibeflow-greenfield` |
| Reviewer workflow-handoff head (pre-fix) | `16d79c5b705207af64c38303e168cdfb6ac81287` |
| Round-2 fix head (GPT applied imageName correction) | `3dbe9e84e21ffaf8eaac141395a9e17d039b4520` |
| Round-3/3b fix heads | `2911bc3` (blockers 1-5), `21108b3` (volume permissions) |
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

### Blocker 1 — devcontainer bootstrap fails in CI (no TTY purge, then volume permissions)

Exact-head CI on `3dbe9e8` failed in `postCreateCommand` with
`ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`: the host checkout's
`node_modules` (with pnpm store symlinks pointing at host paths) was visible
through the workspace bind mount; pnpm decided the modules dir was
incompatible, attempted to purge/recreate it, and aborted non-interactively.

Fix part 1 (canonical in both local and CI Dev Containers usage): the dev
container declares one container-local volume that shadows `node_modules` —

```json
"mounts": [
  "source=vibeflow-node-modules,target=${containerWorkspaceFolder}/node_modules,type=volume"
]
```

Exact-head CI on the first fix (`2911bc3`, run `32164179453`) proved the
purge was gone but surfaced the second part: a fresh Docker named volume is
root-owned, so the non-root container user got
`EACCES: permission denied, mkdir /workspaces/VibeFlow-Greenfield/node_modules/.pnpm`
(the bootstrap's own version checks — node v24.19.0, pnpm 11.4.0, python3,
git — all passed before the install).

Fix part 2: a host-side `initializeCommand` chowns the volume root to the
host user, which is exactly the uid the container user is aligned to by
devcontainers/ci / VS Code:

```json
"initializeCommand": "docker run --rm -u 0 -v vibeflow-node-modules:/data docker.io/library/node@sha256:934240a162082fd8b8a2f90cd5114446443f1eba1c5378f6687167ca405e6584 chown $(id -u):$(id -g) /data"
```

The throwaway chown container uses the same digest-pinned node image (already
pulled), mounts no host paths into the dev container, runs only during
host-side initialization, and never touches the host checkout's
`node_modules`. Frozen-lockfile install and the canonical bootstrap are
unchanged; postCreate bootstrap and runtime smoke then execute
non-interactively. The retained validator pins both the volume and the
initializeCommand in the active snapshot and requires an owning
later-mission declaration to change them.

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

## Round 4 — image selection / remediation (review ID 4963633347 continuation)

Exact-head CI at `21108b3` (runs `32167152736/56/43/46`) proved: foundation
(devcontainer build + non-root start + postCreate bootstrap + frozen-lockfile
install + `pnpm run check` + runtime smoke) PASS, verify PASS, sanitize PASS,
security-gate FAIL only because the dev-image Trivy scan reported real
HIGH/CRITICAL findings in the exact `node:24.19.0` bookworm image.

### Candidate evidence matrix (official Node 24.19.0 variants, resolved to immutable OCI digests)

| Variant | OCI index digest | amd64 digest | arm64 digest | git | Debian HIGH (bookworm evidence / trixie analysis) | npm findings | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `node:24.19.0` (bookworm, previous) | `sha256:934240a1…e6584` | `sha256:f6d02cf1…1055` | `sha256:7e4b2953…8099` | yes | 5 (libaprutil1 CVE-2026-34191; libpq-dev/libpq5 CVE-2025-8714, CVE-2026-6473) | 7 | tested → FAIL |
| `node:24.19.0-bookworm-slim` | `sha256:3638d9a6…fc03` | `sha256:65932751…4848` | `sha256:c133efe2…bb03` | **no** | ~0 (minimal base) | 7 | not eligible (no git; git unaddable without apt) |
| `node:24.19.0-trixie` | `sha256:66bb8d36…75c1` | `sha256:05c60dce…2ad3` | `sha256:3f734716…65c` | yes | 3 (libaprutil1 CVE-2026-34191; libpq-dev/libpq5 CVE-2026-6473) — CVE-2025-8714 fixed by trixie main 17.10 | 7 → 0 after npm removal | **selected** |
| `node:24.19.0-trixie-slim` | `sha256:0711b541…74d` | `sha256:f2925910…b486` | `sha256:8525258f…e9e` | **no** | ~0 | 7 | not eligible (no git) |
| `node:24.19.0-alpine` (3.24) | `sha256:d32cdf61…ad43` | `sha256:2a49bdf7…b43` | `sha256:0e6f1567…082` | **no** | ~0 (musl/apk base) | 7 | not eligible (no git; apk package manager; musl) |
| `node:24.19.0-forky` (Debian 14) | N/A | N/A | N/A | — | — | — | **not published** for Node 24 (docker-node `24/` contains only alpine3.23, alpine3.24, bookworm, bookworm-slim, bullseye, bullseye-slim, trixie, trixie-slim) |

Debian CVE fixed-version status (Debian security tracker, 2026-08-18):
CVE-2026-34191 libaprutil1 — bookworm fixed `1.6.3-1+deb12u1`, **trixie main
`1.6.3-3` still vulnerable** (only trixie-security `1.6.3-3+deb13u1` fixes);
CVE-2025-8714 postgresql — bookworm fixed `15.19`, **trixie main `17.10`
fixed**; CVE-2026-6473 postgresql — bookworm fixed `15.19`, **trixie main
`17.10` still vulnerable** (trixie-security `17.11` fixes). Official Debian
docker images are built from release snapshots without security-update
pockets, so a digest-pinned official image cannot carry the +deb13u1/+deb12u1
fixes.

### Selected design

- Base: `docker.io/library/node:24.19.0-trixie@sha256:66bb8d36ae1ddd72199ed235a089904874ca4079ee517936ca3adb80506a75c1`
  (amd64 `sha256:05c60dce…`, arm64 `sha256:3f734716…`, ppc64le, s390x).
- `.devcontainer/Dockerfile` (new, deterministic remediation layer):
  `FROM` the digest-pinned trixie base; `RUN rm -rf` of unused bundled npm
  (`/usr/local/lib/node_modules/npm`, `/usr/local/bin/npm`, `/usr/local/bin/npx`)
  and yarn (`/opt/yarn-v1.22.22`, `/usr/local/bin/yarn`,
  `/usr/local/bin/yarnpkg`). No apt/apk operations, no downloads, no floating
  references; corepack and git retained.
- `.devcontainer/devcontainer.json` now uses `"dockerFile": "Dockerfile"`
  (the `image` key is removed); mounts, initializeCommand (trixie digest),
  non-root users, pinned python feature and postCreate bootstrap unchanged.
- Deterministic npm-removal proof: the M-007 bootstrap (`dev-bootstrap.py`),
  runtime smoke, root `pnpm run check`, and all retained validators invoke
  only `node`, `corepack`, `pnpm`, `python3`, `git`; the `npm`/`yarn`
  executables are never invoked (repo references to "npm" are registry-
  ecosystem labels in harvest validators, not the npm CLI). Corepack provides
  pnpm/yarn shims independently of npm.

### Expected Trivy outcome and residual findings (analysis; exact-head CI to confirm)

- Node-pkg findings (brace-expansion, ip-address, tar, undici — all inside the
  removed `/usr/local/lib/node_modules/npm`) are cleared by the deterministic
  removal: Trivy's node-pkg detection is filesystem-based.
- Debian findings in the trixie base are **not clearable within M-007
  authority**: Trivy's os-pkg detection reads the dpkg status database;
  filesystem-only removal does not clear them; `apt-get purge`/`upgrade`
  is a mutable apt operation forbidden by the packet; no newer official
  Node 24.19.0 image exists (no forky variant); and every Node 24.19.0 image
  with git baked in carries the same buildpack-deps dev-package set.
  Expected residual on trixie: `libaprutil1` CVE-2026-34191 (HIGH, fixed
  only in trixie-security) and `libpq-dev`/`libpq5` CVE-2026-6473 (HIGH,
  fixed only in trixie-security). CVE-2025-8714 is fixed by trixie main 17.10.
- The packet's stop-and-report clause is therefore expected to apply: no
  M-007-permitted image selection or deterministic remediation can pass the
  unchanged HIGH/CRITICAL gate without (a) changing Node 24.19.0, (b) mutable
  apt/apk package operations, (c) new unratified tooling, or (d) weakening
  Trivy policy — each requiring owner amendment of mission authority.

### Round-4 CI evidence (head `65faf04`) and the DS-0002 correction

- `verify` PASS (run `32171671074`), `sanitize` PASS (run `32171671104`),
  `foundation` PASS (run `32171671050`): the trixie-based devcontainer
  (Dockerfile + python feature + volume + initializeCommand) builds, the
  postCreate bootstrap and `pnpm run check` succeed non-interactively, and
  the runtime smoke passes inside the exact built image.
- `Security & Dependency Gates` (run `32171671047`): the repository
  filesystem scan flagged the new `.devcontainer/Dockerfile` with
  **DS-0002 (HIGH)** — "Specify at least 1 USER command in Dockerfile with
  non-root user as argument" — because the image ran non-root only through
  devcontainer.json `remoteUser`/`containerUser`. Corrected by adding
  `USER node` to the Dockerfile (the non-root `node` user is created by the
  official image), which satisfies DS-0002 at the container level too. This
  is a hardening, not a threshold change. The dev-image Trivy scan step
  therefore did not run on `65faf04`; it runs after the corrected repo scan
  on the next head.

### Round-4 workflow handoff (exact patch)

Arena cannot write `.github/workflows/**`. The exact Round-4 correction
(replace the three `docker pull` bookworm-digest lines with the trixie
digest-pinned coordinate in `repository-foundation.yml` and
`security-and-dependency-gates.yml`) is preserved at
`evidence/missions/M-007/INTENDED_WORKFLOWS.patch`

SHA-256: `e0fab0f8b1b663eea8d44ad90e3b0df1ef46f1fa8cc476dc61e8e775bcdb3c94`
(`git apply --check` clean). GPT applies only those workflow files on the same
branch; exact-head CI then reruns the four protected contexts.

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
| M-007 | 88 | PASS |
| Total | 365 | PASS |

Round 4 (image remediation) rewrote the image-provenance mutations from the
bookworm `image` key to the trixie `dockerFile`/Dockerfile: floating FROM,
malformed digest, digest-lock mismatch, wrong semantic coordinate, missing
Dockerfile, forbidden `image` key, missing npm removal, Dockerfile containing
`apt-get`/`apk`/curl-pipe, and missing `USER node` (Trivy DS-0002) all fail
(previous rounds: 53 -> 78 -> 81 -> 87 -> 88). The counts are recorded after
the local run on this branch; the exact-head CI run re-executes all retained
suites.

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
  round-3 tree (M-007 suite 81 after the volume-permissions follow-up);
  `pnpm install --frozen-lockfile` and `pnpm run check` PASS; synthetic
  combined durable tree passes M-007 durable, M-006 durable and master
  contracts.

### Round-3 exact-head CI evidence (head `2911bc3`, runs `32164179453` / `32164179498`)

- `Master Build System Integrity / verify`: **PASS** (run `32164179653`).
- `Repository Sanitation / sanitize`: **PASS** (run `32164179507`).
- `Repository Foundation / foundation`: **FAIL** (run `32164179453`) at
  `postCreateCommand` with `EACCES` on the fresh root-owned volume (fixed by
  the initializeCommand chown above; see the re-run below).
- `Security & Dependency Gates / sbom`: **PASS** (run `32164179498`) — the
  exact dev image was built and the ephemeral dev-image CycloneDX SBOM was
  generated and uploaded:
  - artifact `vibeflow-dev-image-cyclonedx`, ID `9334786052`,
    1,319,260 bytes, archive digest `sha256:155a219433f5eedb8b2ea7d3748383d34a2e4655bd11f9f96a59d25d78519b96`
    (content SHA-256 is inside the artifact next to the SBOM).
- `Security & Dependency Gates / vulnerabilities`: **FAIL** (run
  `32164179498`) — the wrapper now executes and Trivy scanned the exact built
  image, which **correctly failed closed** on real actionable findings
  (see the stop-and-report blocker below). `secrets`, `dependency-policy`,
  `sast` all PASS; aggregate `security-gate` failed closed as designed.
### Round-3b exact-head CI evidence (head `21108b3`, the volume-permissions fix)

- `Master Build System Integrity / verify`: **PASS** (run `32167152736`).
- `Repository Sanitation / sanitize`: **PASS** (run `32167152743`).
- `Repository Foundation / foundation`: **PASS** (run `32167152756`) — the
  dev container now builds, the `postCreateCommand` bootstrap
  (`pnpm install --frozen-lockfile` + `pnpm run check`) succeeds
  non-interactively, and the step "Build dev container and run runtime smoke
  inside the exact image" passes, so the in-container runtime smoke executed
  successfully.
- `Security & Dependency Gates / security-gate`: **FAIL** (run `32167152746`)
  — the aggregate gate failed closed because the `vulnerabilities` job
  correctly fails on the real Trivy dev-image findings (stop-and-report
  blocker below). `secrets`, `dependency-policy`, `sast` and `sbom` pass
  (same pattern as run `32164179498`, where `sbom` produced artifact
  `9334786052`); the dev-image SBOM generation/upload succeeds.
- The four required contexts remain: `verify` PASS, `foundation` PASS,
  `sanitize` PASS, `security-gate` FAIL-closed on the documented image
  findings.
- Runtime smoke: **executed and passed** inside the exact built dev image
  (part of the green foundation step on `21108b3`).

### Stop-and-report blocker: dev-image Trivy findings (packet §4.3 / §8)

The exact pinned dev image `vibeflow-dev:latest` (from official
`docker.io/library/node:24.19.0@sha256:934240…e6584`, debian 12.15) fails the
locked Trivy policy with real actionable HIGH/CRITICAL findings. Per M-007
§8 ("Do not weaken security thresholds to make the dev image pass. Select/
remediate the image instead.") and §4.3 ("if the selected image cannot meet
exact Node/pnpm parity without an unratified tool/feature or unsafe mutable
bootstrap, STOP and report instead of improvising"), Arena does **not** weaken
the threshold, repin Node, or mutate the image. Findings:

- Debian (5 HIGH): `libaprutil1` CVE-2026-34191; `libpq-dev`/`libpq5`
  CVE-2025-8714, CVE-2026-6473 (bundled by the official image's
  buildpack-deps:bookworm base).
- Node/npm bundled (`/usr/local/lib/node_modules/npm/node_modules/`, 7:
  6 HIGH + 1 CRITICAL): `brace-expansion` 5.0.6 (CVE-2026-13149,
  CVE-2026-14257, CVE-2026-69152), `ip-address` 10.2.0 (CVE-2026-69192,
  SSRF), `tar` 7.5.16 (CVE-2026-59873 CRITICAL, CVE-2026-59874), `undici`
  6.26.0 (CVE-2026-12151, DoS).

Every `node:24.19.0` official variant bundles the same npm/undici packages,
so no image with exact Node 24.19.0 parity clears the gate. Remediation
options require an owner decision (out of M-007 authority): (a) authorize a
later toolchain/ADR mission to repin Node to a patched 24.19.x once released,
(b) accept a documented risk exception for the dev-only image with the
runtime non-root posture as the compensating control, or (c) otherwise
explicitly direct the next step. No threshold weakening is proposed.

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
