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
