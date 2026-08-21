import { eq, sql } from "drizzle-orm";

import type { ControlPlaneDatabase } from "./client.js";
import { NotFoundError } from "./errors.js";
import { requireId } from "./ids.js";
import {
  artifactRelations,
  artifacts,
  projectArchiveImports,
  projectCapabilities,
  projectClonePlans,
  projectProfiles,
  projects,
  type ArtifactRelationRow,
  type ArtifactRow,
  type ProjectArchiveImportRow,
  type ProjectCapabilityRow,
  type ProjectClonePlanRow,
  type ProjectProfileRow,
  type ProjectRow,
} from "./schema.js";

interface CapabilityProfileVersionRow {
  version: number;
}

/**
 * One point-in-time Project-domain read snapshot for M-015 Project Overview.
 * This is a projection/read model, not a canonical resource or new authority
 * root. Canonical ownership remains Project -> Organization.
 */
export interface ProjectOverviewSnapshot {
  readonly project: ProjectRow;
  readonly profile: ProjectProfileRow | undefined;
  readonly capabilityProfileVersion: number;
  readonly capabilities: readonly ProjectCapabilityRow[];
  readonly artifacts: readonly ArtifactRow[];
  readonly artifactRelations: readonly ArtifactRelationRow[];
  readonly importProvenance: ProjectArchiveImportRow | undefined;
  readonly cloneProvenance: ProjectClonePlanRow | undefined;
}

/**
 * Persistence-side M-015 overview projection.
 *
 * PostgreSQL READ COMMITTED would take a fresh snapshot for each SELECT. This
 * repository explicitly upgrades the transaction before its first read so all
 * Project/Profile/Capability/Artifact/provenance components describe one
 * database snapshot.
 */
export class ProjectOverviewRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  public async getSnapshot(projectId: string): Promise<ProjectOverviewSnapshot> {
    const id = requireId("projectId", projectId);

    return this.db.transaction(async (tx) => {
      await tx.execute(sql`SET TRANSACTION ISOLATION LEVEL REPEATABLE READ`);

      const projectRows = await tx.select().from(projects).where(eq(projects.id, id));
      const project = projectRows[0];
      if (!project) {
        throw new NotFoundError(`project not found: ${id}`);
      }

      const profileRows = await tx
        .select()
        .from(projectProfiles)
        .where(eq(projectProfiles.projectId, id));

      const capabilityVersionResult = await tx.execute(
        sql`SELECT version FROM project_capability_profiles WHERE project_id = ${id}`,
      );
      const capabilityVersionRows =
        (capabilityVersionResult.rows as CapabilityProfileVersionRow[] | undefined) ?? [];

      const capabilityRows = await tx
        .select()
        .from(projectCapabilities)
        .where(eq(projectCapabilities.projectId, id))
        .orderBy(projectCapabilities.capabilityKey);

      const artifactRows = await tx
        .select()
        .from(artifacts)
        .where(eq(artifacts.projectId, id));

      const relationRows = await tx
        .select()
        .from(artifactRelations)
        .where(eq(artifactRelations.projectId, id));

      const importRows = await tx
        .select()
        .from(projectArchiveImports)
        .where(eq(projectArchiveImports.projectId, id));

      const cloneRows = await tx
        .select()
        .from(projectClonePlans)
        .where(eq(projectClonePlans.targetProjectId, id));

      return {
        project,
        profile: profileRows[0],
        capabilityProfileVersion: capabilityVersionRows[0]?.version ?? 0,
        capabilities: capabilityRows,
        artifacts: artifactRows,
        artifactRelations: relationRows,
        importProvenance: importRows[0],
        cloneProvenance: cloneRows[0],
      };
    });
  }
}
