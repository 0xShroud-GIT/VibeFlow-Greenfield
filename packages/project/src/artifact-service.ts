/**
 * M-013 Artifact / ArtifactRelation authority service.
 *
 * VibeFlow owns durable Artifact metadata and durable ArtifactRelation edges,
 * both rooted in canonical Project ownership. No client, agent, repository,
 * workspace, blob store or provider may assert canonical Project/Organization
 * ownership for an Artifact or relation.
 */

import {
  ARTIFACT_RELATION_KINDS,
  CrossProjectArtifactRelationError,
  isArtifactTypeToken,
  isUuid,
  NotFoundError,
  type ArtifactRelationKind,
  type ArtifactRelationRow,
  type ArtifactRepository,
  type ArtifactRow,
} from "@vibeflow/persistence";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import {
  ArtifactAuthorizationError,
  ArtifactInputError,
  ArtifactNotFoundError,
  ArtifactRelationError,
} from "./errors.js";

export interface ArtifactServiceOptions {
  artifacts: ArtifactRepository;
  authz: TenantAuthorizationService;
}

export interface CreateArtifactInput {
  accountId: string;
  projectId: string;
  type: string;
}

export interface GetArtifactInput {
  accountId: string;
  artifactId: string;
}

export interface ListArtifactsInput {
  accountId: string;
  projectId: string;
}

export interface CreateArtifactRelationInput {
  accountId: string;
  subjectArtifactId: string;
  objectArtifactId: string;
  relationKind: ArtifactRelationKind;
}

export interface GetArtifactRelationInput {
  accountId: string;
  relationId: string;
}

export interface ListArtifactRelationsInput {
  accountId: string;
  projectId: string;
}

function requireUuid(name: string, value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ArtifactInputError(`${name} is required`);
  }
  if (!isUuid(value)) {
    throw new ArtifactInputError(`${name} must be a UUID`);
  }
  return value;
}

function requireType(value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ArtifactInputError("type is required");
  }
  const trimmed = value.trim();
  if (!isArtifactTypeToken(trimmed)) {
    throw new ArtifactInputError(
      "type must be a 1-200 character identifier of [A-Za-z0-9] plus the separators '.', '_', '-', '/', ':' with no whitespace or control characters",
    );
  }
  return trimmed;
}

function requireRelationKind(value: ArtifactRelationKind): ArtifactRelationKind {
  if (!(ARTIFACT_RELATION_KINDS as readonly string[]).includes(value)) {
    throw new ArtifactInputError(
      `relationKind must be one of: ${ARTIFACT_RELATION_KINDS.join(", ")}`,
    );
  }
  return value;
}

export class ArtifactService {
  public constructor(private readonly options: ArtifactServiceOptions) {}

  public async createArtifact(input: CreateArtifactInput): Promise<ArtifactRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);
    const type = requireType(input.type);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "create",
      resource: { type: "project", id: projectId },
    });
    if (!decision.allowed) {
      throw new ArtifactAuthorizationError(
        `Artifact creation denied: ${decision.reason}`,
        decision.reason,
      );
    }

    return this.options.artifacts.createArtifact({ projectId, type });
  }

  public async getArtifact(input: GetArtifactInput): Promise<ArtifactRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const artifactId = requireUuid("artifactId", input.artifactId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "artifact", id: artifactId },
    });
    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ArtifactNotFoundError(`Artifact not found: ${artifactId}`);
      }
      throw new ArtifactAuthorizationError(
        `Artifact read denied: ${decision.reason}`,
        decision.reason,
      );
    }

    try {
      return await this.options.artifacts.getArtifactById(artifactId);
    } catch (error) {
      if (error instanceof NotFoundError) {
        throw new ArtifactNotFoundError(`Artifact not found: ${artifactId}`);
      }
      throw error;
    }
  }

  public async listArtifacts(input: ListArtifactsInput): Promise<ArtifactRow[]> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "project", id: projectId },
    });
    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ArtifactNotFoundError(`Project not found: ${projectId}`);
      }
      throw new ArtifactAuthorizationError(
        `Artifact list denied: ${decision.reason}`,
        decision.reason,
      );
    }

    return this.options.artifacts.listArtifactsForProject(projectId);
  }

  public async createArtifactRelation(
    input: CreateArtifactRelationInput,
  ): Promise<ArtifactRelationRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const subjectArtifactId = requireUuid("subjectArtifactId", input.subjectArtifactId);
    const objectArtifactId = requireUuid("objectArtifactId", input.objectArtifactId);
    const relationKind = requireRelationKind(input.relationKind);

    if (subjectArtifactId === objectArtifactId) {
      throw new ArtifactInputError("artifact relation must link two distinct artifacts");
    }

    await this.authorizeEndpointRead(accountId, subjectArtifactId);
    await this.authorizeEndpointRead(accountId, objectArtifactId);

    let subject: ArtifactRow;
    let object: ArtifactRow;
    try {
      subject = await this.options.artifacts.getArtifactById(subjectArtifactId);
      object = await this.options.artifacts.getArtifactById(objectArtifactId);
    } catch (error) {
      if (error instanceof NotFoundError) {
        throw new ArtifactNotFoundError("Artifact relation endpoint not found");
      }
      throw error;
    }

    if (subject.projectId !== object.projectId) {
      throw new ArtifactRelationError(
        "Artifact relation endpoints must belong to the same canonical Project",
      );
    }

    const relationProjectId = subject.projectId;
    const decision = await this.options.authz.authorize({
      accountId,
      action: "create",
      resource: { type: "project", id: relationProjectId },
    });
    if (!decision.allowed) {
      throw new ArtifactAuthorizationError(
        `Artifact relation creation denied: ${decision.reason}`,
        decision.reason,
      );
    }

    try {
      return await this.options.artifacts.createArtifactRelation({
        subjectArtifactId,
        objectArtifactId,
        relationKind,
      });
    } catch (error) {
      if (error instanceof CrossProjectArtifactRelationError) {
        throw new ArtifactRelationError(
          "Artifact relation endpoints must belong to the same canonical Project",
        );
      }
      throw error;
    }
  }

  private async authorizeEndpointRead(
    accountId: string,
    artifactId: string,
  ): Promise<void> {
    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "artifact", id: artifactId },
    });
    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ArtifactNotFoundError(`Artifact not found: ${artifactId}`);
      }
      throw new ArtifactAuthorizationError(
        `Artifact access denied: ${decision.reason}`,
        decision.reason,
      );
    }
  }

  public async getArtifactRelation(
    input: GetArtifactRelationInput,
  ): Promise<ArtifactRelationRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const relationId = requireUuid("relationId", input.relationId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "artifact_relation", id: relationId },
    });
    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ArtifactNotFoundError(`Artifact relation not found: ${relationId}`);
      }
      throw new ArtifactAuthorizationError(
        `Artifact relation read denied: ${decision.reason}`,
        decision.reason,
      );
    }

    try {
      return await this.options.artifacts.getArtifactRelationById(relationId);
    } catch (error) {
      if (error instanceof NotFoundError) {
        throw new ArtifactNotFoundError(`Artifact relation not found: ${relationId}`);
      }
      throw error;
    }
  }

  public async listArtifactRelations(
    input: ListArtifactRelationsInput,
  ): Promise<ArtifactRelationRow[]> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "project", id: projectId },
    });
    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ArtifactNotFoundError(`Project not found: ${projectId}`);
      }
      throw new ArtifactAuthorizationError(
        `Artifact relation list denied: ${decision.reason}`,
        decision.reason,
      );
    }

    return this.options.artifacts.listArtifactRelationsForProject(projectId);
  }
}
