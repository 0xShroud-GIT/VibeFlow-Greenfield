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
