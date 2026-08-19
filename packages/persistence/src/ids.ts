import { randomUUID } from "node:crypto";

import { PersistenceInputError } from "./errors.js";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

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
 * True when `value` is a canonical VibeFlow UUID shape. Used by the M-010
 * authorization boundary to reject client/provider/scoped identifiers that are
 * never authoritative for a tenant/resource decision.
 */
export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}
