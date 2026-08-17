# M-002 — Dependency / Harvest Registry Ratification

## Identity

| Field | Value |
| --- | --- |
| Mission | M-002 — Ratify dependency/harvest registry |
| Phase | 0 — Architecture Constitution |
| Authoritative dependency | `M-002 depends_on M-001` (M-001 independently accepted and merged) |
| Starting main SHA | `ffbb9421417b871ae84883e24cd4d95ffead30cd` |
| Branch | `arena/01a01122-vibeflow-greenfield` (Arena-generated; required) |
| Verification date | 2026-08-17 |
| Classification | `M-002 READY FOR INDEPENDENT REVIEW` (revision 2 — independent-review amendments applied) |
| M-001 status | `DONE` (canonical terminal state per `10_IMPLEMENTATION/STATUS_PROTOCOL.md`) |
| M-002 status | `REVIEW` |
| M-003+ status | `LOCKED`; not started |

## Review amendments (revision 2)

Independent review required changes; all applied on the same branch/PR without merging:

1. **CI:** `.github/workflows/master-build-system-integrity.yml` now executes, after pack hash verification: `python3 scripts/validate-master-contracts.py`, `python3 scripts/validate-harvest-registry.py`, `python3 tests/contract/test_m002_validators.py` — each fails the workflow on non-zero exit. Trigger paths extended to `scripts/**`, `tests/**`, `.ai/**` so validator/test changes always run the integrity job.
2. **LICENSE_POLICY ↔ registry contract closed by strengthening the registry:** every H-001..H-035 entry now records `use`, `ownership`, `upgrade_policy` and `replacement_strategy` alongside the existing `version` (approved line) and `license` (classification) — the full data set LICENSE_POLICY.md demands. All pre-existing fields, decisions and rules preserved verbatim.
3. **Official-source validation hardened:** generic `github.com` is no longer accepted as provenance. Each H-ID validates against its exact upstream identity — exact `owner/repo` for GitHub sources (case-insensitive) or the exact official domain (www-variant tolerated). Deterministic tests prove a fake repository hosted on github.com (`attacker/TypeScript-mirror`) and a same-slug/wrong-owner repo (`vercel-mirror/turborepo`) both fail.
4. Evidence, PR description and pack hashes updated; all commands re-run.

## Verdict

All 35 registry entries (H-001..H-035) were independently verified against official upstream sources. **28 PASS, 7 PASS with recorded findings/corrections, 0 FAIL.** The ADOPT → WRAP → BRIDGE → EXTEND → BUILD priority is preserved; no BUILD entry exists; no dependency was replaced. Five entries carry explicit review-required license classifications; three maintenance/security observations were recorded for later missions. No finding invalidates the approved architecture, so **no architecture ADR was required or created**.

## Method

Registry ratification ≠ repository dependency pinning. This mission ratified technology choices, version lines and license classifications. Exact installable package pins are deferred to M-004 (Repository Foundation), which creates the first lockfile; **no lockfile existed during M-001/M-002 and none is claimed** — the stale registry wording asserting "Mission 001" lockfile pinning was corrected mechanically in `OSS_HARVEST_REGISTRY.yaml` (policy), `TECHNOLOGY_BASELINE_2026-08-17.md`, and `LICENSE_POLICY.md`, without falsifying history.

Evidence hierarchy used: official specification → official documentation → official repository/release metadata → official license file → official package registry (npm/PyPI/pkg.go.dev for package-level facts). No packages were installed to prove existence. No third-party source was copied (clean-room rule respected; Replit material untouched).

## Per-entry results (H-001..H-035)

Full machine-readable detail: `DEPENDENCY_HARVEST_RATIFICATION.json`. Summary:

