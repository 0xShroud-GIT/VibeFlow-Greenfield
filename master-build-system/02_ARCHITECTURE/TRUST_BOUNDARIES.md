# Trust Boundaries

This document is normative for security architecture. A trust boundary is crossed whenever data, authority, credentials, or execution control moves between components with different authority or compromise assumptions.

## Global rules

- The VibeFlow Control Plane is authoritative for VibeFlow product resources. External providers own their external resources/runtime, but their IDs, status, capabilities, completion claims, callbacks, and data are observations until VibeFlow validates and binds them.
- Mobile/web/workspace-web clients are untrusted requestors. A client-supplied identifier never proves tenant, project, resource, grant, or approval scope.
- Every privileged boundary crossing must authenticate the actor/channel, authorize against canonical server-side scope, validate the message/resource binding, minimize data, and create audit/evidence appropriate to risk.
- Capability discovery and tool availability never grant permission. `ConnectionGrant`, `Policy`, and `Approval` remain separate VibeFlow authorities.
- If identity, scope, origin, version, continuity, or resource binding cannot be proven, the operation fails closed or enters an explicit reconciliation/approval flow.
- Provider-specific trust handling remains behind adapters; core authority rules do not vary by provider.

## TB-001 — Client → Gateway

- **Source:** Native mobile app, first-party web app, or workspace-web client.
- **Destination:** VibeFlow Gateway/API edge.
- **Trust:** Source is an untrusted requestor even after authentication; device/client state may be stale or compromised.
- **Authentication:** Validate the VibeFlow session/access token and current session state server-side.
- **Authorization:** Resolve Account/Organization/Project/resource scope server-side; never authorize from client IDs alone.
- **Allowed data/actions:** Versioned requests, opaque refs, user intent, bounded commands supported by the authenticated session.
- **Forbidden:** Raw provider/BYOK secrets in ordinary APIs; client assertion of role, grant, approval, canonical resource version, or execution truth.
- **Replay/confusion defense:** Request/message IDs, idempotency keys for durable commands, expected version where applicable, CSRF/origin protections for browser flows, and project/resource binding.
- **Audit/evidence:** Record principal, session, tenant/project/resource, command, policy/approval references, result, and correlation identifiers for privileged actions.

## TB-002 — Gateway → Control Plane

- **Source:** Authenticated VibeFlow Gateway.
- **Destination:** Authoritative VibeFlow Control Plane.
- **Trust:** Gateway authenticates transport/session context; Control Plane still validates authorization and domain invariants.
- **Authentication:** Service identity plus authenticated actor/session context.
- **Authorization:** Canonical server-side policy for tenant/project/resource and command.
- **Allowed data/actions:** Normalized commands/events carrying authenticated actor context and bounded resource references.
- **Forbidden:** Trusting edge/client-derived authorization conclusions without authoritative revalidation where required.
- **Replay/confusion defense:** Correlation/message IDs, idempotency/deduplication, expected resource versions, and canonical resource lookup.
- **Audit/evidence:** Preserve actor/session provenance and policy/approval revision through the authoritative transition.

## TB-003 — Control Plane → Secret Broker/KMS

- **Source:** Authorized Control Plane execution/token broker path.
- **Destination:** Approved encrypted secret broker/KMS boundary.
- **Trust:** Broker/KMS is the only approved raw-secret custody boundary; callers receive no ambient secret access.
- **Authentication:** Strong service identity to the broker/KMS.
- **Authorization:** Secret access is scoped to exact tenant/project/binding/grant/purpose and execution where applicable.
- **Allowed data/actions:** `SecretRef`, metadata, bounded secret enrollment, and minimum necessary runtime secret release to an approved channel.
- **Forbidden:** Returning raw secrets through ordinary project APIs or placing them in prompts, event payloads, evidence, logs, analytics, support data, or the native-web bridge.
- **Replay/confusion defense:** Short-lived issuance, purpose/audience binding, revocation, rotation, and non-reusable exchange where supported.
- **Audit/evidence:** Record reference, purpose, recipient class, policy/grant, issuance/revocation metadata without recording plaintext secret material.

## TB-004 — Control Plane → Agent Provider

- **Source:** VibeFlow Control Plane/Agent adapter.
- **Destination:** External coding-agent provider/runtime.
- **Trust:** Agent is an untrusted executor. Agent text, events, provider status, and finish claims are observations, not VibeFlow authority.
- **Authentication:** Provider account/binding authentication via approved brokered credentials or provider session.
- **Authorization:** Agent actions are limited by VibeFlow Task/Execution, project, workspace, tool grants, policy, and approvals.
- **Allowed data/actions:** Bounded task context, normalized lifecycle/control operations, opaque refs, and only specifically authorized capabilities.
- **Forbidden:** Treating agent finish as `VERIFIED`; granting ambient tool/secret/repository/deployment authority; trusting prompt/tool/repository content as policy.
- **Replay/confusion defense:** Bind provider session IDs to `AgentBinding`/ExecutionAttempt; deduplicate control messages; reject stale/malformed/misbound events.
- **Audit/evidence:** Persist normalized events, provider references, controls, capability observations, attempt lineage, and verification candidate evidence.

