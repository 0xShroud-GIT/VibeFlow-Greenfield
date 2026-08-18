# M-005 — Establish schema/codegen pipeline

**Mission ID:** M-005
**Phase:** 1 — Repository Foundation
**Starting main SHA:** `7b422e0675d5200d8e63e575496d16d1b2844bc3`
**Branch:** `mission/m-005-schema-codegen`
**Final status:** REVIEW (never self-marked DONE; acceptance is external)

## Final branch head binding policy

This evidence describes the work on `mission/m-005-schema-codegen`. Acceptance
must be bound to the exact final pushed head SHA of that branch, not to this
document. Any later push invalidates a prior exact-head review.

## Mission-state transition

| Mission | Before | After |
| ------- | ------ | ----- |
| M-001   | DONE   | DONE  |
| M-002   | DONE   | DONE  |
| M-003   | DONE   | DONE  |
| M-004   | REVIEW | DONE (externally accepted, merged, post-merge verified — consumed here) |
| M-005   | LOCKED | REVIEW |
| M-006..M-151 | LOCKED | LOCKED |

Updated coherently in:

- `master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml`
- `master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv`
- `.ai/ACTIVE_MISSION.md`
- `README.md`
- `docs/WORKSPACE_BOOTSTRAP_STATUS.md`

## Tranche zero — audit remediation

### 3A. Generalized the M-004 validator

`scripts/validate-m004-foundation.py` froze the M-004 historical snapshot and
would have rejected a legitimate M-005 branch. It is now progression-aware while
every permanent foundation invariant remains enforced: Node 24.19.0 baseline,
pnpm 11.4.0, exact approved dependency pins, one root pnpm lockfile, no
npm/yarn/bun lockfiles, required workspace globs, the seven shared package
manifests, no manifests under `apps|services|workers|adapters`, `typebox` 1.x at
the exact foundation pin, strict TypeScript flags, no forbidden lifecycle
scripts, pnpm supply-chain policy, no `dangerouslyAllowAllBuilds`, no unexpected
`allowBuilds`, foundation CI presence, and the required build/typecheck/test
commands.

Mission-state logic became:

- M-001..M-003 must remain DONE;
- M-004 must be REVIEW (its own mission) or DONE (accepted), and may never
  regress to LOCKED/IN_PROGRESS after acceptance;
- while M-004 is REVIEW, every later mission must remain LOCKED;
- once M-004 is DONE the validator no longer hard-codes later missions as
  LOCKED — serial progression is owned by `validate-master-contracts.py` — but
  DAG/register agreement is still required.

Root `check` is no longer one frozen literal. Its `&&` stages are parsed and
required in order: `python3 scripts/validate-m004-foundation.py` (must be first),
then any additional legitimate gates, then `pnpm run typecheck`,
`pnpm run test`, `pnpm run build`. Removal or reordering of a required stage
fails.

Regression coverage added to `tests/contract/test_m004_foundation.py`
(47 tests total, all passing):

- historical M-004 REVIEW / M-005 LOCKED state passes;
- M-004 DONE / M-005 REVIEW passes, and M-004 DONE / M-005 IN_PROGRESS passes;
- M-004 REVIEW with M-005 active fails;
- M-004 regression to LOCKED or IN_PROGRESS after acceptance fails;
- DAG/register desync fails (for M-004 and for later missions);
- Phase 0 regression fails;
- each required root `check` stage cannot be removed, reordered, or displaced
  from first position; an extra legitimate gate is explicitly allowed.

### 3B. Closed README / mission-pointer drift

The root README still said M-003 was active. It now names M-005.

`scripts/validate-master-contracts.py` mission-pointer coherence now covers
`.ai/ACTIVE_MISSION.md`, `README.md` and `docs/WORKSPACE_BOOTSTRAP_STATUS.md`.
A pointer that names no mission, omits the active mission, describes a different
mission as active, or is missing entirely is an error. The pre-existing
ACTIVE_MISSION checks were not weakened.

Deterministic tests added to `tests/contract/test_m002_validators.py` (38 tests
total, all passing): stale README pointer fails, README naming no mission fails,
stale bootstrap-status pointer fails, missing README fails. The synthetic
serial-state fixture was extended to move all three pointers, matching what a
real mission transition does.

### 3C. Master Build System workflow trigger gap

The intended change adds `apps/**`, `services/**`, `workers/**`, `adapters/**`
to **both** the `pull_request` and main `push` path lists, and adds the two
M-005 CI steps. All existing triggers and steps are retained.

**Arena's GitHub App cannot push `.github/workflows/**`.** The change is
prepared locally and its exact content is returned at handoff for GPT to apply
through its GitHub connector before final exact-head review. No OAuth or
device-code workaround was attempted.

### 3D. Reconciled H-025