| H-ID | Name | Decision / Integration | Ratified version line (official evidence) | License (class) | Result |
| --- | --- | --- | --- | --- | --- |
| H-001 | Node.js | ADOPT / DEPEND | 24.x LTS "Krypton"; 24.18.x verified (24.18.1 sec. release 2026-07-29), latest 24.19.0 | MIT (green) | PASS |
| H-002 | TypeScript | ADOPT / DEPEND | 6.0.3 (latest, 2026-04-16) | Apache-2.0 (green) | PASS |
| H-003 | pnpm | ADOPT / DEPEND | 11.x; 11.4.x verified, latest 11.14 | MIT (green) | PASS |
| H-004 | Turborepo | ADOPT / DEPEND | 2.10.x stable (2.10.10, 2026-08-14) | MIT (green) | PASS |
| H-005 | Expo | ADOPT / DEPEND | SDK 56 stable (RN 0.85, React 19.2) | MIT (green) | PASS |
| H-006 | React Native | ADOPT / DEPEND | 0.85.x (0.85.3, 2026-05-05) | MIT (green) | PASS |
| H-007 | Monaco Editor | ADOPT / DEPEND | 0.56.x (0.56.0, 2026-06-25) | MIT (green) | PASS |
| H-008 | xterm.js | ADOPT / DEPEND | 6.0.x (6.0.0, 2025-12-22) | MIT verified (green) | PASS — `@xterm/*` scoped npm packages recorded |
| H-009 | Fastify | ADOPT / DEPEND | 5.x; 5.10.x verified, latest 5.12.0 | MIT (green) | PASS |
| H-010 | PostgreSQL | ADOPT / SERVICE | 18.x (18.6 minor, 2026-08-13) | PostgreSQL (green) | PASS |
| H-011 | Drizzle ORM + Kit | ADOPT / DEPEND | 0.45.2 stable (1.0 RC excluded per rule) | Apache-2.0 (green) | PASS |
| H-012 | Better Auth | ADOPT / WRAP | 1.6.x (1.6.27, 2026-08-11) | MIT verified (green) | PASS |
| H-013 | OpenFGA | ADOPT_LATER / SERVICE | 1.18.x (1.18.1, 2026-06-29) | Apache-2.0 (green) | PASS |
| H-014 | Temporal TS SDK | ADOPT / DEPEND_SERVICE | 1.21.x (@temporalio/client 1.21.1) | MIT (green) | PASS — scoped packages note |
| H-015 | OpenHands Software Agent SDK | ADOPT_AS_DEFAULT_ADAPTER / SERVICE_ADAPTER | 1.x current (v1.42.1, 2026-08-12) — **supersedes 1.24.x anchor** | MIT — SDK repo (green; `enterprise/` source-available code excluded) | PASS w/ version correction |
| H-016 | Daytona | ADOPT_AS_PROVIDER / SERVICE_ADAPTER | 0.190.x = final OSS line | **AGPL-3.0 verified — REVIEW REQUIRED** | PASS w/ findings (see below) |
| H-017 | E2B | ADOPT_AS_PROVIDER / SERVICE_ADAPTER | 2.36.x verified; latest 2.39.0; npm pkg `e2b` | Repo Apache-2.0; JS SDK pkg license confirm at pin (review-marked) | PASS |
| H-018 | Agent Client Protocol | ADOPT / PROTOCOL | Schema 1.20.x stable (latest, 2026-07-21); v2 alpha experimental — matches policy | Apache-2.0 (green) | PASS |
| H-019 | Model Context Protocol | ADOPT / PROTOCOL_SDK | Spec 2026-07-28 (official); TS SDK v2 stable (2.0.0) | Apache-2.0 spec (transition), CC-BY-4.0 docs, MIT SDK (green) | PASS |
| H-020 | Agent2Agent (A2A) | ADOPT_WHEN_DELEGATION / PROTOCOL_SDK | Spec 1.0.1 (2026-05-26) | Apache-2.0 (green) | PASS |
| H-021 | AG-UI | OPTIONAL_BRIDGE / PROTOCOL | current stable profile at implementation | MIT verified (green) | PASS |
| H-022 | Vercel AI SDK | ADOPT / WRAP | 7.0.x stable 2026 line (7.0.66, 2026-08-14) — anchor made explicit | Apache-2.0 npm; per-package verify at pin (review-marked) | PASS |
| H-023 | Dev Containers Spec | ADOPT / PROTOCOL | current stable spec (maintained) | CC-BY-4.0 spec text / MIT code (green, attribution note) | PASS |
| H-024 | OpenTelemetry JS | ADOPT / DEPEND | 2.10.x (2.10.0, 2026-07) | Apache-2.0 (green) | PASS |
| H-025 | TypeBox | ADOPT / DEPEND | 1.x (typebox repo, ESM, TS6-7) or 0.x LTS (@sinclair/typebox) — choose at M-004 | MIT (green) | PASS — upstream repo split recorded |
| H-026 | Playwright | ADOPT / DEPEND_DEV | 1.62.x (2026-07/08) | Apache-2.0 (green) | PASS |
| H-027 | Maestro | ADOPT / TOOL | 2.x (CLI 2.8.0, 2026-08-06) | Apache-2.0 (green) | PASS |
| H-028 | Vitest | ADOPT / DEPEND_DEV | 4.1.x (4.1.7 stable; 5.0 beta excluded) | MIT (green) | PASS |
| H-029 | Gitleaks | ADOPT / CI_TOOL | 8.30.1 (2026-03-21) | MIT (green) | PASS — maintenance observation |
| H-030 | Trivy | ADOPT / CI_TOOL | 0.72.0 (2026-06-30) | Apache-2.0 (green) | PASS — supply-chain provenance note |
| H-031 | OSV-Scanner | ADOPT / CI_TOOL | 2.x (v2.3.5, 2026-03) | Apache-2.0 (green) | PASS |
| H-032 | Semgrep CE | ADOPT / CI_TOOL | current stable engine | **LGPL-2.1 engine — REVIEW REQUIRED** (rules vary; no restricted rulesets) | PASS w/ review flag |
| H-033 | GitHub API / Octokit | ADOPT / ADAPTER | 5.x / @octokit/core 7.x | MIT (green) | PASS |
| H-034 | S3-compatible SDK | ADOPT / ADAPTER | aws-sdk-js-v3 3.x (3.1108.0, 2026-08) | Apache-2.0 (AWS, verified); other providers vary (review-marked) | PASS |
| H-035 | CloudEvents | ADOPT_PROFILE / STANDARD | 1.0.x (v1.0.2 stable; 1.0.3 draft) | Apache-2.0 (green) | PASS |

