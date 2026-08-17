# M-003 — Threat Model / Trust Boundary Ratification

## Identity

| Field | Value |
| --- | --- |
| Mission | M-003 — Ratify threat model and trust boundaries |
| Phase | 0 — Architecture Constitution |
| Starting main SHA | `41209e0b0ee2ab6a45f2cf66eef2d19177d7e4d4` |
| Branch | `mission/m-003-threat-model` |
| Date | 2026-08-17 |
| Dependency | M-003 depends on accepted/merged M-002 |
| Target state | M-001 DONE · M-002 DONE · M-003 REVIEW · M-004+ LOCKED |
| Classification | READY FOR REVIEW; independent acceptance pending |

## Ratified contract

The prior security pack already established the direction: clients are untrusted requestors; the Control Plane owns VibeFlow authority; agents are untrusted executors; workspace state must be reconciled; tools require grants; providers own their external resources but not VibeFlow product truth; verification must not echo agent assertions. M-003 makes that summary stable and testable rather than changing it.

The ratified model contains:

- **12 high-value asset classes** (`AS-001..AS-012`);
- **13 canonical trust boundaries** (`TB-001..TB-013`);
- **24 threat cases** (`TM-001..TM-024`);
- **20/20 non-negotiable invariants** explicitly crosswalked;
- a fail-closed rule whenever identity, scope, binding, freshness, continuity, approval, or required evidence cannot be proven.

Covered boundary families: client/gateway, gateway/control-plane, broker/KMS, agent provider, workspace provider/runtime, tools/MCP/connections, model providers, repository/Git hosts, data/object storage, deployment/production, native↔workspace-web bridge, external callbacks/webhooks/OAuth, and verification/evidence sources.

## Security conclusions

- External agent/model/tool/workspace/repository/provider/web content is **untrusted data**, not policy authority.
- Provider IDs, statuses, capabilities and completion claims remain observations/references.
- Tool/capability availability never creates permission.
- Raw credentials stay inside broker/KMS custody and the minimum authorized runtime channel; they never become ordinary prompts/events/evidence/logs/analytics/bridge state.
- Privileged actions are canonical actor+tenant+project+resource bound and retain Policy/Approval/evidence semantics.
- Agent/provider completion remains candidate state; Verification owns VERIFIED and binds evidence to exact revision/check.
- Repository, workspace, object storage and production runtime stay distinct.
- Reconnect/replay ambiguity enters resync/reconciliation; it never fabricates recovery.
- Later provider certification must measure runtime behavior; provider documentation is not sufficient evidence.
- No custom cryptography/security protocol was introduced.

## Machine enforcement

`python3 scripts/validate-threat-model.py` (stdlib only) verifies:

1. exact sequential IDs and required fields;
2. valid threat→asset/boundary references;
3. every asset and trust boundary is covered by at least one threat;
4. `INV-001..INV-020` are crosswalked exactly once;
5. Security Master retains normative security files and fail-closed/negative-test rules;
6. raw-secret and workspace-isolation protections cannot be silently weakened;
7. key anti-authority statements remain present.

`python3 tests/contract/test_m003_security_contracts.py` contains **18 deterministic mutation tests** that recreate security regressions and require the validator to fail.

## Scope / change control

No dependency was installed. No lockfile/package manifest or monorepo was created. No product/security implementation from M-004+ was started. No provider-specific exception was introduced. No ADR is required because this ratifies and makes explicit the already-established authority/security model rather than changing it.

GitHub CI results are attached to the final PR head SHA; they are deliberately not copied into this file so the evidence does not become self-referential when CI reruns.