M-002 delegated the TypeBox 1.x vs 0.x choice to M-004; M-004 accepted
`typebox@1.3.6`, TypeBox 1.x, ESM. Only the current registry language was
updated to record the already-made decision. Historical M-002 evidence was not
rewritten. This is reconciliation of a delegated decision, **not** a new ADR.

The M-002 multiline-rule regression fixture for H-025 was updated so the new
two-line continuation stays structurally protected inside the parsed `rule`
value.

### 3E. Retired the public HealthSchema canary

`packages/contracts/src/index.ts` no longer exports the temporary M-004
`HealthSchema` canary; it re-exports the generated catalog. The smoke-test file
was kept but its contents now test the generated contract schemas. The M-005
validator fails if the canary reappears in the public index, the generated
artifacts, or the smoke test.

## Architecture — no new dependency

**External dependency changes: NONE.**

No PyYAML, tsx, json-schema-to-typescript, typebox-codegen,
@sinclair/typebox-codegen, Ajv or any other codegen/schema package was added.
`typebox@1.3.6` is retained as the only contracts dependency. The generator is
stdlib-only Python and reuses the repository's already-tested stdlib YAML-subset
loader from `validate-master-contracts.py`; `load_yaml_file(...)` public
behaviour is unchanged, so historical M-002 tests still work.

**pnpm-lock.yaml changed: NO.** `git diff 7b422e06 -- pnpm-lock.yaml` is empty.

## Authority model

The Master Build System remains authoritative; generated runtime contracts are
DERIVED. The generator confirms the SOURCE_OF_TRUTH_INDEX routing at run time
and fails if it changes:

| Route       | Authoritative file                              |
| ----------- | ----------------------------------------------- |
| `resources` | `02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml` |
| `states`    | `03_BACKEND/STATE_MACHINES.yaml`                |
| `events`    | `03_BACKEND/EVENT_CATALOG.yaml`                 |

No second hand-maintained list of these values exists. No Replit evidence is
parsed. No authority is derived from README or evidence files.

### Authoritative inputs and SHA-256

```
967cda17f559e0ccfb3e59ea01add1a76440fe93e9a499fc3e35b31e9090da68  master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml
5575eef27cef87cffa63aae5f6e2c619a517e43c5277a9c33487bfbea566c06d  master-build-system/02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml
4ecb50c4d3bb86fd1be59fa6d3114f454cacf4e38609005d0da4c9699ea1a5e2  master-build-system/03_BACKEND/STATE_MACHINES.yaml
cf5aa50943046bcfa21d59a88d2bb4057ed7dc04c0e05b8872b756dc9003d203  master-build-system/03_BACKEND/EVENT_CATALOG.yaml
```

Each value matches both the current file bytes and the corresponding
`SHA256SUMS.txt` pack entry.

## Generated artifact inventory

```
f520845b114008e185d7a18398efb3f0d2dee9b6e4d7ea4cecabb1ada7c21931  packages/contracts/src/generated/catalog.ts
11f20b0adb1354b8b444df111d3f731c1733d8cd3ede90eefc81df65fdd7cd76  packages/contracts/generated/catalog.schema.json
74cb60f5577d6cf152de99d39f8746bb0fe9f53c388cfa30ef9e911c98ad96c9  packages/contracts/generated/catalog.manifest.json
```

No other generated file exists; the validator fails on any unexpected file in
the generated trees.

**Counts: 35 canonical resources / 7 state machines / 37 events.**

- `catalog.ts` — GENERATED FILE — DO NOT EDIT. Exposes `CANONICAL_RESOURCES`,
  `CanonicalResourceNameSchema` / `CanonicalResourceName`, `STATE_MACHINE_NAMES`,
  `StateMachineNameSchema` / `StateMachineName`, per-machine
  `<Machine>StateSchema` / `<Machine>State` and `<Machine>TerminalStateSchema` /
  `<Machine>TerminalState`, `EVENT_IDS`, `EVENT_NAMES`, `EventIdSchema` /
  `EventId`, `EventNameSchema` / `EventName`, and `EVENT_CATALOG` in canonical
  order with `id`, `name`, `resource`, `producer`, `envelope`, `durable`. No
  event payload fields are invented.
- `catalog.schema.json` — JSON Schema 2020-12, stable `$id`
  `urn:vibeflow:contracts:catalog:v1`, `$defs` for `CanonicalResourceName`,
  `StateMachineName`, each state enum, each terminal-state enum, `EventId` and
  `EventName`.
- `catalog.manifest.json` — `schema_version`, generator, authoritative source
  paths, SHA-256 of each input, resource/state-machine/event counts and the
  generated artifact inventory. No timestamp, no self-referential output hashes.

**TypeBox exact pin:** `typebox@1.3.6` (TypeBox 1.x, ESM).
**JSON Schema draft:** 2020-12.

