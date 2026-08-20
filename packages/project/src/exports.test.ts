import { describe, expect, it } from "vitest";

import * as packageRoot from "./index.js";
import {
  ARCHIVE_FORMATS,
  ARCHIVE_MANIFEST_VERSION,
  ARCHIVE_REJECTION_CODES,
  ARTIFACT_RELATION_KINDS,
  ArchiveRejectedError,
  ArtifactAuthorizationError,
  ArtifactError,
  ArtifactInputError,
  ArtifactNotFoundError,
  ArtifactRelationError,
  ArtifactService,
  DEFAULT_ARCHIVE_SCAN_LIMITS,
  InMemoryArchiveStaging,
  ProjectCloneError,
  ProjectCloneService,
  ProjectError,
  ProjectImportError,
  ProjectImportService,
  resolveArchiveScanLimits,
  scanArchive,
  stagedArchiveRefFor,
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

describe("M-014 @vibeflow/project package-root export surface", () => {
  it("exports the import and clone lifecycle services as constructible classes", () => {
    expect(ProjectImportService).toBeTypeOf("function");
    expect(ProjectImportService.prototype.constructor.name).toBe("ProjectImportService");
    expect(ProjectCloneService).toBeTypeOf("function");
    expect(ProjectCloneService.prototype.constructor.name).toBe("ProjectCloneService");
  });

  it("exports the M-014 domain error hierarchy", () => {
    expect(ProjectImportError.prototype).toBeInstanceOf(ProjectError);
    expect(ProjectCloneError.prototype).toBeInstanceOf(ProjectError);
    expect(ArchiveRejectedError).toBeTypeOf("function");
    expect(new ArchiveRejectedError("path_traversal", "x").code).toBe("path_traversal");
  });

  it("exports the structural scanner, its limits and its rejection vocabulary", () => {
    expect(scanArchive).toBeTypeOf("function");
    expect(ARCHIVE_MANIFEST_VERSION).toBe("vibeflow.archive.manifest.v1");
    expect(resolveArchiveScanLimits).toBeTypeOf("function");
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxEntryCount).toBe(10_000);
    expect(Object.isFrozen(DEFAULT_ARCHIVE_SCAN_LIMITS)).toBe(true);
    expect(ARCHIVE_REJECTION_CODES).toContain("path_traversal");
    expect(ARCHIVE_REJECTION_CODES).toContain("symlink_entry");
    expect(ARCHIVE_REJECTION_CODES).toContain("compression_ratio_exceeded");
  });

  it("exports exactly the archive formats the master/ledger prove", () => {
    expect(ARCHIVE_FORMATS).toEqual(["zip", "tar"]);
  });

  it("exports the private staging port and its in-memory adapter", () => {
    expect(InMemoryArchiveStaging).toBeTypeOf("function");
    expect(stagedArchiveRefFor(Buffer.from("x"))).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it("does NOT re-export persistence/DB internals from the package root", () => {
    const forbidden = [
      "ProjectLifecycleRepository",
      "ProjectRepository",
      "ArtifactRepository",
      "TenantRepository",
      "createControlPlanePool",
      "applyCommittedSqlMigrations",
      "projectArchiveImports",
      "projectClonePlans",
      "projectCloneArtifactMap",
      "projectArchiveImportEntries",
      "artifacts",
      "artifactRelations",
      "projects",
      "CONTROL_PLANE_TABLES",
    ];
    for (const name of forbidden) {
      expect(Object.prototype.hasOwnProperty.call(packageRoot, name)).toBe(false);
    }
  });

  it("does not export an invented Import/Template canonical resource surface", () => {
    // M-014 adds no canonical Import/Template resource, catalog, or state
    // machine; nothing of that shape may leak into the public API.
    const invented = [
      "Import",
      "ImportService",
      "Template",
      "TemplateService",
      "TemplateCatalog",
      "ProjectImport",
      "IMPORT_STATES",
      "TEMPLATE_STATES",
      "CLONE_STATES",
    ];
    for (const name of invented) {
      expect(Object.prototype.hasOwnProperty.call(packageRoot, name)).toBe(false);
    }
  });
});
