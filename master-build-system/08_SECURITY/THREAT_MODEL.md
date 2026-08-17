# Threat Model

This document is the canonical M-003 threat catalog. It turns the original summary into stable asset/threat identifiers, maps every threat to explicit trust boundaries, and records the minimum controls/evidence later implementation missions must satisfy.

## Security stance

- Assume mobile/web clients, agent/model providers, workspaces, repositories, tools/MCP servers, provider callbacks and third-party content can be stale, compromised, malicious, or simply wrong.
- The VibeFlow Control Plane is authoritative for VibeFlow resources. External components own their external runtime/resources but cannot assert VibeFlow product authority.
- Authorization is evaluated server-side from authenticated principal plus canonical tenant/project/resource/binding/grant/policy/approval context. Client/provider identifiers alone never grant access.
- Plaintext secrets are confined to the approved broker/KMS and minimum authorized runtime channel; they never become ordinary project/event/evidence/log/analytics/bridge state.
- Privileged operations fail closed when identity, scope, binding, approval, freshness, continuity, or required verification evidence cannot be proven.
- Verification prefers independent evidence and never upgrades an agent/provider completion claim directly to VERIFIED.
- No custom cryptography or security protocol is created by this mission; later implementation must use ratified standards/libraries/providers and preserve these semantics.

## Scope and assumptions

- This is a product/control-plane threat model, not a claim that VibeFlow can prove or inspect the internal security of every third-party provider.
- A fully compromised user endpoint can act within that user's currently valid server-authorized scope; least privilege, revocation and high-risk approvals are the containment mechanisms.
- Users may intentionally authorize destructive actions within their own scope. The security requirement is correct identity/scope/material-action presentation, policy/approval, idempotency and evidence—not silently overriding legitimate user intent.
- Provider documentation is input to certification, not proof of runtime isolation, persistence, idempotency or recovery behavior.

## High-value assets

### AS-001 — Identity and sessions

Account/Organization membership, authenticated sessions, OAuth state, device/session binding.

### AS-002 — Tenant/project/resource authority

Canonical ownership, membership, project/resource relationships, server-side authorization decisions.

### AS-003 — Secrets and provider credentials

Raw BYOK/API/OAuth credentials, broker/KMS material, SecretRef metadata and issuance controls.

### AS-004 — Grants, policy and approvals

ConnectionGrant scopes, Policy revisions, Approval state/freshness and revocation.

### AS-005 — Project source and private repository data

Source code, Git history/refs, repository metadata and private imported content.

### AS-006 — Workspace execution surface

Workspace filesystem, processes, terminal, preview, network, environment, snapshots and provider session.

### AS-007 — Canonical task/execution/event state

Task, Execution, ExecutionAttempt, Event, cursors, idempotency and canonical user-visible status.

### AS-008 — Evidence, verification and audit integrity

Evidence bytes/metadata, Verification/VerificationCheck results, AuditEvent provenance and hashes.

### AS-009 — Release and production authority

Release identity, DeploymentBinding, production runtime, domains/access, rollback and release evidence.

### AS-010 — Data and object-storage resources

DataBinding/ObjectStorageBinding, environment separation, application data, artifact/evidence blobs.

### AS-011 — Billing, usage and entitlement records

Entitlement, UsageRecord, provider-attributed spend, budgets and abuse limits.

### AS-012 — Provider bindings and capability observations

Agent/Model/Workspace/Repository/Deployment bindings, provider IDs, capability and health observations.

## Threat catalog

### TM-001 — Cross-tenant/resource ID confusion (IDOR)