**Totals: 35 verified; 28 PASS; 7 PASS with findings/corrections (H-008, H-015, H-016, H-017, H-022, H-029, H-030); 0 FAIL. Review-required licenses: H-016, H-017, H-022, H-032, H-034.**

## Findings

### F-1 — Daytona (H-016): upstream frozen + AGPL-3.0 (handled, decision preserved)

1. **Maintenance:** the official repository banner states the OSS repo is no longer maintained as of June 2026; core development moved to a private codebase and no further OSS releases will occur. `0.190.x` is the final open-source line. The operated Daytona service and documentation continue.
2. **License:** the official raw `LICENSE` at tag `v0.190.0` is **AGPL-3.0** (network copyleft) → review-required under `LICENSE_POLICY.md`.

Treatment: the decision (ADOPT_AS_PROVIDER behind a certifying workspace adapter) remains legally/technically supportable because VibeFlow integrates Daytona strictly as an **external provider over its API** — no source incorporation, vendoring or forking (also forbidden by this mission). The registry now records the verified license and the frozen-OSS fact, and requires Phase-11 workspace certification to certify the **operated service**, not the frozen repository. This is **not** permission for silent substitution (E2B/BYOW remain the approved alternatives in DO_NOT_INVENT). No ADR: the approved architecture (Daytona/E2B/BYOW behind certified adapters) is unchanged.

### F-2 — OpenHands SDK (H-015): stale version anchor (corrected)

Registry anchor `1.24.x` predates upstream reality: latest release is **v1.42.1** (2026-08-12, MIT). Version-line policy corrected to "1.x current stable reference line"; exact reference pin is re-resolved when the Phase-9 adapter mission executes. The MIT license applies to the SDK repository; the OpenHands application's `enterprise/` directory is separately-licensed source-available code that VibeFlow must never incorporate — recorded in the registry rule.

### F-3 — License precision completions

`See upstream`-style placeholders were replaced with verified values: H-021 AG-UI → **MIT**; H-023 Dev Containers → **CC-BY-4.0 (spec text) / MIT (code)**; H-019 MCP → **Apache-2.0 (spec, MIT→Apache-2.0 transition) + CC-BY-4.0 (docs) + MIT (TS SDK)**; H-016 Daytona → **AGPL-3.0**; H-034 → AWS SDK **Apache-2.0** with explicit variance note for non-AWS providers; H-017 E2B → repo Apache-2.0 with package-level confirmation explicitly deferred to the M-004 pin; H-022 → npm `ai` Apache-2.0 with per-package verification explicitly deferred. "Visible on GitHub = safe to copy" was never assumed; no third-party source was copied.

