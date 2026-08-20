export { ProjectService } from "./service.js";
export { ArtifactService } from "./artifact-service.js";
// M-014 Project import/template lifecycle services.
export { ProjectImportService } from "./import-service.js";
export { ProjectCloneService } from "./clone-service.js";
// M-015 Project Profile / Capability Profile / Overview services.
export { ProjectProfileService } from "./profile-service.js";
export { ProjectCapabilityProfileService } from "./capability-profile-service.js";
export { ProjectOverviewService } from "./overview-service.js";
// Canonical Artifact relation vocabulary (closed kind set + its union type)
// is part of the M-013 public contract. It is re-exported from the canonical
// persistence vocabulary, not duplicated here.
export { ARTIFACT_RELATION_KINDS, type ArtifactRelationKind } from "@vibeflow/persistence";
// M-014 archive intake vocabulary, also owned by the canonical persistence
// vocabulary so the service and repository never disagree.
export { ARCHIVE_FORMATS, type ArchiveFormat } from "@vibeflow/persistence";
export {
  ArtifactAuthorizationError,
  ArtifactError,
  ArtifactInputError,
  ArtifactNotFoundError,
  ArtifactRelationError,
  ProjectAuthorizationError,
  ProjectCapabilityProfileError,
  ProjectCloneError,
  ProjectError,
  ProjectImportError,
  ProjectInputError,
  ProjectNotFoundError,
  ProjectOverviewError,
  ProjectProfileError,
} from "./errors.js";
export type {
  CreateProjectInput,
  GetProjectInput,
  ListProjectsInput,
  UpdateProjectInput,
  ProjectServiceOptions,
} from "./service.js";
export type {
  ArtifactServiceOptions,
  CreateArtifactInput,
  CreateArtifactRelationInput,
  GetArtifactInput,
  GetArtifactRelationInput,
  ListArtifactRelationsInput,
  ListArtifactsInput,
} from "./artifact-service.js";
export type {
  ImportProjectArchiveInput,
  ImportProjectArchiveResult,
  ProjectImportServiceOptions,
} from "./import-service.js";
export type {
  CloneProjectInput,
  CloneProjectResult,
  ProjectCloneServiceOptions,
} from "./clone-service.js";
export type {
  ProjectProfileServiceOptions,
  GetProjectProfileInput,
  UpdateProjectProfileInput,
  ProjectProfileResult,
} from "./profile-service.js";
export type {
  ProjectCapabilityProfileServiceOptions,
  GetProjectCapabilityProfileInput,
  ReplaceProjectCapabilityProfileInput,
  ProjectCapabilityProfileResult,
} from "./capability-profile-service.js";
export type {
  ProjectOverviewServiceOptions,
  GetProjectOverviewInput,
  ProjectOverview,
  ImportProvenance,
  CloneProvenance,
} from "./overview-service.js";

/**
 * M-014 structural archive scanner public surface.
 *
 * The scanner, its rejection vocabulary and its safety limits are intentional
 * public contract: callers need to distinguish a hostile archive from an
 * authorization failure, and reviewers need the limits to be inspectable.
 *
 * NOTE: this is a STRUCTURAL scanner (container integrity, path safety, entry
 * kind, bounded resource use). It is NOT a malware scanner and M-014 makes no
 * malware-detection claim.
 */
export {
  ARCHIVE_MANIFEST_VERSION,
  scanArchive,
  type ArchiveFormatToken,
  type ArchiveManifest,
  type ArchiveManifestEntry,
  type ScanArchiveInput,
} from "./archive/scanner.js";
export {
  ARCHIVE_REJECTION_CODES,
  ArchiveRejectedError,
  type ArchiveRejectionCode,
} from "./archive/errors.js";
export {
  DEFAULT_ARCHIVE_SCAN_LIMITS,
  resolveArchiveScanLimits,
  type ArchiveScanLimits,
} from "./archive/limits.js";
/**
 * Private content-addressed archive staging port plus its in-memory adapter.
 *
 * This is NOT a canonical ObjectStorageBinding and advances no
 * storage/provider capability; it exists only so archive bytes stay out of
 * canonical Project/Artifact metadata rows.
 */
export {
  InMemoryArchiveStaging,
  stagedArchiveRefFor,
  type ArchiveStagingPort,
  type StagedArchiveRef,
} from "./archive/staging.js";

// Persistence/DB internals are deliberately NOT re-exported from this package
// root: no repositories, no Drizzle table objects, no control-plane database
// handle or connection pool, no row types, and no migration runner. Consumers
// depend on @vibeflow/persistence directly when they legitimately need those.
// (This comment intentionally avoids naming those symbols verbatim so the
// retained M-013 export-surface contract test can keep scanning this file for
// literal internal identifiers.)