- **Actors:** Malicious or buggy authenticated client; stale client; compromised session.
- **Assets:** AS-001, AS-002, AS-004, AS-005, AS-010
- **Boundaries:** TB-001, TB-002
- **Risk:** P0 — unauthorized cross-tenant/project/resource read or mutation.
- **Attack:** Submit another tenant/project/resource identifier, swap a binding ID, or rely on a stale cached relationship so a valid session acts outside its canonical scope.
- **Required controls:** Authenticate session; resolve Organization/Project/resource relationships server-side; bind every privileged command to actor+tenant+project+resource; never authorize from client IDs alone; reject stale expected versions; apply least-privilege grants/policy.
- **Detection/evidence:** Audit actor/session/tenant/project/resource and denied scope checks; negative E2E proves cross-tenant and cross-project identifiers fail.
- **Residual risk:** A server-side authorization bug can still violate isolation; later IAM/authorization missions must produce systematic negative coverage and code review evidence.

### TM-002 — Stolen, replayed, or confused session/token

- **Actors:** Network attacker, malicious client, compromised device/browser, leaked bearer token.
- **Assets:** AS-001, AS-002, AS-004
- **Boundaries:** TB-001, TB-002, TB-012
- **Risk:** P0 — impersonation and unauthorized privileged commands.
- **Attack:** Reuse a stolen/revoked session, replay browser/OAuth state, mix actor/session/project context, or continue using credentials after logout/revocation.
- **Required controls:** Short-lived/revocable sessions; secure transport/storage; server-side current-session validation; state/nonce/CSRF/origin defenses where applicable; actor/project/resource binding; privileged commands remain idempotent and policy-checked.
- **Detection/evidence:** Record session/principal/correlation and revocation outcomes; flag replayed nonce/state/message IDs and impossible tenant/project switches.
- **Residual risk:** A fully compromised endpoint may act as the user within granted scope until session revocation; server-side least privilege and high-risk approvals limit blast radius.

### TM-003 — Client privilege escalation or forged authority

- **Actors:** Malicious/stale mobile, web, or workspace-web client; malicious embedded content.
- **Assets:** AS-002, AS-004, AS-007, AS-009
- **Boundaries:** TB-001, TB-002, TB-011
- **Risk:** P0 — client turns UI/cache/provider observations into authority.
- **Attack:** Forge role/grant/approval/status/version fields, claim a resource is VERIFIED/DONE, or invoke a privileged command unavailable to the authenticated canonical state.
- **Required controls:** Clients are request/inspection surfaces only; canonical resource state/version comes from Control Plane; server revalidates authorization, Policy and Approval; UI state maps to canonical backend state; bridge never transfers backend authority.
- **Detection/evidence:** Audit rejected forged/stale versions and authorization mismatches; contract tests mutate client-supplied roles/status/resource IDs and require rejection.
- **Residual risk:** Presentation bugs may mislead without granting server authority; frontend-backend contracts must prevent misleading privileged affordances.

### TM-004 — Raw secret or provider credential exfiltration

- **Actors:** Malicious agent/tool/workspace/web content, compromised client/provider, logging/support pipeline, accidental developer error.
- **Assets:** AS-003, AS-004
- **Boundaries:** TB-003, TB-004, TB-005, TB-006, TB-007, TB-011
- **Risk:** P0 — credential compromise can escape VibeFlow project boundaries and incur external damage/cost.
- **Attack:** Expose plaintext credentials through ordinary APIs, prompts, events, evidence, logs, analytics, bridge messages, workspace environment, or over-broad provider/tool release.
- **Required controls:** Raw custody only in approved encrypted broker/KMS; ordinary state stores SecretRef/metadata; release minimum secret only to exact approved provider/tool channel for shortest practical lifetime; scope/purpose/audience binding, revocation/rotation; explicit redaction; no raw secret across native-web bridge.
- **Detection/evidence:** Secret-scanning/redaction tests, broker audit without plaintext, negative bridge/event/evidence/log tests, credential revocation/usage anomaly monitoring.
- **Residual risk:** An authorized external recipient may itself be compromised; minimize lifetime/scope and allow revocation/rotation without pretending VibeFlow can inspect provider internals.

### TM-005 — Prompt injection from repository, tool, model, workspace, or external data

