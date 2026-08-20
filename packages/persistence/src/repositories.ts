import { and, eq, sql } from "drizzle-orm";

import type { ControlPlaneDatabase } from "./client.js";
import {
  CrossProjectArtifactRelationError,
  DuplicateArtifactRelationError,
  DuplicateMembershipError,
  ForeignKeyViolationError,
  mapDatabaseError,
  NotFoundError,
  PersistenceInputError,
  PersistenceError,
  rejectProviderAuthority,
  StaleVersionError,
} from "./errors.js";
import { newId, requireArtifactTypeToken, requireCapabilityKey, requireId, requireNonEmpty } from "./ids.js";
import {
  accounts,
  ARTIFACT_RELATION_KINDS,
  artifactRelations,
  artifacts,
  identityUsers,
  ORGANIZATION_KINDS,
  organizationMemberships,
  organizations,
  projectCapabilities,
  projectProfiles,
  projects,
  type AccountRow,
  type ArtifactRelationKind,
  type ArtifactRelationRow,
  type ArtifactRow,
  type OrganizationKind,
  type OrganizationMembershipRow,
  type OrganizationRow,
  type ProjectCapabilityRow,
  type ProjectProfileRow,
  type ProjectRow,
} from "./schema.js";

export interface CreateAccountInput {
  displayName: string;
}

export interface CreateOrganizationInput {
  name: string;
  kind: OrganizationKind;
}

export interface CreateMembershipInput {
  organizationId: string;
  accountId: string;
}

export interface CreateProjectInput {
  organizationId: string;
  name: string;
}

export interface UpdateProjectInput {
  id: string;
  name: string;
}

export interface CreateArtifactInput {
  projectId: string;
  type: string;
}

export interface CreateArtifactRelationInput {
  subjectArtifactId: string;
  objectArtifactId: string;
  relationKind: ArtifactRelationKind;
}

function now(): Date {
  return new Date();
}

function isOrganizationKind(value: string): value is OrganizationKind {
  return (ORGANIZATION_KINDS as readonly string[]).includes(value);
}

function isArtifactRelationKind(value: string): value is ArtifactRelationKind {
  return (ARTIFACT_RELATION_KINDS as readonly string[]).includes(value);
}

interface PgLikeError {
  code?: string;
  constraint?: string;
  cause?: unknown;
}

function postgresErrorCode(error: unknown): string | undefined {
  let current: unknown = error;
  const seen = new Set<unknown>();
  while (current && typeof current === "object" && !seen.has(current)) {
    seen.add(current);
    const candidate = current as PgLikeError;
    if (typeof candidate.code === "string" && /^\d{5}$/.test(candidate.code)) {
      return candidate.code;
    }
    current = candidate.cause;
  }
  return undefined;
}

/** Maps ArtifactRelation-specific integrity violations to dedicated errors. */
function mapArtifactRelationError(error: unknown): never {
  const code = postgresErrorCode(error);
  if (code === "23505") {
    throw new DuplicateArtifactRelationError("artifact relation edge already exists");
  }
  if (code === "23503") {
    throw new ForeignKeyViolationError("referenced artifact does not exist");
  }
  if (error instanceof PersistenceError) {
    throw error;
  }
  throw new PersistenceError(error instanceof Error ? error.message : "persistence operation failed");
}

