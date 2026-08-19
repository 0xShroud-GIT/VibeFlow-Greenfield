import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  createControlPlanePool,
  defaultMigrationsDirectory,
  type AccountRow,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
  ProjectRepository,
  TenantRepository,
} from "./index.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-012 PostgreSQL Project authority requires DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-012 PostgreSQL Project persistence", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;

  let alice: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);

    alice = await tenants.createAccount({ displayName: "Project Alice" });
    orgA = await tenants.createOrganization({ name: "Project Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Project Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: alice.id });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("creates a canonical Project with server-generated id and canonical Organization ownership", async () => {
    const project = await projects.createProject({
      organizationId: orgA.id,
      name: "Alpha Project",
    });

    expect(project.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(project.organizationId).toBe(orgA.id);
    expect(project.name).toBe("Alpha Project");
    expect(project.createdAt).toBeInstanceOf(Date);
    expect(project.updatedAt).toBeInstanceOf(Date);
    // Server-controlled timestamps: createdAt === updatedAt on creation
    expect(project.createdAt.getTime()).toBe(project.updatedAt.getTime());
  });

  it("proves canonical Organization ownership is persisted and retrievable", async () => {
    const created = await projects.createProject({
      organizationId: orgA.id,
      name: "Ownership Probe",
    });
    const fetched = await projects.getProjectById(created.id);
    expect(fetched.organizationId).toBe(orgA.id);
    expect(fetched.id).toBe(created.id);
  });

  it("enforces FK integrity: forged organization id fails", async () => {
    const forgedOrg = randomUUID();
    await expect(
      projects.createProject({ organizationId: forgedOrg, name: "Bad Org" }),
    ).rejects.toThrow();
  });

  it("enforces tenant-safe list: listing is scoped to canonical organization", async () => {
    const projA1 = await projects.createProject({ organizationId: orgA.id, name: "A1" });
    const projA2 = await projects.createProject({ organizationId: orgA.id, name: "A2" });
    const projB1 = await projects.createProject({ organizationId: orgB.id, name: "B1" });

    const listA = await projects.listProjectsForOrganization(orgA.id);
    const listB = await projects.listProjectsForOrganization(orgB.id);

    const idsA = new Set(listA.map((p) => p.id));
    const idsB = new Set(listB.map((p) => p.id));

    expect(idsA.has(projA1.id)).toBe(true);
    expect(idsA.has(projA2.id)).toBe(true);
    expect(idsA.has(projB1.id)).toBe(false);

    expect(idsB.has(projB1.id)).toBe(true);
    expect(idsB.has(projA1.id)).toBe(false);
  });

  it("fails closed on random/unknown Project UUID", async () => {
    const random = randomUUID();
    await expect(projects.getProjectById(random)).rejects.toThrow();
  });

  it("supports tenant-safe mutation via update with server-controlled updated_at", async () => {
    const project = await projects.createProject({ organizationId: orgA.id, name: "Mutable" });
    const before = project.updatedAt.getTime();
    // Small delay to ensure timestamp changes
    await new Promise((r) => setTimeout(r, 10));
    const updated = await projects.updateProject({ id: project.id, name: "Mutable Renamed" });
    expect(updated.name).toBe("Mutable Renamed");
    expect(updated.id).toBe(project.id);
    expect(updated.organizationId).toBe(orgA.id);
    expect(updated.updatedAt.getTime()).toBeGreaterThanOrEqual(before);
  });

  it("has required indexes for canonical tenant/project lookup", async () => {
    const indexes = await controlPlane.pool.query<{
      indexname: string;
      indexdef: string;
    }>(
      `SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'projects'`,
    );
    const defs = indexes.rows.map((r) => r.indexdef);
    expect(defs.some((d) => d.includes("organization_id"))).toBe(true);
  });

  it("rejects provider authority keys as tenant authority", async () => {
    await expect(
      // @ts-expect-error provider key injection attempt
      projects.createProject({
        organizationId: orgA.id,
        name: "Legit",
        providerId: "external-123",
      }),
    ).rejects.toThrow(/never establish tenant authority/i);
  });
});
