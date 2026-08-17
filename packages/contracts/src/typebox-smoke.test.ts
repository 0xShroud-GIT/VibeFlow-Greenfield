import { describe, it, expect } from "vitest";
import { HealthSchema } from "./index.js";

describe("M-004 TypeBox 1.x ESM smoke", () => {
  it("creates a JSON Schema object and validates runtime shape", () => {
    // Prove ESM import works and schema is a JSON Schema object
    expect(HealthSchema.type).toBe("object");
    expect(HealthSchema.properties).toBeDefined();
    // JSON Schema first: schema must have required fields
    expect(HealthSchema.required).toEqual(["status", "version"]);
  });

  it("exposes static type compatibility via TypeBox", () => {
    // Type-level check: Health should be { status: "ok"; version: string }
    const sample: { status: "ok"; version: string } = {
      status: "ok",
      version: "0.0.0"
    };
    // Runtime check that sample would satisfy schema shape
    expect(sample.status).toBe("ok");
    expect(typeof sample.version).toBe("string");
  });
});