- **Actors:** Malicious repository author/dependency, compromised tool/MCP server, malicious web content, model/provider output, hostile workspace file.
- **Assets:** AS-002, AS-003, AS-004, AS-005, AS-009
- **Boundaries:** TB-004, TB-005, TB-006, TB-007, TB-008
- **Risk:** P0 — untrusted content persuades an agent/model to misuse real authority.
- **Attack:** Place instructions in code/docs/tool output/web content that ask the agent to reveal secrets, expand grants, call destructive tools, push code, or deploy outside user intent.
- **Required controls:** External content is data, not policy authority; tool calls pass through ConnectionGrant/Policy/Approval; secrets are brokered and not placed in prompts; repository/deployment writes are separately scoped; agent capability never implies permission; high-risk actions require explicit server-side checks.
- **Detection/evidence:** Audit tool/repo/deployment actions with originating execution and grants; adversarial prompt-injection tests prove content cannot bypass broker/policy/approval boundaries.
- **Residual risk:** Injection can influence low-risk actions inside granted scope; minimize grants/context and make destructive/irreversible authority independently mediated.

### TM-006 — Malicious/compromised coding agent or false completion

- **Actors:** Agent provider compromise, adversarial agent behavior, model failure inside agent, provider session confusion.
- **Assets:** AS-005, AS-006, AS-007, AS-008, AS-009, AS-012
- **Boundaries:** TB-004, TB-005, TB-006, TB-013
- **Risk:** P0 — executor mutates state incorrectly or falsely claims success.
- **Attack:** Emit malformed/misbound events, claim completion without correct files/tests, perform unauthorized tool/workspace actions, or hide provider session loss.
- **Required controls:** Agent is untrusted executor; adapter normalizes and binds provider session to ExecutionAttempt; Agent finish never VERIFIED; provider finish maps only to CANDIDATE_COMPLETE; tools/workspace separately authorized; malformed/duplicate/stale events rejected; independent Verification decides VERIFIED.
- **Detection/evidence:** Persist normalized events/attempt lineage; certification covers disconnect, duplicate controls, malformed events, unsupported capability, cancellation/session loss; verification evidence is independent where feasible.
- **Residual risk:** Agent may produce subtly incorrect code that passes available checks; verification quality and later security/product tests bound but cannot eliminate semantic risk.

### TM-007 — Tool grant bypass or ambient connection authority

- **Actors:** Agent, malicious client, compromised tool, implementation bug.
- **Assets:** AS-003, AS-004, AS-010, AS-011
- **Boundaries:** TB-006, TB-003
- **Risk:** P0 — available connection/tool becomes implicitly callable outside intended scope.
- **Attack:** Call a discovered tool without a grant, reuse a grant across project/execution, escalate scope from tool metadata, or use stale/revoked approval.
- **Required controls:** Tool availability != permission; active ConnectionGrant plus canonical project/connection scope and Policy required; Approval for policy-designated high-risk actions; broker releases only needed credential; grant revocation and approval freshness enforced.
- **Detection/evidence:** Audit tool+grant+policy+approval references and denials; deterministic negative tests for no-grant, wrong-project, revoked-grant and stale-approval calls.
- **Residual risk:** Over-broad user-approved grants remain risky; UX/policy should default to least privilege and allow immediate revocation.

### TM-008 — Compromised MCP/tool server or malicious tool output

- **Actors:** Compromised/malicious MCP server, external API, connection provider.
- **Assets:** AS-003, AS-004, AS-005, AS-007
- **Boundaries:** TB-006, TB-004
- **Risk:** P0 — malicious tool can return injection/data or abuse granted credentials.
- **Attack:** Return poisoned schemas/results, prompt-inject the agent, request unexpected parameters/secrets, lie about side effects, or exploit a grant to reach unrelated resources.
- **Required controls:** Treat schemas/descriptions/output as untrusted data; validate call arguments and normalized result; grant and resource scope server-side; do not send unrelated secrets/context; approval/idempotency for high-risk durable calls; record external request refs.
- **Detection/evidence:** Sanitized tool-call audit/evidence, schema/conformance/security tests, side-effect reconciliation where provider supports it, anomalous scope/egress detection.
- **Residual risk:** Within an intentionally granted external scope the tool can misbehave; provider choice, minimal scopes, reconciliation and revocation contain exposure.

