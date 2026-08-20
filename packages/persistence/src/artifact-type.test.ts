import { describe, expect, it } from "vitest";

import { PersistenceInputError } from "./errors.js";
import {
  ARTIFACT_TYPE_TOKEN_MAX_LENGTH,
  isArtifactTypeToken,
  requireArtifactTypeToken,
} from "./ids.js";

describe("M-013 Artifact type opaque-token grammar", () => {
  it("accepts simple, namespaced, and compound opaque tokens", () => {
    const valid = [
      "website",
      "mobile",
      "slides",
      "design",
      "animation",
      "data",
      "app",
      "image",
      "report",
      "com.acme.website",
      "slides:v2",
      "react-app",
      "design/hero",
      "data_dump",
      "a1",
      "A",
      "Z9",
      "ns.sub-ns/type:variant",
    ];
    for (const value of valid) {
      expect(isArtifactTypeToken(value), `should accept ${JSON.stringify(value)}`).toBe(true);
      expect(requireArtifactTypeToken("type", value)).toBe(value);
    }
  });

  it("trims outer whitespace as canonicalization", () => {
    expect(requireArtifactTypeToken("type", "  website  ")).toBe("website");
    expect(isArtifactTypeToken("  website  ")).toBe(false);
  });

  it("rejects empty and blank values", () => {
    for (const value of ["", "   ", "\t", "\n"]) {
      expect(isArtifactTypeToken(value)).toBe(false);
      expect(() => requireArtifactTypeToken("type", value)).toThrow(PersistenceInputError);
    }
  });

  it("rejects values over the maximum length", () => {
    const tooLong = "a".repeat(ARTIFACT_TYPE_TOKEN_MAX_LENGTH + 1);
    expect(tooLong.length).toBe(201);
    expect(isArtifactTypeToken(tooLong)).toBe(false);
    expect(() => requireArtifactTypeToken("type", tooLong)).toThrow(PersistenceInputError);

    const atLimit = "a".repeat(ARTIFACT_TYPE_TOKEN_MAX_LENGTH);
    expect(isArtifactTypeToken(atLimit)).toBe(true);
  });

  it("rejects control characters", () => {
    for (const value of ["a\u0000b", "a\u0007b", "a\u001fb", "a\u007fb"]) {
      expect(isArtifactTypeToken(value)).toBe(false);
      expect(() => requireArtifactTypeToken("type", value)).toThrow(PersistenceInputError);
    }
  });

  it("rejects embedded whitespace and malformed token syntax", () => {
    const invalid = [
      "two words",
      "a\tb",
      "a\nb",
      "a\rb",
      ".leading",
      "trailing.",
      "-leading",
      "_leading",
      "/leading",
      ":leading",
      "trailing-",
      "trailing_",
      "trailing/",
      "trailing:",
      "has space",
      "a+b",
      "a=b",
      "a@b",
      "a#b",
      "a,b",
      "a;b",
      "a(b)",
      "emoji🙂",
      "café",
    ];
    for (const value of invalid) {
      expect(isArtifactTypeToken(value), `should reject ${JSON.stringify(value)}`).toBe(false);
      expect(() => requireArtifactTypeToken("type", value)).toThrow(PersistenceInputError);
    }
  });

  it("does not invent a closed taxonomy: arbitrary conforming tokens are accepted", () => {
    // Open-ended: no registry of known types exists; any token matching the
    // grammar is accepted, proving this is syntax validation, not a taxonomy.
    expect(isArtifactTypeToken("totally:unknown/type-token_9")).toBe(true);
  });
});
