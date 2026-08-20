import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  ArtifactRepository,
  createControlPlanePool,
  CrossProjectArtifactRelationError,
  defaultMigrationsDirectory,
  DuplicateArtifactRelationError,
  ForeignKeyViolationError,
  NotFoundError,
  ProjectRepository,
  ProviderAuthorityRejectedError,
  TenantRepository,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
} from "./index.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-013 Artifact persistence PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-013 Artifact/ArtifactRelation persistence authority", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;

  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let projectA: ProjectRow;
  let projectB: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);

    orgA = await tenants.createOrganization({ name: "Artifact Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Artifact Org B", kind: "standard" });
    projectA = await projects.createProject({ organizationId: orgA.id, name: "Artifact Project A" });
    projectB = await projects.createProject({ organizationId: orgB.id, name: "Artifact Project B" });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("canonical Artifact creation with server-generated id, project FK, timestamps", async () => {
    const artifact = await artifacts.createArtifact({ projectId: projectA.id, type: "website" });
    expect(artifact.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(artifact.projectId).toBe(projectA.id);
    expect(artifact.type).toBe("website");
    expect(artifact.createdAt).toBeInstanceOf(Date);
    expect(artifact.updatedAt).toBeInstanceOf(Date);
    const fromDb = await artifacts.getArtifactById(artifact.id);
    expect(fromDb.projectId).toBe(projectA.id);
    expect(fromDb.type).toBe("website");
  });

  it("Artifact type is a syntax-validated opaque token; malformed values rejected", async () => {
    for (const bad of ["", "   ", "two words", "a\nb", ".leading", "trailing.", "a+b"]) {
      await expect(
        artifacts.createArtifact({ projectId: projectA.id, type: bad }),
      ).rejects.toThrow();
    }
  });

  it("tenant-safe list returns only the canonical project's artifacts", async () => {
    await artifacts.createArtifact({ projectId: projectA.id, type: "slides" });
    await artifacts.createArtifact({ projectId: projectB.id, type: "mobile" });
    const listA = await artifacts.listArtifactsForProject(projectA.id);
    expect(listA.every((a) => a.projectId === projectA.id)).toBe(true);
    expect(listA.some((a) => a.type === "mobile")).toBe(false);
  });

  it("unknown/random Artifact UUID fails closed", async () => {
    await expect(artifacts.getArtifactById(randomUUID())).rejects.toBeInstanceOf(NotFoundError);
  });

  it("provider/external identifier never establishes authority", async () => {
    await expect(
      artifacts.createArtifact({
        projectId: projectA.id,
        type: "website",
        providerId: "github-123",
      } as never),
    ).rejects.toBeInstanceOf(ProviderAuthorityRejectedError);
  });

  it("forged Project FK on Artifact creation fails (FK integrity)", async () => {
    await expect(
      artifacts.createArtifact({ projectId: randomUUID(), type: "report" }),
    ).rejects.toBeInstanceOf(ForeignKeyViolationError);
  });

  it("valid same-Project relation persists with server id and derived project", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "design" });
    const object = await artifacts.createArtifact({ projectId: projectA.id, type: "app" });
    const relation = await artifacts.createArtifactRelation({
      subjectArtifactId: subject.id,
      objectArtifactId: object.id,
      relationKind: "derived-from",
    });
    expect(relation.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(relation.projectId).toBe(projectA.id);
    expect(relation.subjectArtifactId).toBe(subject.id);
    expect(relation.objectArtifactId).toBe(object.id);
    expect(relation.relationKind).toBe("derived-from");
    const fromDb = await artifacts.getArtifactRelationById(relation.id);
    expect(fromDb.projectId).toBe(projectA.id);
  });

  it("unknown relation endpoint fails closed", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "data" });
    await expect(
      artifacts.createArtifactRelation({
        subjectArtifactId: subject.id,
        objectArtifactId: randomUUID(),
        relationKind: "contains",
      }),
    ).rejects.toBeInstanceOf(NotFoundError);
  });

  it("cross-Project relation fails even when both Projects are canonical", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "a" });
    const object = await artifacts.createArtifact({ projectId: projectB.id, type: "b" });
    await expect(
      artifacts.createArtifactRelation({
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "lineage",
      }),
    ).rejects.toBeInstanceOf(CrossProjectArtifactRelationError);
  });

  it("self-edge relation fails", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "self" });
    await expect(
      artifacts.createArtifactRelation({
        subjectArtifactId: subject.id,
        objectArtifactId: subject.id,
        relationKind: "variant",
      }),
    ).rejects.toThrow();
  });

  it("duplicate relation edge fails", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "dup-s" });
    const object = await artifacts.createArtifact({ projectId: projectA.id, type: "dup-o" });
    await artifacts.createArtifactRelation({
      subjectArtifactId: subject.id,
      objectArtifactId: object.id,
      relationKind: "variant",
    });
    await expect(
      artifacts.createArtifactRelation({
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "variant",
      }),
    ).rejects.toBeInstanceOf(DuplicateArtifactRelationError);
  });

  it("invalid relation kind fails", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "k-s" });
    const object = await artifacts.createArtifact({ projectId: projectA.id, type: "k-o" });
    await expect(
      artifacts.createArtifactRelation({
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "not-a-kind" as never,
      }),
    ).rejects.toThrow();
  });

  it("DB composite FK prevents cross-Project edge even if service checks are bypassed", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "fk-s" });
    const object = await artifacts.createArtifact({ projectId: projectB.id, type: "fk-o" });
    await expect(
      controlPlane.pool.query(
        `INSERT INTO artifact_relations
           (id, project_id, subject_artifact_id, object_artifact_id, relation_kind)
         VALUES ($1, $2, $3, $4, $5)`,
        [randomUUID(), projectA.id, subject.id, object.id, "lineage"],
      ),
    ).rejects.toMatchObject({ code: "23503" });
  });

  it("Artifact/ArtifactRelation lookup indexes exist", async () => {
    const result = await controlPlane.pool.query<{ indexname: string }>(
      `SELECT indexname FROM pg_indexes WHERE tablename IN ('artifacts', 'artifact_relations')`,
    );
    const names = result.rows.map((r) => r.indexname);
    expect(names).toContain("artifacts_project_id_idx");
    expect(names).toContain("artifacts_project_id_created_at_idx");
    expect(names).toContain("artifact_relations_project_id_idx");
    expect(names).toContain("artifact_relations_subject_idx");
    expect(names).toContain("artifact_relations_object_idx");
  });
});
