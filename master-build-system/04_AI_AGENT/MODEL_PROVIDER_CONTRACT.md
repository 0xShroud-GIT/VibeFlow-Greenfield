# Model Provider Contract

ModelBinding stores provider/model/profile/key reference and policy, never raw key material in client-visible state.

VibeFlow-owned inference uses an approved provider abstraction/SDK. Agent-owned inference may occur inside an Agent provider; in that case VibeFlow records model/provider attribution when observable but does not pretend to control unobservable internals.

Budget/spend policies attach to ModelBinding and Execution where supported.