### TM-009 — Hostile workspace process, isolation escape, or cross-tenant leakage

- **Actors:** Malicious dependency/build script, compromised agent, hostile user code, compromised workspace provider.
- **Assets:** AS-003, AS-005, AS-006, AS-010, AS-012
- **Boundaries:** TB-005, TB-003, TB-009
- **Risk:** P0 — code execution escapes project/workspace boundary or reads another tenant/secret.
- **Attack:** Read host/neighbor files, persist after cleanup, access another workspace/project, steal credentials, abuse preview/auth, or exploit weak provider isolation.
- **Required controls:** Certified provider boundary: filesystem/project scoping, process isolation, network controls, preview auth, secrets exposure checks, persistence/snapshot semantics, quotas, cleanup and cross-tenant tests; exact WorkspaceBinding; minimal secret exposure; provider docs alone are not evidence.
- **Detection/evidence:** Adapter certification records observed negative behavior; lifecycle/cleanup evidence, workspace revision hashes, provider refs and cross-tenant canary tests.
- **Residual risk:** A provider infrastructure compromise can defeat sandbox guarantees; support provider revocation/failover and never elevate provider workspace to VibeFlow authority.

### TM-010 — Workspace network egress exfiltration, SSRF, or internal pivot

- **Actors:** Hostile project process/dependency, compromised agent, injected command.
- **Assets:** AS-003, AS-006, AS-010, AS-012
- **Boundaries:** TB-005, TB-006, TB-009
- **Risk:** P0/P1 — workspace uses network to leak data or reach internal/provider metadata endpoints.
- **Attack:** Send project/secrets externally, scan private services, hit cloud metadata/control endpoints, or bypass tool grants by direct network access.
- **Required controls:** Workspace certification must validate network controls; egress/resource policy and quotas; do not make privileged control-plane/internal endpoints reachable from workspace by default; brokered credentials have narrow audience/scope; tools remain grant-mediated.
- **Detection/evidence:** Workspace/provider network audit where available, egress policy denies, resource anomalies, certification probes for metadata/private-network access.
- **Residual risk:** Some development tasks need broad internet egress; later workspace/security missions must expose and constrain the risk rather than claim perfect isolation.

### TM-011 — Replayed, duplicated, stale, or reordered privileged command

- **Actors:** Network/client retry, malicious client, reconnect race, provider duplicate callback, implementation failure.
- **Assets:** AS-004, AS-007, AS-009, AS-011
- **Boundaries:** TB-001, TB-002, TB-006, TB-010, TB-012
- **Risk:** P0 — duplicate charge/deploy/delete/write or stale transition.
- **Attack:** Replay a previously authorized command/approval, race old expected state, or redeliver provider events to apply side effects twice.
- **Required controls:** Every durable transition is idempotent/deduplicated; use idempotency keys/message/event IDs and expected resource version; bind Approval/Policy revision and resource; deduplicate callbacks; reject stale transitions.
- **Detection/evidence:** Audit duplicate/dedup decisions, expected-version conflicts and event IDs; chaos/contract tests resend commands/callbacks around disconnects.
- **Residual risk:** External provider APIs without idempotency may duplicate side effects; adapters must reconcile provider state and record ambiguity rather than fabricate success.

### TM-012 — Native-web bridge origin/session/project confusion