## TB-005 — Control Plane/Agent → Workspace Provider

- **Source:** VibeFlow workspace adapter and authorized agent execution.
- **Destination:** External workspace/sandbox provider and workspace processes.
- **Trust:** Workspace is a hostile-capable, mutable execution environment; provider isolation is a certified capability, not assumed.
- **Authentication:** Provider/binding identity and workspace session authentication.
- **Authorization:** Exact tenant/project/WorkspaceBinding/Execution scope with permitted filesystem/process/network capabilities.
- **Allowed data/actions:** Project-scoped files, processes, terminal/preview operations, bounded environment values, and certified provider capabilities.
- **Forbidden:** Cross-tenant/project access, implicit production authority, uncontrolled credential exposure, or treating mutable workspace state as canonical repository/project truth.
- **Replay/confusion defense:** Bind workspace/provider IDs to canonical `WorkspaceBinding`; verify session/resource identity on attach; reconcile revisions after reconnect or uncertain state.
- **Audit/evidence:** Record provider/workspace refs, observed capabilities, lifecycle, revision/hash observations, network/security results, cleanup, and certification evidence.

## TB-006 — Agent/Control Plane → Tool/Connection/MCP

- **Source:** Authorized VibeFlow execution/tool broker or agent through that broker.
- **Destination:** External tool, connection, API, or MCP server.
- **Trust:** Tool availability, schemas, descriptions, returned data, and server behavior are untrusted input.
- **Authentication:** Connection-specific credential or OAuth/token channel mediated by VibeFlow.
- **Authorization:** Active `ConnectionGrant` scope plus `Policy`; `Approval` when the action is privileged/high-risk.
- **Allowed data/actions:** Only grant-scoped tool calls and minimum necessary data/credentials.
- **Forbidden:** Ambient connection authority, tool self-authorization, grant escalation from tool metadata, or following prompt-injected instructions that bypass policy.
- **Replay/confusion defense:** Bind call to connection/grant/project/execution; validate call arguments; idempotency for durable/destructive calls where supported; enforce approval freshness.
- **Audit/evidence:** Record tool identity, grant/policy/approval refs, sanitized inputs/outputs, result, correlation, and provider request reference.

## TB-007 — Control Plane → Model Provider

- **Source:** VibeFlow-owned inference path through `ModelBinding`.
- **Destination:** External model provider.
- **Trust:** Model output is untrusted generated data; provider-reported model/status/usage are observations subject to normalization.
- **Authentication:** Brokered provider credential/key reference; raw key is not client-visible.
- **Authorization:** Exact ModelBinding, tenant/project/execution purpose, policy, entitlement/budget.
- **Allowed data/actions:** Minimum prompt/context allowed for the inference purpose and provider.
- **Forbidden:** Raw BYOK in client state/bridge/events; model output directly granting authority or bypassing policy.
- **Replay/confusion defense:** Bind request/response to ModelBinding and execution/correlation; validate provider/model profile and budget policy.
- **Audit/evidence:** Record provider/model attribution when observable, usage/cost observations, sanitized request metadata, and policy outcome.

## TB-008 — Control Plane → Repository/Git Host

- **Source:** Repository adapter and authorized VibeFlow command.
- **Destination:** External Git/repository provider.
- **Trust:** Repository provider owns repo bytes/history; provider IDs/webhooks/status are external observations. Repository content may be malicious.
- **Authentication:** Repository connection/binding credential through approved broker.
- **Authorization:** Exact Organization/Project/RepositoryBinding, repository scope, branch/ref/action, grant/policy/approval for privileged writes.
- **Allowed data/actions:** Authorized clone/fetch/status/diff/history/commit/push/import operations.
- **Forbidden:** Equating RepositoryBinding with Project or Workspace; cross-project repo access; unapproved destructive/ref-changing operations.
- **Replay/confusion defense:** Bind repo/provider IDs server-side; use exact refs/expected revisions where applicable; reconcile repo/workspace before claims about state.
- **Audit/evidence:** Record provider repo/ref/SHA observations, actor/grant/policy/approval, write result, and reconciliation evidence.

## TB-009 — Control Plane → Data/Object Storage Provider

- **Source:** VibeFlow data/storage adapter.
- **Destination:** External database/data/object-storage provider.
- **Trust:** Provider owns external bytes/runtime; VibeFlow owns binding metadata and product authority. Object storage is not a workspace.
- **Authentication:** Provider-specific credential via approved broker.
- **Authorization:** Exact tenant/project/binding/environment/resource scope and policy.
- **Allowed data/actions:** Binding-scoped data/storage operations and evidence/artifact bytes as defined by resource contracts.
- **Forbidden:** Dev/prod environment confusion, cross-tenant prefixes/resources, using object storage as execution workspace, or treating provider metadata as VibeFlow authority.
- **Replay/confusion defense:** Environment/binding/resource identifiers resolved server-side; version/checksum/precondition semantics where applicable.
- **Audit/evidence:** Record binding/environment, operation, sanitized target, provider reference, checksums/snapshot evidence where required.

