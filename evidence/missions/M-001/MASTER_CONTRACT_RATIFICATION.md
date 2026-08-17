# M-001 — Master Contract Ratification

## Identity

| Field | Value |
| --- | --- |
| Mission | M-001 — Ratify master contracts |
| Phase | 0 — Architecture Constitution |
| Starting main SHA | `23471a9be093cb4ca5b9f935d6dc09b2703b8d9c` |
| Branch | `arena/01a01112-vibeflow-greenfield` |
| Date/time (UTC) | `2026-08-17T18:59:54Z` |
| Classification | `M-001 READY FOR INDEPENDENT REVIEW` |
| M-001 status | `REVIEW` (not DONE) |
| Later missions | M-002+ remain `LOCKED`; not started |

Arena requires this automatically generated branch. Preferred name `bootstrap/m-001` was not used.

## Verdict

The Master Build System is internally coherent enough to serve as the architecture constitution for later missions. Baseline counts match `PACK_SUMMARY.json`. No semantic architecture contradiction was found. No product functionality was implemented.

## Checks A–L

| Check | Result |
| --- | --- |
| A Pack integrity | PASS |
| B Repository sanitation | PASS |
| C Source-of-truth integrity | PASS |
| D Canonical resource model | PASS |
| E Invariants | PASS |
| F State machines | PASS |
| G Event catalog | PASS |
| H Frontend ↔ backend contract | PASS |
| I Capability ledger | PASS |
| J Mission graph | PASS |
| K V1 gates | PASS |
| L Clean-room boundary | PASS |

## Command results

```text
git rev-parse HEAD (start) = 23471a9be093cb4ca5b9f935d6dc09b2703b8d9c
git branch --show-current  = arena/01a01112-vibeflow-greenfield

cd master-build-system && sha256sum -c SHA256SUMS.txt
  -> all 72 listed files OK, exit 0
  (re-checked after legitimate M-001 status/hash update; still exit 0)

bash scripts/repo-sanitize.sh
  -> Repository sanitation checks passed. exit 0

python3 scripts/validate-master-contracts.py
  -> RESULT: PASS  exit 0
  start-state mission statuses: READY=1 LOCKED=150
  end-state mission statuses:   REVIEW=1 LOCKED=150
```

Sanitation note: the original `git grep` invocation treated a `-----BEGIN` pattern as a git option, so the secret scan did not execute. The scan is now invoked with `-e` and a non-1 git-grep exit is a sanitation failure. This strengthens, and does not weaken, sanitation.

## Actual counts

| Item | Declared | Counted |
| --- | ---: | ---: |
| VibeFlow capabilities | 405 | 405 |
| Replit trace rows | 390 | 390 |
| Canonical resources | 35 | 35 |
| Invariants | 20 | 20 |
| Approved harvest entries | 35 | 35 |
| Phases | 33 | 33 |
| Missions | 151 | 151 |
| Frontend surface contracts | 13 | 13 |
| Event types | 37 | 37 |
| V1 gates | 15 | 15 |

Capability origin split: 385 `REPLIT-DERIVED-REQUIREMENT` + 20 `VibeFlow-native requirement`. All 405 statuses are `NOT_STARTED`. All 390 R2V IDs are referenced by the ledger; YAML and CSV `vf_id` sets match.

## Check notes

### C — Source of truth

Every path in `00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml` and `.ai/INDEX.yaml` exists. Repo-root INDEX and pack INDEX differ only by path prefix. `acceptance` (`V1_ACCEPTANCE.yaml`) and `verification` (`VERIFICATION_MASTER.md`) are complementary, not circular or conflicting.

### D — Resources

Exactly 35 unique canonical resources. `STATE_OWNERSHIP.yaml` names the same 35 resources in the same order. Bindings remain bindings; no resources were added.

### E — Invariants

Exactly 20 unique IDs `INV-001`..`INV-020`. Rules and enforcement references are non-empty. No Master contract was found to contradict an invariant.

### F — State machines

Seven machines (Task, Execution, Approval, Connection, Verification, Release, RecoveryRecord).

- Terminal states are subsets of declared states.
- `CANDIDATE_COMPLETE` is non-terminal on Task/Execution; `VERIFIED` is terminal and requires Verification.
- `CANCELLED`/`FAILED`/`LOST` are terminal on Execution, so cancelled/lost runs cannot become VERIFIED on the same machine.
- Recovery distinguishes `REPLAYING_EVENTS`, `RECONCILING_WORKSPACE`, `REATTACHING_PROVIDER`, `REVERIFYING`, and honest `EXECUTION_LOST`.
- Verification treats `STALE` as terminal and invalidates prior PASS on candidate revision change.