- **Actors:** Malicious embedded web content, XSS/compromised workspace preview, stale web/native endpoint.
- **Assets:** AS-001, AS-002, AS-003, AS-004, AS-006
- **Boundaries:** TB-011, TB-001
- **Risk:** P0 — embedded content invokes native/backend privilege or steals credentials.
- **Attack:** Send bridge messages from wrong origin/project/workspace/session, replay old messages, forge OAuth/permission requests, or smuggle raw secrets.
- **Required controls:** Bridge bound to version, app build, authenticated account, project, WorkspaceBinding, allowed origin and negotiated capability; validate envelope/direction/correlation; sensitive commands require explicit permission plus backend authorization; no raw provider tokens; OAuth/secrets mediated through native/control-plane opaque refs.
- **Detection/evidence:** Bridge fuzz/conformance and wrong-origin/project/session negative tests; audit permission/OAuth handoffs without secret payloads.
- **Residual risk:** A compromised allowed-origin application can issue allowed UI requests; backend authority checks and least-privilege bridge capabilities contain impact.

### TM-013 — Provider account compromise or forged provider status/capability

- **Actors:** Compromised provider account/API, malicious provider response, stale capability cache.
- **Assets:** AS-003, AS-007, AS-009, AS-011, AS-012
- **Boundaries:** TB-004, TB-005, TB-007, TB-008, TB-009, TB-010, TB-012
- **Risk:** P0/P1 — external provider claims are mistaken for VibeFlow truth or expand authority.
- **Attack:** Forge completion/health/deployment/capability/usage status, swap provider resource IDs, or advertise unsupported capabilities that core assumes safe.
- **Required controls:** Provider IDs/status/capabilities are observations; bind provider resources to canonical Binding; capability negotiation/certification; core never treats provider claim as authorization; adapter normalization; independent verification/reconciliation for authoritative transitions.
- **Detection/evidence:** Provider reference/health/capability history, mismatch/reconciliation evidence, certification failures and usage anomalies.
- **Residual risk:** Provider can lie about facts only it can observe internally; VibeFlow must label such data as provider-reported and avoid stronger claims.

### TM-014 — Repository/workspace state confusion or stale reconciliation

- **Actors:** Concurrent user/agent/provider mutation, reconnect race, stale client, lost workspace session.
- **Assets:** AS-005, AS-006, AS-007, AS-008
- **Boundaries:** TB-005, TB-008, TB-013
- **Risk:** P0 — verification/recovery/release applies to different bytes than user believes.
- **Attack:** Assume event replay restored files, equate repository SHA with workspace revision, verify stale files, or overwrite evidence from a failed/lost attempt.
- **Required controls:** Repository != workspace; replay != workspace reconciliation; WorkspaceRevision records observed state/hash; reconcile after uncertainty/reconnect; bind verification/checkpoint/release evidence to exact revision/source; preserve failed/lost attempt evidence.
- **Detection/evidence:** Revision/hash comparisons, reconciliation records, mismatch state, checkpoint/evidence provenance and crash-window tests.
- **Residual risk:** Providers may not expose atomic snapshots; VibeFlow records the proven consistency level and must not pretend atomicity.

### TM-015 — Malicious dependency/build script or software supply-chain compromise

- **Actors:** Compromised package/release/registry, typosquat, malicious dependency maintainer, poisoned build artifact.
- **Assets:** AS-003, AS-005, AS-006, AS-009
- **Boundaries:** TB-005, TB-008, TB-010
- **Risk:** P0/P1 — third-party code executes in CI/workspace/build/deploy context.
- **Attack:** Introduce malicious package/code, compromised release binary, dependency confusion, install script or build artifact that exfiltrates or tampers with output.
- **Required controls:** Only registry-ratified dependencies; exact pins/lockfile beginning M-004; provenance/checksum verification for tools where required; secret/dependency/container/static scans; least-privilege CI/workspace; clean-room rule; release evidence must bind tested artifact/revision.
- **Detection/evidence:** Dependency/provenance scan evidence, lockfile/registry diff gates, secret/static/container scans, reproducibility/hash comparisons where practical.
- **Residual risk:** Approved upstream can later be compromised; upgrade policy, provenance verification and rapid replacement/revocation remain necessary.

### TM-016 — Forged, tampered, stale, or self-attested verification evidence

