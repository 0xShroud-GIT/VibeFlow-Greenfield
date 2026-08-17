# Security Master

Security is defined around authorities, explicit grants, verified bindings, and evidence rather than around trusting the agent, workspace, client, model, tool, or provider.

## Normative security contract

The following documents are jointly normative and must remain coherent:

- `02_ARCHITECTURE/TRUST_BOUNDARIES.md` — canonical boundary IDs and crossing rules.
- `08_SECURITY/THREAT_MODEL.md` — canonical assets, threat IDs, required controls, evidence expectations, and invariant crosswalk.
- `08_SECURITY/SECRET_HANDLING.md` — raw-secret custody and release boundary.
- `08_SECURITY/WORKSPACE_ISOLATION.md` — workspace-provider certification/isolation requirements.
- `08_SECURITY/SUPPLY_CHAIN.md` — dependency/build provenance controls.
- `00_MASTER/NON_NEGOTIABLE_INVARIANTS.yaml` — product invariants that security controls must preserve.

Where a provider protocol or SDK offers weaker semantics, VibeFlow must add a containing adapter/policy/reconciliation control or mark the capability unsupported. Provider behavior never silently weakens this contract.

## Constitutional security principles

1. **Authority is server-side and explicit.** Clients and external providers may request/report; they do not assert VibeFlow product truth.
2. **Least privilege is multi-dimensional.** Authenticate the actor/channel, then authorize tenant, project, resource, action, grant, policy revision, approval, and environment as applicable.
3. **Availability is not permission.** A discovered tool/provider capability never creates a grant.
4. **External content is data, not instruction authority.** Repository text, tool output, model output, agent output, workspace files, provider events, and web content are untrusted inputs when they cross into VibeFlow policy/control decisions.
5. **Secrets have one raw custody boundary.** Plaintext credentials exist only in the approved broker/KMS path and the minimum authorized provider/tool channel for the shortest practical lifetime.
6. **Privileged and irreversible actions are explicit.** They require policy/evidence semantics, fresh approval where policy requires it, and durable idempotency/deduplication.
7. **Execution claims are not verification.** Completion/status from agents/providers is candidate/observation only; verification needs independent evidence where feasible.
8. **Mutable state is reconciled before trust.** Workspace/repository/provider state that may have changed outside VibeFlow is reconciled/bound to exact revisions before verification or release claims.
9. **Continuity is proven, not guessed.** Reconnect/replay gaps, stale versions, unknown callback state, or ambiguous resource binding enter resync/reconciliation or fail closed.
10. **Negative isolation evidence is required.** Security tests prove forbidden tenant/project/resource/secret/tool/provider crossings fail; happy-path tests alone are insufficient.
11. **Provider differences stay behind adapters.** Core authority semantics do not contain provider-specific exceptions.
12. **Do not invent cryptography or security protocols.** Use approved standards/libraries/providers under the harvest policy, then wrap or constrain them to this authority model.

## Required control families

- authentication/session security,
- tenant/project/resource authorization,
- provider account linking and canonical binding validation,
- SecretRef/KMS envelope and token brokerage,
- ConnectionGrant least privilege and revocation,
- agent/tool/workspace permissions,
- policy-revision binding and approval for privileged/irreversible actions,
- durable command idempotency/replay defenses,
- workspace sandbox/network egress/resource quotas and certification,
- repository/workspace revision reconciliation,
- native-web bridge origin/session/project/workspace binding,
- external callback/webhook authenticity, correlation and replay defense,
- supply-chain/dependency/container/static scanning,
- independent verification and evidence provenance/integrity,
- audit plus redaction in logs/telemetry/support,
- abuse/rate/budget/runaway-execution controls.

## Failure stance

If VibeFlow cannot prove identity, scope, binding, freshness, continuity, approval, or required verification evidence, it **fails closed** for the privileged action. A degraded read-only projection may remain available when it cannot create authority or misrepresent canonical state.

Security tests are negative by default: prove one tenant, project, agent, tool, workspace, provider, callback, or stale client cannot cross a boundary it does not own.
