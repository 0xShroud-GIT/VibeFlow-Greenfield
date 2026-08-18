/**
 * `@vibeflow/contracts` — public entrypoint for the generated contract catalog.
 *
 * The VibeFlow Master Build System is authoritative. Everything re-exported here
 * is DERIVED from it by `scripts/generate-contracts.py`; nothing in this package
 * defines product authority and no product implementation lives here.
 *
 * Contracts are JSON Schema first: each exported `*Schema` is a raw
 * JSON-Schema-compatible literal, and each exported type is derived from that
 * schema through TypeBox `Static<>` inference.
 *
 * Regenerate:  pnpm run contracts:generate
 * Verify:      pnpm run contracts:check
 */

export * from "./generated/catalog.js";

export const CONTRACTS_PACKAGE = "@vibeflow/contracts" as const;