export class TenantRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  public async createAccount(input: CreateAccountInput): Promise<AccountRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const displayName = requireNonEmpty("displayName", input.displayName);
    const createdAt = now();
    const row = {
      id: newId(),
      displayName,
      createdAt,
      updatedAt: createdAt,
    };
    try {
      const inserted = await this.db.insert(accounts).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("account insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }

  public async getAccountById(accountId: string): Promise<AccountRow> {
    const id = requireId("accountId", accountId);
    const rows = await this.db.select().from(accounts).where(eq(accounts.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`account not found: ${id}`);
    }
    return row;
  }

  /**
   * Resolves an authenticated library user through the durable server-side
   * VibeFlow Account link. It deliberately returns no organization/role state.
   */
  public async findAccountByIdentityUserId(identityUserId: string): Promise<AccountRow | undefined> {
    const userId = requireId("identityUserId", identityUserId);
    const links = await this.db
      .select({ accountId: identityUsers.vibeflowAccountId })
      .from(identityUsers)
      .where(eq(identityUsers.id, userId));
    const link = links[0];
    if (!link) {
      return undefined;
    }

    const rows = await this.db.select().from(accounts).where(eq(accounts.id, link.accountId));
    return rows[0];
  }

  public async createOrganization(input: CreateOrganizationInput): Promise<OrganizationRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const name = requireNonEmpty("name", input.name);
    if (!isOrganizationKind(input.kind)) {
      throw new PersistenceInputError("organization kind must be personal or standard");
    }
    const createdAt = now();
    const row = {
      id: newId(),
      name,
      kind: input.kind,
      createdAt,
      updatedAt: createdAt,
    };
    try {
      const inserted = await this.db.insert(organizations).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("organization insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }

  public async getOrganizationById(organizationId: string): Promise<OrganizationRow> {
    const id = requireId("organizationId", organizationId);
    const rows = await this.db.select().from(organizations).where(eq(organizations.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`organization not found: ${id}`);
    }
    return row;
  }

  public async addMembership(input: CreateMembershipInput): Promise<OrganizationMembershipRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const organizationId = requireId("organizationId", input.organizationId);
    const accountId = requireId("accountId", input.accountId);
    const row = {
      id: newId(),
      organizationId,
      accountId,
      createdAt: now(),
    };
    try {
      const inserted = await this.db.insert(organizationMemberships).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("membership insert returned no row");
      }
      return created;
    } catch (error) {
      if (error instanceof DuplicateMembershipError || error instanceof ForeignKeyViolationError) {
        throw error;
      }
      mapDatabaseError(error);
    }
  }

  public async getMembership(input: CreateMembershipInput): Promise<OrganizationMembershipRow> {
    const organizationId = requireId("organizationId", input.organizationId);
    const accountId = requireId("accountId", input.accountId);
    const rows = await this.db
      .select()
      .from(organizationMemberships)
      .where(
        and(
          eq(organizationMemberships.organizationId, organizationId),
          eq(organizationMemberships.accountId, accountId),
        ),
      );
    const row = rows[0];
    if (!row) {
      throw new NotFoundError("organization membership not found");
    }
    return row;
  }

  /**
   * Persistence-boundary isolation: memberships are listed only for one
   * canonical organization id. There is no unscoped membership catalog.
   */
  public async listMembershipsForOrganization(organizationId: string): Promise<OrganizationMembershipRow[]> {
    const id = requireId("organizationId", organizationId);
    return this.db
      .select()
      .from(organizationMemberships)
      .where(eq(organizationMemberships.organizationId, id));
  }

  public async listOrganizationsForAccount(accountId: string): Promise<OrganizationRow[]> {
    const id = requireId("accountId", accountId);
    return this.db
      .select({
        id: organizations.id,
        name: organizations.name,
        kind: organizations.kind,
        createdAt: organizations.createdAt,
        updatedAt: organizations.updatedAt,
      })
      .from(organizationMemberships)
      .innerJoin(organizations, eq(organizations.id, organizationMemberships.organizationId))
      .where(eq(organizationMemberships.accountId, id));
  }

  public async createPersonalOrganizationForAccount(
    accountId: string,
    name: string,
  ): Promise<{ organization: OrganizationRow; membership: OrganizationMembershipRow }> {
    const account = await this.getAccountById(accountId);
    return this.db.transaction(async (tx) => {
      const scoped = new TenantRepository(tx);
      const organization = await scoped.createOrganization({
        name,
        kind: "personal",
      });
      const membership = await scoped.addMembership({
        organizationId: organization.id,
        accountId: account.id,
      });
      return { organization, membership };
    });
  }
}

export class ProjectRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  /**
   * Canonical Project creation.
   * Server-generated id, canonical organization ownership, server-controlled
   * timestamps, FK integrity. Provider/external ids are never accepted.
   */
  public async createProject(input: CreateProjectInput): Promise<ProjectRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const organizationId = requireId("organizationId", input.organizationId);
    const name = requireNonEmpty("name", input.name);
    const createdAt = now();
    const row = {
      id: newId(),
      organizationId,
      name,
      createdAt,
      updatedAt: createdAt,
    };
    try {
      const inserted = await this.db.insert(projects).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("project insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }

  public async getProjectById(projectId: string): Promise<ProjectRow> {
    const id = requireId("projectId", projectId);
    const rows = await this.db.select().from(projects).where(eq(projects.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`project not found: ${id}`);
    }
    return row;
  }

  /**
   * Tenant-safe list: projects are listed only for one canonical organization id.
   * There is no unscoped project catalog.
   */
  public async listProjectsForOrganization(organizationId: string): Promise<ProjectRow[]> {
    const id = requireId("organizationId", organizationId);
    return this.db.select().from(projects).where(eq(projects.organizationId, id));
  }

  public async updateProject(input: UpdateProjectInput): Promise<ProjectRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const id = requireId("id", input.id);
    const name = requireNonEmpty("name", input.name);
    const updatedAt = now();
    try {
      const updated = await this.db
        .update(projects)
        .set({ name, updatedAt })
        .where(eq(projects.id, id))
        .returning();
      const row = updated[0];
      if (!row) {
        throw new NotFoundError(`project not found: ${id}`);
      }
      return row;
    } catch (error) {
      if (error instanceof NotFoundError) {
        throw error;
      }
      mapDatabaseError(error);
    }
  }
}

/**
 * M-013 authoritative Artifact/ArtifactRelation persistence.
 *
 * Artifact authority is VibeFlow metadata only: server-generated id, canonical
 * Project FK, bounded type token, server-controlled timestamps. Content bytes
 * are never part of this boundary. ArtifactRelation Project ownership is
 * derived from the canonical endpoint Artifacts, never a client claim, and the
 * composite foreign keys make cross-Project edges impossible at the database
 * level even if service checks are bypassed.
 */
export class ArtifactRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  public async createArtifact(input: CreateArtifactInput): Promise<ArtifactRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const projectId = requireId("projectId", input.projectId);
    const type = requireArtifactTypeToken("type", input.type);
    const createdAt = now();
    const row = {
      id: newId(),
      projectId,
      type,
      createdAt,
      updatedAt: createdAt,
    };
    try {
      const inserted = await this.db.insert(artifacts).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("artifact insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }

  public async getArtifactById(artifactId: string): Promise<ArtifactRow> {
    const id = requireId("artifactId", artifactId);
    const rows = await this.db.select().from(artifacts).where(eq(artifacts.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`artifact not found: ${id}`);
    }
    return row;
  }

  /** Tenant-safe list: artifacts are listed only for one canonical project id. */
  public async listArtifactsForProject(projectId: string): Promise<ArtifactRow[]> {
    const id = requireId("projectId", projectId);
    return this.db.select().from(artifacts).where(eq(artifacts.projectId, id));
  }

  /**
   * Create a durable directed relation between two canonical Artifacts.
   *
   * The owning Project is derived from the canonical endpoint Artifacts and
   * must be identical for both; a cross-Project edge is rejected here (and, as
   * a backstop, by the composite foreign keys). self-edges are rejected and
   * relation_kind is restricted to the canonical kinds. No client-supplied
   * project_id is accepted.
   */
  public async createArtifactRelation(
    input: CreateArtifactRelationInput,
  ): Promise<ArtifactRelationRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const subjectArtifactId = requireId("subjectArtifactId", input.subjectArtifactId);
    const objectArtifactId = requireId("objectArtifactId", input.objectArtifactId);
    if (subjectArtifactId === objectArtifactId) {
      throw new PersistenceInputError(
        "artifact relation must link two distinct artifacts",
      );
    }
    if (!isArtifactRelationKind(input.relationKind)) {
      throw new PersistenceInputError(
        `relationKind must be one of: ${ARTIFACT_RELATION_KINDS.join(", ")}`,
      );
    }
    const relationKind = input.relationKind;

    // Resolve both endpoints from canonical persistence; unknown endpoints
    // fail closed as NotFoundError. The owning Project is derived here, never
    // from a client claim.
    const subject = await this.getArtifactById(subjectArtifactId);
    const object = await this.getArtifactById(objectArtifactId);
    if (subject.projectId !== object.projectId) {
      throw new CrossProjectArtifactRelationError(
        "artifact relation endpoints must belong to the same canonical Project",
      );
    }

    const createdAt = now();
    const row = {
      id: newId(),
      projectId: subject.projectId,
      subjectArtifactId,
      objectArtifactId,
      relationKind,
      createdAt,
    };
    try {
      const inserted = await this.db.insert(artifactRelations).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("artifact relation insert returned no row");
      }
      return created;
    } catch (error) {
      mapArtifactRelationError(error);
    }
  }

  public async getArtifactRelationById(relationId: string): Promise<ArtifactRelationRow> {
    const id = requireId("relationId", relationId);
    const rows = await this.db
      .select()
      .from(artifactRelations)
      .where(eq(artifactRelations.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`artifact relation not found: ${id}`);
    }
    return row;
  }

  /** Tenant-safe list: relations are listed only for one canonical project id. */
  public async listArtifactRelationsForProject(
    projectId: string,
  ): Promise<ArtifactRelationRow[]> {
    const id = requireId("projectId", projectId);
    return this.db
      .select()
      .from(artifactRelations)
      .where(eq(artifactRelations.projectId, id));
  }
}
/**
 * M-015 ProjectProfile repository.
 */
