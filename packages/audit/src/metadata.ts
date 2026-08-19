import { AuditInputError } from "./types.js";

const MAX_DEPTH = 3;
const MAX_KEYS = 32;
const MAX_ARRAY = 20;
const MAX_STRING = 256;
const MAX_SERIALIZED_BYTES = 4096;

const AUTHORITY_KEY = /^(actor|actor_?account_?id|subject_?account_?id|account_?id|organization_?id|tenant_?id|resource_?id|occurred_?at|event_?id)$/i;
const SECRET_KEY = /(password|passphrase|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key|session[_-]?token)/i;
const SECRET_VALUE = /^(?:Bearer\s+|Basic\s+|sk-[A-Za-z0-9]|gh[pousr]_|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.)/i;

/**
 * Normalize bounded JSON metadata. Authority-shaped keys are rejected, secret
 * fields are omitted, and secret-looking string values are replaced. Audit
 * callers never gain a raw-payload escape hatch.
 */
export function sanitizeAuditMetadata(input: unknown): Record<string, unknown> {
  if (input === undefined) return {};
  if (!isPlainObject(input)) {
    throw new AuditInputError("audit metadata must be a plain object");
  }
  const normalized = normalizeObject(input, 0);
  if (new TextEncoder().encode(JSON.stringify(normalized)).byteLength > MAX_SERIALIZED_BYTES) {
    throw new AuditInputError("audit metadata exceeds the 4096-byte limit");
  }
  return normalized;
}

function normalizeObject(input: Record<string, unknown>, depth: number): Record<string, unknown> {
  if (depth > MAX_DEPTH) throw new AuditInputError("audit metadata is too deeply nested");
  const entries = Object.entries(input);
  if (entries.length > MAX_KEYS) throw new AuditInputError("audit metadata has too many keys");
  const output: Record<string, unknown> = {};
  for (const [key, value] of entries) {
    if (AUTHORITY_KEY.test(key)) {
      throw new AuditInputError(`audit metadata cannot claim authority field: ${key}`);
    }
    if (SECRET_KEY.test(key)) continue;
    output[key] = normalizeValue(value, depth + 1);
  }
  return output;
}

function normalizeValue(value: unknown, depth: number): unknown {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new AuditInputError("audit metadata numbers must be finite");
    return value;
  }
  if (typeof value === "string") {
    if (value.length > MAX_STRING) throw new AuditInputError("audit metadata strings are too long");
    return SECRET_VALUE.test(value) ? "[REDACTED]" : value;
  }
  if (Array.isArray(value)) {
    if (value.length > MAX_ARRAY) throw new AuditInputError("audit metadata arrays are too long");
    if (depth > MAX_DEPTH) throw new AuditInputError("audit metadata is too deeply nested");
    return value.map((item) => normalizeValue(item, depth + 1));
  }
  if (isPlainObject(value)) return normalizeObject(value, depth);
  throw new AuditInputError("audit metadata contains an unsupported value");
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value) as object | null;
  return prototype === Object.prototype || prototype === null;
}
