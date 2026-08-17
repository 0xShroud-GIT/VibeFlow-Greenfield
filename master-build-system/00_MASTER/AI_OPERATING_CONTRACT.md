# AI Engineering Operating Contract

Coding agents are implementation collaborators, not architectural authorities.

## Less-is-more context policy

A mission packet should normally include only:
1. current mission objective and explicit non-goals,
2. relevant invariants,
3. exact resource/state/API/event contracts,
4. approved harvest entries,
5. acceptance tests and evidence requirements,
6. touched files/modules.

Do not dump the whole pack into every mission.

## Agent discretion

Agents may decide local implementation details, naming inside a module, refactoring, test strategy and performance improvements **within the approved design space**.

Agents may not silently change resource authority, state-machine semantics, protocol ownership, dependency choices, security boundaries or verification semantics. Those require an ADR and master update.