Raw schemas are JSON-Schema-compatible literal structures; every TypeScript type
is derived from its schema with TypeBox `Static<>` inference, verified by
compilation. No parallel handwritten union vocabulary is maintained — the
validator rejects any exported type not derived from a schema.

## Determinism proof

- `scripts/generate-contracts.py --check` performs no writes; it regenerates the
  expected bytes in memory and compares against tracked output. Verified with
  byte and mtime comparison, including when output is stale.
- Two consecutive generation runs produced byte-identical artifacts (identical
  SHA-256 for all three files), and the tracked artifacts equal a fresh
  generation.
- Output contains no timestamps, machine paths, hostnames, random UUIDs or clock
  values; a test asserts their absence.

## Verification results

| Check | Result |
| ----- | ------ |
| `git diff --check` | clean |
| `bash scripts/repo-sanitize.sh` | PASS |
| `sha256sum -c SHA256SUMS.txt` (72 entries) | 72/72 OK |
| `validate-master-contracts.py` | PASS |
| `validate-harvest-registry.py` | PASS (35 entries) |
| `validate-threat-model.py` | PASS |
| `validate-m004-foundation.py` | PASS (mission=M-004:DONE) |
| `validate-m005-contract-codegen.py` | PASS |
| `test_m002_validators.py` | OK — 38 tests |
| `test_m003_security_contracts.py` | OK — 18 tests |
| `test_m004_foundation.py` | OK — 47 tests |
| `test_m005_contract_codegen.py` | OK — 61 tests |
| `generate-contracts.py --check` | PASS |
| `node --version` | v24.19.0 |
| `pnpm --version` | 11.4.0 |
| `pnpm install --frozen-lockfile` | PASS |
| `pnpm run contracts:check` | PASS |
| `pnpm run check` | PASS (foundation → contracts:check → typecheck → test → build) |
| TypeBox smoke tests | 8/8 pass against generated schemas |
| `git diff 7b422e06 -- pnpm-lock.yaml` | empty (no lockfile change) |

No old test suite was weakened to make new code pass. The M-002 and M-004 suites
grew (34→38 and 28→47) by adding coverage, not by relaxing assertions.

## Scope exclusions

The master pack defines canonical resource names, state machines and event
catalog metadata. It does **not** yet define complete runtime payload schemas
for every command and event, nor a complete authoritative error-code catalog.

> The M-005 pipeline is capable of generating future command/event/error-code
> contracts once authoritative definitions exist; M-005 does not manufacture
> missing domain authority.

Accordingly M-005 did not invent: Project/Task/etc persistence schemas, REST
request/response payloads, command payload fields, event payload fields, error
codes, or database schemas. No IAM/auth work, no M-006 security tooling, no
M-007 dev environment work was started. The validator enforces these exclusions.

## Capability-ledger review

Reviewed all 16 REL/ENV-selected rows: `VF-REL-001`..`VF-REL-011` and
`VF-ENV-001`..`VF-ENV-005`.

The REL rows verify against "SBOM/signature/provenance/reproducible-build/release
gates" and cover clean-room policy, dependency policy, conformance suite, SBOM
and dependency evidence, runtime compatibility, mobile/OTA/native signed release.
The ENV rows verify against "Environment parsing/port/dependency reproducibility
tests" and cover project runtime descriptors, dependency capability, port
capability manifests, project instruction artifacts and environment definitions.

**No status changed. All 405 product capability statuses remain `NOT_STARTED`.**
No existing row clearly and specifically represents this repository's contract
codegen pipeline, and no row's verification gate is satisfied by schema tooling
alone. Per STATUS_PROTOCOL.md, product capability is not complete merely because
schema tooling exists, and no bulk marking was performed.

## Pack hashes changed

Three authoritative files changed, and only their `SHA256SUMS.txt` entries were
updated:

- `06_HARVEST/OSS_HARVEST_REGISTRY.yaml` (H-025 reconciliation)
- `10_IMPLEMENTATION/MISSION_DAG.yaml` (M-004 DONE, M-005 REVIEW)
- `10_IMPLEMENTATION/MISSION_REGISTER.csv` (M-004 DONE, M-005 REVIEW)

No other authoritative master-build-system file was modified. All 72 pack hashes
verify.

## ADR status

**ADR required: NO.** No architecture decision changed. H-025 records a decision
already made and delegated at M-002 and taken at M-004. The contracts-first,
JSON-Schema-first, derived-types architecture is the pre-existing ratified
position.

## CI

No CI run IDs are claimed. The workflow change that adds the M-005 steps and the
`apps|services|workers|adapters` triggers could not be pushed by Arena and is
handed to GPT for application. Actual CI conclusions must be read from the PR
after that change lands; expected CI is not reported here as real CI.
