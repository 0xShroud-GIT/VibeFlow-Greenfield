export { ProjectService } from "./service.js";
export { ArtifactService } from "./artifact-service.js";
// Canonical Artifact relation vocabulary (closed kind set + its union type)
// is part of the M-013 public contract. It is re-exported from the canonical
// persistence vocabulary, not duplicated here.
export { ARTIFACT_RELATION_KINDS, type ArtifactRelationKind } from "@vibeflow/persistence";
export {
  ArtifactAuthorizationError,
  ArtifactError,
  ArtifactInputError,
  ArtifactNotFoundError,
  ArtifactRelationError,
  ProjectAuthorizationError,
  ProjectError,
  ProjectInputError,
  ProjectNotFoundError,
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
