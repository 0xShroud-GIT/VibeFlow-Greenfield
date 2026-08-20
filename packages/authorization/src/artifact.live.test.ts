import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  ArtifactRepository,
  createControlPlanePool,
  defaultMigrationsDirectory,
  ProjectRepository,
  TenantRepository,
  type AccountRow,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
} from "@vibeflow/persistence";

import { TenantAuthorizationService } from "./service.js";
import { ALLOW, deny } from "./types.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-013 PostgreSQL Artifact authorization requires DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-013 PostgreSQL Artifact/ArtifactRelation authorization integration", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;
  let authz: TenantAuthorizationService;

  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let projectA: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);

    const combined = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projects.getProjectById.bind(projects),
      getArtifactById: artifacts.getArtifactById.bind(artifacts),
      getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
    };

    authz = new TenantAuthorizationService(combined, {
      async recordAuthorizationDecision() {},
    });

    alice = await tenants.createAccount({ displayName: "Artifact Auth Alice" });
    bob = await tenants.createAccount({ displayName: "Artifact Auth Bob" });
    orgA = await tenants.createOrganization({ name: "Artifact Auth Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Artifact Auth Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });
    projectA = await projects.createProject({ organizationId: orgA.id, name: "Artifact Auth Project A" });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("same-tenant Artifact read succeeds", async () => {
    const artifact = await artifacts.createArtifact({ projectId: projectA.id, type: "website" });
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact", id: artifact.id },
      }),
    ).resolves.toEqual(ALLOW);
  });

  it("cross-tenant Artifact read fails closed (no_membership)", async () => {
    const artifact = await artifacts.createArtifact({ projectId: projectA.id, type: "website" });
    await expect(
      authz.authorize({
        accountId: bob.id,
        action: "read",
        resource: { type: "artifact", id: artifact.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("forged actor/Account identity fails closed", async () => {
    const artifact = await artifacts.createArtifact({ projectId: projectA.id, type: "slides" });
    await expect(
      authz.authorize({
        accountId: randomUUID(),
        action: "read",
        resource: { type: "artifact", id: artifact.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("unknown/random Artifact UUID fails closed (unknown_resource)", async () => {
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact", id: randomUUID() },
      }),
    ).resolves.toEqual(deny("unknown_resource"));
  });

  it("revoked membership fails closed for Artifact", async () => {
    const artifact = await artifacts.createArtifact({ projectId: projectA.id, type: "report" });
    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [orgA.id, alice.id],
    );
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact", id: artifact.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
  });

  it("Artifact authorization derives tenant from canonical persistence, not client claim", async () => {
    const artifact = await artifacts.createArtifact({ projectId: projectA.id, type: "data" });
    // The authorization boundary only receives an artifact id; the client
    // cannot inject an organization/project claim. Cross-tenant id still fails.
    await expect(
      authz.authorize({
        accountId: bob.id,
        action: "read",
        resource: { type: "artifact", id: artifact.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("same-tenant ArtifactRelation read succeeds", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "design" });
    const object = await artifacts.createArtifact({ projectId: projectA.id, type: "app" });
    const relation = await artifacts.createArtifactRelation({
      subjectArtifactId: subject.id,
      objectArtifactId: object.id,
      relationKind: "derived-from",
    });
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact_relation", id: relation.id },
      }),
    ).resolves.toEqual(ALLOW);
  });

  it("cross-tenant ArtifactRelation read fails closed", async () => {
    const subject = await artifacts.createArtifact({ projectId: projectA.id, type: "design" });
    const object = await artifacts.createArtifact({ projectId: projectA.id, type: "app" });
    const relation = await artifacts.createArtifactRelation({
      subjectArtifactId: subject.id,
      objectArtifactId: object.id,
      relationKind: "variant",
    });
    await expect(
      authz.authorize({
        accountId: bob.id,
        action: "read",
        resource: { type: "artifact_relation", id: relation.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("unknown ArtifactRelation UUID fails closed", async () => {
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact_relation", id: randomUUID() },
      }),
    ).resolves.toEqual(deny("unknown_resource"));
  });
});