## TB-010 — Control Plane → Deployment Provider/Production

- **Source:** VibeFlow deployment/release path.
- **Destination:** External deployment provider and production runtime.
- **Trust:** Provider owns runtime; deployment status is observed. Production authority is separate from development workspace authority.
- **Authentication:** DeploymentBinding credential through approved broker.
- **Authorization:** Exact tenant/project/DeploymentBinding/Release with policy and approval for privileged/irreversible production actions.
- **Allowed data/actions:** Release-scoped deploy/status/domain/access/rollback operations backed by required verification evidence.
- **Forbidden:** Deploying from an unverified arbitrary workspace claim, treating dev workspace as production, or unapproved destructive production changes.
- **Replay/confusion defense:** Bind deployment command to immutable release/evidence identifiers; idempotency/deduplication and expected deployment version where supported.
- **Audit/evidence:** Record release, evidence/verification refs, provider deployment ID/status observations, actor/policy/approval, and rollback lineage.

## TB-011 — Native Shell ↔ Workspace-Web Bridge

- **Source:** Native mobile shell or embedded/linked workspace-web surface.
- **Destination:** The other bridge endpoint.
- **Trust:** Both UI surfaces are non-authoritative request/inspection surfaces; embedded web content may be malicious or stale.
- **Authentication:** Bridge session bound to authenticated account/session, app build, project, WorkspaceBinding, allowed origin, version, and negotiated capabilities.
- **Authorization:** Sensitive actions require explicit bridge permission and backend grant/policy/approval where relevant.
- **Allowed data/actions:** Versioned UI/workspace actions defined by the bridge contract, opaque refs, ACK/error/performance messages.
- **Forbidden:** Raw BYOK/provider tokens, backend authority transfer, accepting messages from an unbound origin/project/session/workspace, or silent OAuth/permission elevation.
- **Replay/confusion defense:** Validate envelope version/id/direction/project/workspace/origin/session, correlation and ACK semantics; reject stale/misbound messages.
- **Audit/evidence:** Security-relevant permission/OAuth/native actions correlate to backend audit/evidence without logging secret payloads.

## TB-012 — External Callback/Webhook → Gateway/Control Plane

- **Source:** External provider callback, webhook, OAuth redirect, or provider event endpoint.
- **Destination:** VibeFlow ingress/Gateway and owning Control Plane adapter.
- **Trust:** Network source and payload are untrusted until authenticated/verified and correlated to a known binding/request.
- **Authentication:** Provider-supported signature, state/nonce, mTLS, token, or equivalent authenticated callback mechanism as applicable.
- **Authorization:** Callback may update only the exact canonical binding/resource/action it is correlated to; it cannot grant new authority by itself.
- **Allowed data/actions:** Expected event/callback types within known provider/binding context.
- **Forbidden:** Unsigned/unverified state-changing callbacks, provider-supplied tenant/project identity as sole authority, or callback-created privilege escalation.
- **Replay/confusion defense:** Signature timestamp/nonce/event ID/state correlation, deduplication, expected provider/binding/resource checks.
- **Audit/evidence:** Record verification outcome, provider/event reference, correlation, affected canonical resource, and rejected replay/spoof attempts.

## TB-013 — Verification/Evidence ↔ Evidence Sources

- **Source:** VibeFlow Verification service/check adapter.
- **Destination:** Workspace, repository, CI/security scanner, provider API, build/test result, artifact store, or other evidence source.
- **Trust:** Evidence source may be external, stale, interrupted, forged, or influenced by the agent being evaluated.
- **Authentication:** Authenticate the evidence source/channel when possible and bind it to exact project/execution/revision/check.
- **Authorization:** Verification reads/runs only within the check's authorized project/resources and does not gain unrelated runtime authority.
- **Allowed data/actions:** Independent checks, hashes, source/provider references, timestamps, logs/results sanitized under evidence policy.
- **Forbidden:** Treating agent/provider assertion alone as proof; treating interrupted/unavailable/unknown checks as pass; accepting evidence for a different revision/resource.
- **Replay/confusion defense:** Bind evidence to exact revision/check/execution, hash immutable evidence where applicable, record freshness/source, reject stale/mismatched artifacts.
- **Audit/evidence:** Verification itself produces VibeFlow-owned `Evidence`, `Verification`, and `VerificationCheck` records with provenance and immutable references where feasible.

## Boundary coverage rule

Every threat in `08_SECURITY/THREAT_MODEL.md` names the boundary or boundaries it crosses. Provider documentation alone never proves a boundary is safe; later adapter/certification missions must produce observed negative evidence.
