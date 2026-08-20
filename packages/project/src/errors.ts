export class ProjectError extends Error {
  override readonly name: string = "ProjectError";
}

export class ProjectInputError extends ProjectError {
  override readonly name = "ProjectInputError";
}

export class ProjectNotFoundError extends ProjectError {
  override readonly name = "ProjectNotFoundError";
}

export class ProjectAuthorizationError extends ProjectError {
  override readonly name = "ProjectAuthorizationError";
  public constructor(
    message: string,
    public readonly reason: string,
  ) {
    super(message);
  }
}

export class ArtifactError extends Error {
  override readonly name: string = "ArtifactError";
}

export class ArtifactInputError extends ArtifactError {
  override readonly name = "ArtifactInputError";
}

export class ArtifactNotFoundError extends ArtifactError {
  override readonly name = "ArtifactNotFoundError";
}

export class ArtifactAuthorizationError extends ArtifactError {
  override readonly name = "ArtifactAuthorizationError";
  public constructor(
    message: string,
    public readonly reason: string,
  ) {
    super(message);
  }
}

export class ArtifactRelationError extends ArtifactError {
  override readonly name = "ArtifactRelationError";
}

/**
 * M-014 archive-import lifecycle failure that is not an input, authorization,
 * or archive-structure rejection (e.g. an idempotent-command conflict or an
 * opaque not-found/denied outcome that must not disclose existence).
 */
export class ProjectImportError extends ProjectError {
  override readonly name = "ProjectImportError";
}

/**
 * M-014 Project Clone Plan lifecycle failure, including the same-Organization
 * template policy denial. Cross-Organization/public template semantics remain
 * deferred; attempting them is an error, not a silent redirect.
 */
export class ProjectCloneError extends ProjectError {
  override readonly name = "ProjectCloneError";
}

/**
 * M-015 Project Profile error.
 */
export class ProjectProfileError extends ProjectError {
  override readonly name = "ProjectProfileError";
}

/**
 * M-015 Project Capability Profile error.
 */
export class ProjectCapabilityProfileError extends ProjectError {
  override readonly name = "ProjectCapabilityProfileError";
}

/**
 * M-015 Project Overview error.
 */
export class ProjectOverviewError extends ProjectError {
  override readonly name = "ProjectOverviewError";
}