- **Actors:** Malicious agent/provider/workspace, compromised scanner/CI source, stale artifact, storage tampering.
- **Assets:** AS-007, AS-008, AS-009
- **Boundaries:** TB-013, TB-004, TB-005, TB-008
- **Risk:** P0 — VibeFlow marks incorrect/unverified state as safe or releasable.
- **Attack:** Submit agent statement as evidence, reuse results from another revision, alter evidence bytes, treat interrupted/unavailable check as pass, or let provider both perform and attest without independent signal.
- **Required controls:** Agent finish never VERIFIED; Verification owns result; exact project/execution/revision/check binding; source/provider+hash+timestamp provenance; interrupted/unknown != pass; independent evidence where feasible; immutable references/hash for stored evidence.
- **Detection/evidence:** VerificationCheck lineage, evidence hashes/source/freshness, mismatch/replay rejection and deliberate failed/interrupted-check tests.
- **Residual risk:** Independent checks can share common infrastructure or blind spots; final high-risk release/security review may require multiple evidence sources.

### TM-017 — Deployment authority abuse or development-to-production confusion

- **Actors:** Compromised agent/client, over-broad grant, stale approval, compromised deployment provider.
- **Assets:** AS-004, AS-008, AS-009, AS-012
- **Boundaries:** TB-010, TB-004, TB-013
- **Risk:** P0 — unverified or unauthorized code/config reaches production.
- **Attack:** Deploy directly from arbitrary workspace, reuse approval for different release, confuse preview with production, or accept provider deployment status as release proof.
- **Required controls:** Development workspace != production runtime; Release is VibeFlow authority linking exact verification evidence and DeploymentBinding; privileged production action requires policy/approval; immutable release/evidence binding; deployment provider status is observation; rollback lineage.
- **Detection/evidence:** Audit release/evidence/provider deployment IDs, approval/policy revision, environment and actor; negative tests deny workspace-only or stale-approval deployment.
- **Residual risk:** A compromised deployment provider controls its runtime; VibeFlow can detect/reconcile/rotate/fail over but cannot guarantee provider internals.

### TM-018 — Data/object-storage environment, prefix, or ownership confusion

- **Actors:** Malicious client/agent, adapter bug, stale provider resource mapping.
- **Assets:** AS-002, AS-003, AS-008, AS-010, AS-012
- **Boundaries:** TB-009, TB-003
- **Risk:** P0 — cross-tenant/dev-prod data access or evidence/artifact corruption.
- **Attack:** Swap DataBinding/ObjectStorageBinding, use wrong environment/prefix/bucket/database, treat object storage as workspace, or accept provider resource ID without canonical binding.
- **Required controls:** Server-side tenant/project/binding/environment/resource authorization; provider IDs are reference only; dev/prod separation; object storage != workspace; credential audience/scope; version/checksum/preconditions for evidence/artifacts where applicable.
- **Detection/evidence:** Binding/environment audit, denied cross-prefix/database tests, snapshot/checksum evidence, provider-resource reconciliation.
- **Residual risk:** Misconfigured provider-side IAM may broaden access; provider certification/configuration review and VibeFlow scoping must both be correct.

### TM-019 — Billing, spend, resource exhaustion, or runaway automation abuse

- **Actors:** Malicious/compromised account, injected agent/tool flow, buggy loop, provider usage misreport.
- **Assets:** AS-007, AS-011, AS-012
- **Boundaries:** TB-004, TB-005, TB-006, TB-007, TB-010
- **Risk:** P1 — financial/resource denial-of-service or hidden provider cost.
- **Attack:** Loop model/tool/workspace/deploy calls, evade budgets, forge usage attribution, or use automation after entitlement/revocation changes.
- **Required controls:** Entitlement distinct from provider subscription; per-binding/execution budgets/quotas/rate controls where supported; durable cancellation; provider usage is observed/attributed, not hidden; high-cost/high-risk actions policy-gated.
- **Detection/evidence:** UsageRecord/provider correlation, budget/rate alerts, abnormal execution duration/call count, cancellation and entitlement audit.
- **Residual risk:** Some provider cost is delayed or approximate; VibeFlow must label observed/reported usage and enforce conservative local limits where possible.