export class ProjectProfileRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  public async getProfileByProjectId(projectId: string): Promise<ProjectProfileRow | undefined> {
    const id = requireId("projectId", projectId);
    const rows = await this.db
      .select()
      .from(projectProfiles)
      .where(eq(projectProfiles.projectId, id));
    return rows[0];
  }

  public async upsertProfile(input: {
    projectId: string;
    expectedVersion: number;
    description: string | null;
    coverArtifactId: string | null;
  }): Promise<ProjectProfileRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const projId = requireId("projectId", input.projectId);
    const updatedAt = now();

    const existing = await this.getProfileByProjectId(projId);

    if (existing) {
      if (existing.version !== input.expectedVersion) {
        throw new StaleVersionError(
          "profile version conflict: expected " + input.expectedVersion + ", current " + existing.version,
        );
      }

      const rows = await this.db
        .update(projectProfiles)
        .set({
          description: input.description ?? null,
          coverArtifactId: input.coverArtifactId ?? null,
          version: existing.version + 1,
          updatedAt,
        })
        .where(and(eq(projectProfiles.projectId, projId), eq(projectProfiles.version, input.expectedVersion)))
        .returning();

      const row = rows[0];
      if (!row) {
        throw new StaleVersionError("profile version conflict: concurrent update");
      }
      return row;
    }

    if (input.expectedVersion !== 0) {
      throw new StaleVersionError(
        "profile version conflict: expected " + input.expectedVersion + ", no profile exists (version 0)",
      );
    }

    const createdAt = now();
    const row = {
      projectId: projId,
      description: input.description ?? null,
      coverArtifactId: input.coverArtifactId ?? null,
      version: 1,
      capabilityProfileVersion: 0,
      createdAt,
      updatedAt: createdAt,
    };

    try {
      const inserted = await this.db.insert(projectProfiles).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("profile insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }
}

/**
 * M-015 ProjectCapabilityProfile repository.
 *
 * The version is stored durably in project_profiles.capability_profile_version.
 * Uses SELECT FOR UPDATE for genuine concurrent CAS semantics.
 */
export class ProjectCapabilityRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  public async getCapabilitiesByProjectId(projectId: string): Promise<ProjectCapabilityRow[]> {
    const id = requireId("projectId", projectId);
    return this.db
      .select()
      .from(projectCapabilities)
      .where(eq(projectCapabilities.projectId, id))
      .orderBy(projectCapabilities.capabilityKey);
  }

  public async getVersionByProjectId(projectId: string): Promise<number> {
    const id = requireId("projectId", projectId);
    const rows = await this.db
      .select({ version: projectProfiles.capabilityProfileVersion })
      .from(projectProfiles)
      .where(eq(projectProfiles.projectId, id));
    const row = rows[0];
    return row?.version ?? 0;
  }

  public async replaceCapabilities(input: {
    projectId: string;
    expectedVersion: number;
    capabilities: readonly string[];
  }): Promise<ProjectCapabilityRow[]> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const projId = requireId("projectId", input.projectId);

    for (const key of input.capabilities) {
      requireCapabilityKey(key);
    }

    return this.db.transaction(async (tx) => {
      // Transaction-safe creation/locking pattern:
      // 1. INSERT ON CONFLICT DO NOTHING — never aborts the transaction
      // 2. SELECT ... FOR UPDATE — acquires row lock, returns profile
      // 3. Validate capability_profile_version against expectedVersion

      const n2 = now();
      await tx.execute(
        sql`INSERT INTO project_profiles (project_id, version, capability_profile_version, created_at, updated_at)
            VALUES (${projId}, 0, 0, ${n2}, ${n2})
            ON CONFLICT (project_id) DO NOTHING`
      );

      const lockResult = await tx.execute(
        sql`SELECT project_id, description, cover_artifact_id, version, capability_profile_version
            FROM project_profiles
            WHERE project_id = ${projId}
            FOR UPDATE`
      );

      type LockRow = {
        project_id: string;
        description: string | null;
        cover_artifact_id: string | null;
        version: number;
        capability_profile_version: number;
      };
      const rows = (lockResult.rows as LockRow[] | undefined) ?? [];
      const profile = rows[0];
      if (!profile) {
        throw new PersistenceError("project_profiles row not found after insert/update");
      }

      if (profile.capability_profile_version !== input.expectedVersion) {
        throw new StaleVersionError(
          "capability version conflict: expected " + input.expectedVersion + ", current " + profile.capability_profile_version,
        );
      }

      const newVersion = profile.capability_profile_version + 1;

      await tx.delete(projectCapabilities).where(eq(projectCapabilities.projectId, projId));

      // Update ONLY capabilityProfileVersion — NOT profile.version or updatedAt
      // (those belong to the independent ProjectProfile optimistic-concurrency domain)
      await tx.update(projectProfiles)
        .set({ capabilityProfileVersion: newVersion })
        .where(eq(projectProfiles.projectId, projId));

      if (input.capabilities.length === 0) {
        return [];
      }

      const uniqueSorted = [...new Set(input.capabilities)].sort();
      const resultRows = await tx.insert(projectCapabilities)
        .values(
          uniqueSorted.map((key) => ({
            id: newId(),
            projectId: projId,
            capabilityKey: key,
            version: newVersion,
            createdAt: n2,
          })),
        )
        .returning();

      return resultRows.sort((a, b) => a.capabilityKey.localeCompare(b.capabilityKey));
    });
  }
}