### F-4 — Non-blocking maintenance/security observations

- **Gitleaks (H-029):** maintainer states feature-complete/security-patches-only; original author started a separate MIT "Betterleaks" project. No substitution made; M-006 may re-evaluate under its own authority.
- **Trivy (H-030):** upstream disclosed a malicious `v0.69.4` release incident (2026-03-19, remediated). M-004/M-006 must verify release provenance/checksums when adopting CI binaries. Recorded in the registry rule.
- **xterm.js (H-008):** upstream migrated npm packages to the `@xterm/*` scope; legacy names deprecated. M-004 must pin scoped packages. Recorded in the registry rule.
- **TypeBox (H-025):** upstream split into `typebox` (1.x, ESM) and `@sinclair/typebox` (0.x LTS). Both are TS-6-compatible; single-line selection at M-004. Recorded in the registry rule.
- **Maestro (H-027):** community-reported Xcode 26.4 physical-device driver build defect in the 2.4.0 era; re-check when mobile E2E activates (Phase 8+).

## DO_NOT_INVENT consistency

All 12 approved-generic-solution areas map to ratified registry entries: Monaco (H-007), xterm.js (H-008), ACP (H-018), MCP (H-019), A2A (H-020), Temporal (H-014), Daytona/E2B/BYOW (H-016/H-017), OpenTelemetry (H-024), Better Auth (H-012), GitHub/GitLab adapters (H-033), Dev Containers (H-023), PostgreSQL (H-010). No duplicate capability implementations were introduced (H-016/H-017 are primary+secondary providers of one capability behind one adapter interface — intended). No BUILD decision exists; BUILD remains gated on an ADR proving no approved alternative fits. VibeFlow's proprietary effort stays pointed at authority composition, grants/policy, durable remote execution, recovery/reconciliation, provider normalization, mobile control and independent verification.

## Architectural boundary verification

Every entry's ownership boundary was re-checked against the Master contracts: provider SDKs stay behind adapters (INV-012); no provider becomes core authority; no provider is authoritative for VibeFlow state (INV-008); Better Auth supplies commodity authentication only; OpenHands is an adapter/reference; Daytona/E2B are providers under WorkspaceBinding authority; Temporal supplies mechanics under VibeFlow Task/Execution semantics; ACP/MCP/A2A cover exactly their interoperability boundaries; AG-UI stays optional; Dev Containers describe environments; OTel carries telemetry under VibeFlow redaction; GitHub/GitLab remain repository providers; S3 holds bytes only; CloudEvents is an external envelope only. No violation of the canonical resource model, invariants, state machines or event catalog was found.

## Mission-control transition

`STATUS_PROTOCOL.md` defines the mission vocabulary `LOCKED → READY → IN_PROGRESS → REVIEW → DONE / BLOCKED`; **DONE** is the canonical accepted terminal state, so no new status was invented:

- M-001: `REVIEW` → `DONE` (external acceptance consumed; documented, not self-accepted here)
- M-002: `LOCKED` → `REVIEW` (this mission)
- M-003..M-151: `LOCKED` (untouched)
- `.ai/ACTIVE_MISSION.md`, `README.md`, `docs/WORKSPACE_BOOTSTRAP_STATUS.md` updated to M-002.

## Validator changes

`scripts/validate-master-contracts.py` was **generalized, not weakened**: the M-001 bootstrap hard-coding (M-001 ∈ {READY, REVIEW}; all others LOCKED) was replaced by structural progression rules — status vocabulary; exactly one active mission under serial progression; an active mission requires all dependencies DONE; DONE missions must precede the active mission; every other mission LOCKED; every transitive dependent of a non-DONE mission LOCKED (subsumes "M-003 stays LOCKED during M-002" and "M-004 stays LOCKED until M-003 is accepted"); dependencies must reference strictly earlier missions (no chain-skipping); DAG ↔ register status synchronization; `.ai/ACTIVE_MISSION.md` pointer coherence. Bootstrap chain invariants (M-002→M-001, M-003→M-002, M-004 Phase-1→M-003) and all M-001 contract checks retained. `--root` added for deterministic testing.

