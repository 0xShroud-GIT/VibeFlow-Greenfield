# J1 Product Throughput Plan

Status: **IMPLEMENTED / ACTIVE**

This plan corrects delivery order, not product scope. The canonical V1 product promise, trust boundaries, security thresholds, state machines, dependency authority, and all 151 mission scopes remain required for V1.

## Goal

Reach canonical user journey J1 — **Zero to running project** — as an early real product milestone instead of completing every horizontal platform layer first.

J1-ALPHA means a user can:

1. establish an authenticated account/organization;
2. create/open a Project;
3. connect one real provider path;
4. create and run a durable Task/Execution;
5. use the mobile shell to inspect project/task state;
6. use one real Agent + Model + Workspace path;
7. open files, terminal and preview;
8. reach candidate completion;
9. run independent build/test/security verification and see the result.

J1-ALPHA is not V1 completion and does not authorize production release, provider breadth, offline/reconnect claims, enterprise features, or deferred security/recovery capabilities.

## Operating rule

**Product progress wins unless a proven correctness, security, dependency or architecture prerequisite blocks it.**

- No new governance/CI/evidence framework merely because it could be cleaner.
- Existing durable validators and security gates remain in force.
- One active mission at a time remains the default control for risk.
- Mission IDs are identities, not an implicit execution order. Activation is controlled by explicit dependencies and status.
- A mission may be deferred without being deleted or treated as complete.
- Deferred missions remain required for V1 and must be completed before their dependent V1 gates can pass.
- If implementation proves a deferred mission is a real prerequisite, stop the jump and pull that prerequisite onto the path rather than creating a shortcut.

## J1-ALPHA critical path

The target path is 30 existing missions instead of executing every M-008→M-076 mission first:

1. `M-008` — Account/Organization persistence
2. `M-009` — authentication/session flows
3. `M-010` — tenant/resource authorization
4. `M-012` — Project authority
5. `M-016` — binding resource family
6. `M-020` — Connection and SecretRef broker
7. `M-021` — ConnectionGrant scopes
8. `M-024` — Task/Execution schemas
9. `M-025` — Temporal workflow engine
10. `M-026` — durable event/outbox/replay
11. `M-027` — idempotent command layer
12. `M-028` — execution lifecycle E2E
13. `M-033` — Expo mobile app bootstrap
14. `M-034` — auth/projects navigation
15. `M-035` — Task/Execution action center
16. `M-038` — ACP gateway/profile
17. `M-039` — OpenHands adapter
18. `M-043` — ModelBinding/BYOK
19. `M-044` — model provider adapter layer
20. `M-046` — model-key redaction/security tests
21. `M-047` — WorkspaceProvider contract
22. `M-048` — Daytona adapter
23. `M-052` — file tree/editor
24. `M-053` — terminal session UI
25. `M-054` — preview/log surfaces
26. `M-072` — Evidence store
27. `M-073` — Verification engine
28. `M-074` — build/test/security check adapters
29. `M-075` — verification UX
30. `M-076` — independent completion E2E

## Explicitly deferred until after J1-ALPHA unless proven necessary

Examples include:

- audit baseline beyond the minimum security evidence needed for J1 (`M-011`);
- Artifact/import/template breadth and project-lifecycle breadth (`M-013`–`M-015`);
- provider discovery/registry/certification breadth (`M-017`–`M-019`);
- approval/OAuth breadth not required by the chosen first path (`M-022`–`M-023`);
- remote replay/reconnect (`M-029`–`M-032`);
- notifications and degraded/offline mobile UX (`M-036`–`M-037`);
- Plan-vs-Build, capability negotiation and BYOA breadth (`M-040`–`M-042`);
- cost attribution (`M-045`);
- E2B/BYOW and workspace certification breadth (`M-049`–`M-051`);
- command-palette/IDE breadth (`M-055`–`M-056`);
- secure native-web bridge depth (`M-057`–`M-061`);
- repository/Git, checkpoint and recovery depth (`M-062`–`M-071`, `M-077+`) until the J1 loop proves which pieces must be pulled forward.

Deferral is **not** acceptance. These missions stay `LOCKED` until selected later and remain required for V1.

## First-provider strategy

Use one production-quality path first, behind the already-ratified provider contracts:

- Agent: OpenHands (`M-038`/`M-039`)
- Workspace: Daytona (`M-047`/`M-048`)
- Model: the first ratified ModelBinding/provider path selected under the harvest registry and implementation-reference policy (`M-043`/`M-044`)

Provider-neutral contracts are built before the first adapter so this path does not hard-code VibeFlow to those providers. Breadth and certification follow after J1 works.

## Verification strategy

PR-fast remains the normal path for ordinary product work. Deep mutation/container verification remains risk-triggered. J1 work must not weaken tenant isolation, secret handling, dependency authority, durable execution invariants or candidate-vs-VERIFIED separation.

## Mission-system correction required by this branch

The current validator incorrectly treats mission/register position as execution order. This branch must change progression semantics so:

- exactly one mission remains active/reviewable;
- an active mission requires all of its **effective explicit dependencies** to be `DONE`;
- non-active, non-DONE missions remain `LOCKED`;
- dependents of incomplete prerequisites remain locked;
- cycles remain forbidden;
- mission IDs/order no longer prevent a later-ID mission from completing before a deferred earlier-ID mission;
- deferred missions can be activated later without invalidating already accepted J1 missions.

The branch must also encode the J1 dependency edges in the canonical machine-readable mission authority, update its human register consistently, add adversarial progression tests, and keep the 151-mission/V1 finish line unchanged.

## Immediate state transition

After this delivery correction is reviewed and accepted:

- close `M-007` from `REVIEW` to `DONE` using its already-merged exact-head evidence;
- complete the M-007 environment capability state according to the capability status protocol;
- activate `M-008` as the first product mission;
- do **not** open another foundation/governance mission before beginning M-008 product implementation.