Machines declare states/terminals/rules rather than explicit edges. That is a documentation shape, not a semantic contradiction.

### G — Events

Exactly 37 unique IDs `EVT-001`..`EVT-037` and unique names. Resources resolve to canonical names or the `*Binding` family. Catalog events are lifecycle facts with `event_id` uniqueness; ordinary replay is not command re-execution.

### H — Frontend/backend

Exactly 13 unique `FE-001`..`FE-013` surfaces. All listed resources exist. The matrix rule forbids an independent authoritative state vocabulary.

Projection/wildcard event names that are not themselves catalog types (not a blocker):

`execution.status_changed`, `terminal.*`, `preview.*`, `repository.*`, `security.finding`, `entitlement.updated`, `budget.exceeded`, `organization.*`, `policy.updated`, `artifact.*`.

These are UI projections over canonical resources/events, not a second state machine.

### I — Capability ledger

405 unique `vf_id`s; required identity fields populated; Replit-derived rows remain traceable to the 390-row map; native rows remain distinguishable; no capability marked implemented.

### J — Mission graph

33 phases (`0`..`32`), 151 unique missions, acyclic, every dependency exists. At start, M-001 was the only READY mission. M-002 depends on M-001; M-003 depends on M-002; M-004 is Phase 1 and depends on M-003. After this mission, M-001 is `REVIEW` and M-002+ remain `LOCKED`.

### K — V1 gates

Exactly 15 unique `V1-001`..`V1-015`. Requirements demand evidence/suites, not feature presence alone. Security, independent verification, recovery, and provider/agent/workspace certification are represented.

### L — Clean-room

`CLEAN_ROOM_POLICY.md` and `99_REFERENCE/REPLIT_EVIDENCE_SUMMARY.md` retain Replit material as capability/interface evidence only. Implementation trees (`apps/`, `packages/`, `services/`, `adapters/`, `workers/`) still contain only seed READMEs. Historical binary/decompilation material was not inspected.

Harvest files `DO_NOT_INVENT.yaml` and `OSS_HARVEST_REGISTRY.yaml` resolve (35 unique `H-001`..`H-035`). Full harvest ratification is M-002 and was not performed.

## Mechanical corrections

1. `.ai/ACTIVE_MISSION.md` — M-000 → M-001 (REVIEW).
2. `docs/WORKSPACE_BOOTSTRAP_STATUS.md` and `README.md` — stale M-000 active-mission pointers.
3. `scripts/repo-sanitize.sh` — secret-scan invocation now uses `git grep -e` and fails if the scanner cannot run.
4. `scripts/validate-master-contracts.py` plus `tests/contract/validate-master-contracts.sh` — no-dependency consistency validator.
5. M-001 status `READY` → `REVIEW` in `MISSION_DAG.yaml` and `MISSION_REGISTER.csv`.
6. `SHA256SUMS.txt` — hashes updated only for the two status-touched pack files above. Hashes were not regenerated to hide a mismatch.

No architecture semantics, resource authorities, state machines, event types, capabilities, or V1 gates were redesigned.

## Unresolved conflicts

None that require an ADR or that block constitution ratification.

Non-blocking observations for later missions:

- Frontend projection event names listed under H may be cataloged or generated when contract codegen exists.
- `OSS_HARVEST_REGISTRY.yaml` still says versions are pinned “during Mission 001”; lockfile pinning belongs to later foundation/harvest missions (M-002/M-004). Not enacted here.
- State machines do not enumerate transition edges.

## Files changed

- `.ai/ACTIVE_MISSION.md`
- `README.md`
- `docs/WORKSPACE_BOOTSTRAP_STATUS.md`
- `scripts/README.md`
- `scripts/repo-sanitize.sh`
- `scripts/validate-master-contracts.py`
- `tests/contract/README.md`
- `tests/contract/validate-master-contracts.sh`
- `master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml`
- `master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv`
- `master-build-system/SHA256SUMS.txt`
- `evidence/missions/M-001/MASTER_CONTRACT_RATIFICATION.md`
- `evidence/missions/M-001/MASTER_CONTRACT_RATIFICATION.json`

## Confirmation

M-002 and later work were not started. This PR must not be merged by the implementation agent.