New `scripts/validate-harvest-registry.py` (no third-party dependencies) validates: exactly 35 unique sequential H-IDs; required fields; https official-source allowlist per entry; decision/integration vocabularies; license classification (green / explicit review-required / unresolved-fails); BUILD requires ADR; DO_NOT_INVENT coverage; PACK_SUMMARY count sync.

Deterministic tests (`tests/contract/test_m002_validators.py`, stdlib unittest, 32 tests) prove failure for: duplicate H-ID; missing required field; invalid/missing/non-official source; **fake GitHub-repository provenance (generic github.com rejected; wrong-owner repo rejected)**; unsupported decision; unsupported integration; missing/unresolved license classification; **missing use/ownership/upgrade-policy/replacement-strategy**; entry-count drift; BUILD without ADR; unlocked M-003 during M-002; unlocked mission without DONE dependencies; two active missions; zero active missions; DONE after active; missing dependency; dependency cycle; forward dependency reference; duplicate mission ID; DAG/register status and order desync; stale ACTIVE_MISSION pointer — and prove validity of both the historical M-001 bootstrap state and a hypothetical future M-003 REVIEW state (generalization).

## Commands and results (revision 2 re-run)

```text
git diff --check                                      -> no output (clean), exit 0
bash scripts/repo-sanitize.sh                         -> "Repository sanitation checks passed." exit 0
  (secret scan executed: git grep -E ...; exit 1 = no matches = pass)
cd master-build-system && sha256sum -c SHA256SUMS.txt -> 72/72 OK, exit 0
python3 scripts/validate-master-contracts.py          -> RESULT: PASS, exit 0
  mission statuses: DONE=1 REVIEW=1 LOCKED=149
python3 scripts/validate-harvest-registry.py          -> RESULT: PASS, exit 0
  entries: 35; review-required licenses: 5 (H-016, H-017, H-022, H-032, H-034)
python3 tests/contract/test_m002_validators.py        -> Ran 32 tests ... OK, exit 0
```

CI (`Master Build System Integrity` on PR #3) executes the same semantic validators/tests after pack hash verification and fails on non-zero exit; the `Repository Sanitation` workflow continues to run unchanged.

## Pack-integrity hash changes

Legitimate M-002 pack modifications and the only hash lines updated in `master-build-system/SHA256SUMS.txt`:

| File | Why changed |
| --- | --- |
| `06_HARVEST/OSS_HARVEST_REGISTRY.yaml` | stale M-001 lockfile-pinning policy corrected; verified license/version/rule data recorded (H-008, H-015, H-016, H-017, H-019, H-021, H-022, H-023, H-025, H-030, H-034); review rev 2 added `use`/`ownership`/`upgrade_policy`/`replacement_strategy` to all 35 entries (LICENSE_POLICY contract closure) |
| `06_HARVEST/TECHNOLOGY_BASELINE_2026-08-17.md` | stale M-001 lockfile-pinning sentence corrected (pins at M-004) |
| `06_HARVEST/LICENSE_POLICY.md` | "records version pin" wording aligned with registry-ratification vs M-004 lockfile pinning |
| `10_IMPLEMENTATION/MISSION_DAG.yaml` | M-001 → DONE, M-002 → REVIEW |
| `10_IMPLEMENTATION/MISSION_REGISTER.csv` | same two status cells |

Old→new digests are listed in the PR description. Revision 2 re-hashed only `06_HARVEST/OSS_HARVEST_REGISTRY.yaml` again after the field additions (baseline `c72ce609…` → rev-1 `5df339d6…` → final `740fcd52…`); `sha256sum -c` confirmed it was the only mismatch before updating. Hashes were updated only for these five files after `sha256sum -c` confirmed they were the only mismatches; the checksum file was not mass-regenerated and no mismatch was concealed. `REPO_SEED_MANIFEST.json` is a frozen seed snapshot (M-001 precedent) and was not touched.

## Scope confirmations

No product implementation; no package installation; no monorepo initialization; no lockfile or package manifests; no M-003 (threat model) or M-004 (toolchain) work; no third-party source copied; M-003+ remain LOCKED. M-002 is submitted for independent review and is not self-accepted.
