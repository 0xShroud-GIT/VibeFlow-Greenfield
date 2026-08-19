import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function sha256(path) {
  return createHash("sha256").update(readFileSync(resolve(process.cwd(), path))).digest("hex");
}

describe("temporary mission closure checksum diagnostic", () => {
  it("prints exact MBS hashes without mutating authority", () => {
    const dag = sha256("../../master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml");
    const register = sha256("../../master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv");
    console.log(`M012_CLOSURE_DAG_SHA256=${dag}`);
    console.log(`M012_CLOSURE_REGISTER_SHA256=${register}`);
    expect(dag).toMatch(/^[0-9a-f]{64}$/);
    expect(register).toMatch(/^[0-9a-f]{64}$/);
  });
});