### TM-020 — Event-stream gap, stale projection, or canonical-state disagreement

- **Actors:** Network failure, stale client, dropped/reordered event, compromised client, gateway/provider outage.
- **Assets:** AS-002, AS-007, AS-008
- **Boundaries:** TB-001, TB-002, TB-004, TB-005
- **Risk:** P0/P1 — UI/user acts on stale state or reconnect is falsely treated as recovery.
- **Attack:** Hide missed events, replay out of order, present stale status as current, or treat transport reconnect/event replay as proof execution/workspace recovered.
- **Required controls:** Canonical backend state/version; cursor/sequence and ACK; if replay continuity cannot be proven require snapshot/resync; reconnect != execution recovery; replay != workspace reconciliation; client cache is projection only.
- **Detection/evidence:** Cursor gaps, resync_required, version conflicts, stale-client telemetry, recovery/reconciliation records and disconnect tests.
- **Residual risk:** Read-only UI may temporarily be stale during outage; it must show degraded/unknown state rather than fabricate authority.

### TM-021 — Secret or sensitive-data leakage through logs, telemetry, evidence, analytics, or support

- **Actors:** Accidental instrumentation, support workflow, compromised observability backend, malicious payload designed to be logged.
- **Assets:** AS-003, AS-005, AS-008, AS-010
- **Boundaries:** TB-001, TB-003, TB-006, TB-013
- **Risk:** P0/P1 — secondary systems become covert secret/data exfiltration channels.
- **Attack:** Place credentials/private content in errors/tool outputs/URLs so they are persisted in logs/traces/evidence/analytics/support exports.
- **Required controls:** Raw secrets forbidden in those channels; structured allowlist/redaction; sanitize tool/provider payloads; Evidence stores minimum required data with source/hash where bytes can live separately; support access is scoped/audited and cannot silently exfiltrate logs.
- **Detection/evidence:** Secret scanning and redaction tests on logs/events/evidence/support fixtures; audit sensitive-data access/export and detect high-entropy credential patterns.
- **Residual risk:** Novel sensitive strings may evade pattern redaction; data minimization and typed schemas reduce reliance on regex-only scrubbing.

### TM-022 — Spoofed or replayed external callback/webhook/OAuth event

- **Actors:** Internet attacker, compromised provider, malicious client, replay proxy.
- **Assets:** AS-001, AS-002, AS-004, AS-007, AS-009, AS-012
- **Boundaries:** TB-012, TB-002
- **Risk:** P0 — external request mutates canonical state without authentic provider/user intent.
- **Attack:** Forge webhook signature/state, replay valid event, swap provider/binding/resource identifiers, or complete OAuth for wrong session/project.
- **Required controls:** Provider-supported signature/token/mTLS verification; OAuth state/nonce; timestamp/event-ID dedup; correlate to expected canonical provider/binding/session/resource; callback cannot grant new authority by itself; provider tenant/project IDs never sole authority.
- **Detection/evidence:** Audit signature/correlation result and replay rejection; deterministic spoof/wrong-binding/replayed-event tests.
- **Residual risk:** If provider signing/auth infrastructure is compromised, events may authenticate falsely; VibeFlow still limits them to pre-existing canonical bindings and reconciles high-risk state.

### TM-023 — Approval/policy replay, stale approval, or approval-context substitution

- **Actors:** Malicious client/agent, reconnect race, stale UI, implementation bug.
- **Assets:** AS-002, AS-004, AS-007, AS-009
- **Boundaries:** TB-001, TB-002, TB-006, TB-010
- **Risk:** P0 — a valid approval authorizes a different/newer/more destructive action.
- **Attack:** Reuse approval after policy/resource/version change, swap target parameters, approve one tool/deploy and execute another, or lose pending approval on reconnect then infer success.
- **Required controls:** Approval is VibeFlow durable authority bound to actor/project/resource/action/material parameters/policy revision and freshness; pending survives reconnect/restart; privileged command revalidates current policy and approval; idempotency prevents duplicate consumption.
- **Detection/evidence:** Audit approval creation/decision/consumption with policy revision and target hash/parameters; negative tests mutate target/version/action or replay consumed/stale approval.
- **Residual risk:** Human may approve malicious-looking content; UI must present material action/target clearly and policy can require stronger review for irreversible operations.

