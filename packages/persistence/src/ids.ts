import { randomUUID } from "node:crypto";

import { PersistenceInputError } from "./errors.js";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * M-015 capability key grammar.
 *
 * Open, provider-neutral, namespaced token grammar suitable for future
 * extension. Two or more lower-case segments separated by '/', each segment
 * starts with a letter and may contain letters and digits.
 *
 * Grammar: ^[a-z][a-z0-9]*(/[a-z][a-z0-9]*)+$
 *
 * Examples: runtime/node, artifact/web, tooling/typescript
 * Rejected: control characters, whitespace, URLs, provider credentials,
 * provider resource IDs, raw JSON blobs, single-segment tokens.
 */
export const CAPABILITY_KEY_MAX_LENGTH = 200;
export const CAPABILITY_KEY_RE =
  /^[a-z][a-z0-9]*(?:\/[a-z][a-z0-9]*)+$/;

export function isCapabilityKeyToken(value: string): boolean {
  return CAPABILITY_KEY_RE.test(value);
}

export function requireCapabilityKey(value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new PersistenceInputError("capability key is required");
  }
  const trimmed = value.trim();
  if (trimmed.length > CAPABILITY_KEY_MAX_LENGTH) {
    throw new PersistenceInputError(
      `capability key must be ${CAPABILITY_KEY_MAX_LENGTH} characters or fewer`,
    );
  }
  if (!isCapabilityKeyToken(trimmed)) {
    throw new PersistenceInputError(
      "capability key must be two or more lower-case '/' separated segments (e.g. 'runtime/node')",
    );
  }
  return trimmed;
}

export function newId(): string {
  return randomUUID();
}

export function requireNonEmpty(name: string, value: string): string {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    throw new PersistenceInputError(`${name} is required`);
  }
  return trimmed;
}

export function requireId(name: string, value: string): string {
  const id = requireNonEmpty(name, value);
  if (!UUID_RE.test(id)) {
    throw new PersistenceInputError(`${name} must be a UUID`);
  }
  return id;
}

/**
 * M-013 Artifact `type` opaque-token grammar.
 *
 * Artifacts are typed outputs, but the canonical resource model defines no
 * closed taxonomy. `type` is therefore an OPAQUE, open-ended typed-output
 * token validated for syntax only — this is NOT a closed enum and NOT a
 * normalized type registry (VF-PRJ-017 remains deferred).
 *
 * Grammar (after trimming outer whitespace):
 *   - 1..200 characters total
 *   - first and last characters are ASCII letters/digits (`[A-Za-z0-9]`)
 *   - interior characters are ASCII letters/digits or one of the separators
 *     `.`, `_`, `-`, `/`, `:`
 *   - whitespace (including embedded), control characters, leading/trailing
 *     separators, and any other punctuation are rejected
 *
 * This admits namespaced/compound opaque tokens such as `com.acme.website`,
 * `slides:v2`, `react-app`, `design/hero`, `data_dump` while rejecting
 * malformed input (`" website "` is canonicalized to `"website"`, `"two words"`,
 * `"a\nb"`, `"leading-dot"`-style leading separators, and over-length tokens
 * are all rejected).
 */
export const ARTIFACT_TYPE_TOKEN_MAX_LENGTH = 200;
export const ARTIFACT_TYPE_TOKEN_RE =
  /^[A-Za-z0-9](?:[A-Za-z0-9._\-/:]{0,198}[A-Za-z0-9])?$/;

export function isArtifactTypeToken(value: string): boolean {
  return ARTIFACT_TYPE_TOKEN_RE.test(value);
}

export function requireArtifactTypeToken(name: string, value: string): string {
  const trimmed = requireNonEmpty(name, value);
  if (!isArtifactTypeToken(trimmed)) {
    throw new PersistenceInputError(
      `${name} must be a 1-${ARTIFACT_TYPE_TOKEN_MAX_LENGTH} character identifier of [A-Za-z0-9] plus the separators '.', '_', '-', '/', ':' with no whitespace or control characters`,
    );
  }
  return trimmed;
}

/**
 * True when `value` is a canonical VibeFlow UUID shape. Used by the M-010
 * authorization boundary to reject client/provider/scoped identifiers that are
 * never authoritative for a tenant/resource decision.
 */
export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}
