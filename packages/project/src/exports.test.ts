import { describe, expect, it } from "vitest";

import {
  ARTIFACT_RELATION_KINDS,
  ArtifactAuthorizationError,
  ArtifactError,
  ArtifactInputError,
  ArtifactNotFoundError,
  ArtifactRelationError,
  ArtifactService,
} from "./index.js";

describe("M-013 @vibeflow/project package-root export surface", () => {
  it("exports ArtifactService as a constructible class", () => {
    expect(ArtifactService).toBeTypeOf("function");
    // ArtifactService requires options at construction time; asserting the
    // prototype constructor identity is enough to prove it is the real class.
    expect(ArtifactService.prototype.constructor.name).toBe("ArtifactService");
  });

  it("exports the Artifact public error hierarchy", () => {
    expect(ArtifactError).toBeTypeOf("function");
    expect(ArtifactInputError.prototype).toBeInstanceOf(ArtifactError);
    expect(ArtifactNotFoundError.prototype).toBeInstanceOf(ArtifactError);
    expect(ArtifactAuthorizationError.prototype).toBeInstanceOf(ArtifactError);
    expect(ArtifactRelationError.prototype).toBeInstanceOf(ArtifactError);
  });

  it("exports the canonical relation-kind vocabulary", () => {
    expect(ARTIFACT_RELATION_KINDS).toEqual(["lineage", "variant", "derived-from", "contains"]);
  });
});
