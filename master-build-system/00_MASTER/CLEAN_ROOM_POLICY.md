# Clean-room Boundary

Replit was analyzed to understand shipped capabilities, client-visible contracts, UX architecture and product boundaries. It is **not** an implementation source.

Allowed inputs:
- capability names and behavioral requirements,
- public documentation,
- protocol/interface observations,
- clean-room architectural conclusions,
- independent open-source projects and official SDKs under their licenses.

Disallowed implementation inputs:
- copied/decompiled Replit source as production code,
- extracted proprietary assets/branding,
- reconstructed proprietary prompts,
- private identifiers or hidden implementation text copied merely because it appeared in a binary.

If a requirement only exposes a private Replit outcome but not a safe implementation, VibeFlow designs independently using the canonical resource/invariant model.