### TM-024 — Capability spoofing or unsupported provider-semantics assumption

- **Actors:** Provider, stale cache, adapter bug, malicious endpoint, implementation shortcut.
- **Assets:** AS-007, AS-008, AS-009, AS-012
- **Boundaries:** TB-004, TB-005, TB-006, TB-007, TB-008, TB-009, TB-010
- **Risk:** P1/P0 — core assumes parity/guarantees the provider does not actually offer.
- **Attack:** Advertise persistence/isolation/idempotency/cancellation/model/tool/deploy capability inaccurately or let core branch on provider-specific behavior that bypasses VibeFlow controls.
- **Required controls:** ProviderCapability is a VibeFlow cache of observed/advertised capability, never authority; negotiate and certify where security/reliability matters; unsupported capability fails closed or degrades explicitly; provider-specific behavior behind adapters; do not claim atomicity/verification/control not proven.
- **Detection/evidence:** Capability/certification evidence by provider/version, mismatch telemetry, adapter contract tests and negative unsupported-capability paths.
- **Residual risk:** Capability can regress between certifications; bind certification/profile version, health checks and re-certification triggers to upgrades.

## Non-negotiable invariant crosswalk

Every `INV-001..INV-020` is explicitly covered so a future security edit cannot silently drop a constitutional invariant.

- **INV-001:** TM-006, TM-016 — agent completion is candidate only; Verification owns VERIFIED.
- **INV-002:** TM-020 — reconnect is transport recovery only.
- **INV-003:** TM-014, TM-020 — replay cannot substitute for workspace reconciliation.
- **INV-004:** TM-014, TM-015 — repository and workspace remain distinct authorities/state surfaces.
- **INV-005:** TM-018 — object storage is never treated as a workspace.
- **INV-006:** TM-017 — development workspace is not production runtime.
- **INV-007:** TM-006, TM-013 — AgentBinding and ModelBinding/runtime authority remain distinct.
- **INV-008:** TM-013, TM-024 — provider IDs/status/capabilities are observations/references.
- **INV-009:** TM-004, TM-012, TM-021 — raw BYOK/provider secrets do not enter client-readable/bridge channels.
- **INV-010:** TM-005, TM-007, TM-008 — tool availability/capability does not imply permission.
- **INV-011:** TM-001, TM-003 — privileged commands are server-bound to canonical tenant/project/resource.
- **INV-012:** TM-013, TM-024 — provider-specific semantics stay behind adapters.
- **INV-013:** TM-015, TM-024 — approved standards/SDKs precede custom security/protocol invention.
- **INV-014:** TM-011, TM-017, TM-023 — irreversible/high-risk actions carry policy, approval where required, and evidence semantics.
- **INV-015:** TM-011, TM-022, TM-023 — durable transitions/callback effects are idempotent/deduplicated.
- **INV-016:** TM-003, TM-020 — user-visible status is projection of one canonical backend mapping.
- **INV-017:** TM-003, TM-020 — phone/web surfaces do not own execution.
- **INV-018:** TM-015 — dependencies must be ratified with license/ownership before addition.
- **INV-019:** TM-015 — clean-room evidence cannot become Replit implementation source.
- **INV-020:** TM-005, TM-006 — mission context stays bounded to reduce ambient/injected authority and scope.

## Ratification rule

A later mission may strengthen these controls without an ADR. Weakening an authority boundary, secret rule, required approval/evidence condition, fail-closed behavior, or invariant requires explicit architecture change control and independent review. Threat IDs and boundary IDs are stable references; additions use new IDs rather than renumbering existing entries.
