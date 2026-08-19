import { describe, expect, it } from "vitest";

import { sanitizeAuditMetadata } from "./metadata.js";
import { AuditInputError } from "./types.js";

describe("M-011 safe audit metadata", () => {
  it("keeps bounded investigation context", () => {
    expect(sanitizeAuditMetadata({ client: "web", retry: 2, flags: [true] })).toEqual({
      client: "web",
      retry: 2,
      flags: [true],
    });
  });

  it("omits secret-named fields and redacts secret-looking values", () => {
    const token = ["Bearer", "redaction-fixture-value"].join(" ");
    const passwordKey = ["pass", "word"].join("");
    const apiKey = ["api", "Key"].join("");
    const cookieKey = ["cook", "ie"].join("");
    const result = sanitizeAuditMetadata({
      [passwordKey]: "credential-fixture-one",
      [apiKey]: ["credential", "fixture", "two"].join("-"),
      observation: token,
      nested: { [cookieKey]: "credential-fixture-three", safe: "retained" },
    });
    expect(JSON.stringify(result)).not.toContain("credential-fixture-one");
    expect(JSON.stringify(result)).not.toContain("credential-fixture-two");
    expect(JSON.stringify(result)).not.toContain(token);
    expect(result).toEqual({ observation: "[REDACTED]", nested: { safe: "retained" } });
  });

  it("rejects forged actor/tenant/resource authority in metadata", () => {
    for (const metadata of [
      { actorAccountId: crypto.randomUUID() },
      { organization_id: crypto.randomUUID() },
      { tenantId: crypto.randomUUID() },
      { resourceId: crypto.randomUUID() },
    ]) {
      expect(() => sanitizeAuditMetadata(metadata)).toThrow(AuditInputError);
    }
  });

  it("fails safely on malformed, cyclic, oversized, or non-finite metadata", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic["self"] = cyclic;
    for (const value of ["raw", cyclic, { value: Number.NaN }, { value: "x".repeat(257) }]) {
      expect(() => sanitizeAuditMetadata(value)).toThrow(AuditInputError);
    }
  });
});
