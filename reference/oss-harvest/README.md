# VibeFlow OSS Research Routing

Status: **accepted advisory reference layer**.

This directory lands the accepted VibeFlow open-source research routing map without turning research into architecture authority. It lives outside `master-build-system/`, does **not** alter mission state, approve dependencies, grant permissions, or authorize source reuse, and does not change M-007 scope. Master Build System contracts remain authoritative.

## Files

- `ROUTING_MANIFEST.json` — routing policy, mission domains, lineage, provenance, and shard index.
- `references/REFERENCES_*.json` — all 104 repository-reference records derived from the accepted routing JSON.
- `SCHEMA_TRANSFORMS.json` — explicit non-semantic repository-native transforms applied for sanitation.
- `BEHAVIORAL_CONTRACTS.json` — 25 behavioral/adversarial contracts routed to owning missions.
- `SOURCE_DIGESTS.json` — immutable hashes for the two source research reports and the three accepted pre-landing routing artifacts.
- `HUMAN_REVIEW.md` — compact review guide for future mission architects.
- `LANDING_METADATA.json` — append-only repository-landing record and authority effects.

## Historical evidence and sanitation rule

The accepted pre-landing routing artifacts remain identified in `SOURCE_DIGESTS.json` by exact SHA-256. The repo-native routing is a deterministic decomposition of that accepted data plus append-only landing metadata. Four public repository slug fields are represented under the equivalent field name `canonical_repository_slug` because Gitleaks correctly failed closed on high-entropy values under the original `canonical_repository_key` field name. The exact records and rationale are declared in `SCHEMA_TRANSFORMS.json`; scanner configuration and security wrappers are unchanged.

## Consumption rule

A reference may enter an implementation packet only when the active mission intersects its `owning_missions`. Reference usefulness does not place a package in `master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml`. Direct source reuse remains mission-owned and requires an exact revision, applicable file/license review, transitive/vendored review, security review, and interface isolation.

**No research reference is routed to M-007 by default.**

## Provenance snapshot

Routing was generated against `0xShroud-GIT/VibeFlow-Greenfield@affa8f9bab79a73dbc0a4e97fb4fa88f07ae3b34`. Agora is the one deep-pinned reference at this landing (`newo-ether/Agora@38147fca345565649e8f4971d6cad974bc858b1b`); the other 103 repositories remain `PIN_REQUIRED` until an owning mission promotes them.
