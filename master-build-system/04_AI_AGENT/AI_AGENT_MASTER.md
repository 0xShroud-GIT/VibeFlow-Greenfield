# AI / Agent Master

## Separation of concerns

- `AgentBinding`: coding/general agent runtime and negotiated capabilities.
- `ModelBinding`: inference provider/model/key policy used by VibeFlow or an agent where supported.
- `WorkspaceBinding`: where code/processes actually execute.
- `Task`: durable user intent and success criteria.
- `Execution`: one authoritative attempt to satisfy a Task with explicit bindings/revision/policy.

These are never collapsed.

## Lifecycle

Human/automation → Task → Execution → agent session → plan/tool/workspace actions → candidate completion → workspace/repository reconciliation → Verification → VERIFIED/FAILED.

## Agent authority

Agents may propose plans, mutate within authorized Build policy, request tools, request approvals and report status. They cannot directly grant themselves permissions, expose secrets, change project authority, or mark Verification passed.

## Plan / Build

Plan mode is read-only except safe metadata/plan artifacts. Build mode permits explicitly granted mutations. The policy is server-enforced, not merely prompt text.

## Context and memory

Context is scoped to Project/Task/Execution and has provenance. Long-term memory is a separately governed resource/feature; do not silently dump cross-project history into prompts. Secret-bearing context is redacted/brokered.

## Delegation

Use A2A when communicating with independently addressable agents. Child/subagent delegation must attenuate grants: a child cannot receive more authority than its parent execution.
