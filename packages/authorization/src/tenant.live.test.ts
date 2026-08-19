import { randomUUID } from "node:crypto";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  createControlPlanePool,
  defaultMigrationsDirectory,
  type AccountRow,
  type ControlPlanePool,
  type OrganizationRow,
  TenantRepository,
} from "@vibeflow/persistence";

import { TenantAuthorizationService } from "./service.js";
import { ALLOW, deny } from "./types.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-010 PostgreSQL authorization requires DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-010 PostgreSQL tenant/resource authorization", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let authz: TenantAuthorizationService;

  let alice: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    authz = new TenantAuthorizationService(tenants, {
      async recordAuthorizationDecision() {},
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("seeds two isolated tenants and proves an allowed canonical membership", async () => {
    alice = await tenants.createAccount({ displayName: "Alice" });
    orgA = await tenants.createOrganization({ name: "Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });

    // Alice is a canonical member of Org A: read is allowed.
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: orgA.id },
      }),
    ).resolves.toEqual(ALLOW);
  });

  it("denies an account with no membership anywhere (P0 negative)", async () => {
    const stranger = await tenants.createAccount({ displayName: "Stranger" });
    await expect(
      authz.authorize({
        accountId: stranger.id,
        action: "read",
        resource: { type: "organization", id: orgA.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("denies cross-tenant access: member of Org A cannot read Org B (IDOR read)", async () => {
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: orgB.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("denies cross-tenant mutations: member of Org A cannot create/update/delete in Org B", async () => {
    for (const action of ["create", "update", "delete"] as const) {
      await expect(
        authz.authorize({
          accountId: alice.id,
          action,
          resource: { type: "organization", id: orgB.id },
        }),
      ).resolves.toEqual(deny("no_membership"));
    }
  });

  it("denies a forged/swapped organization id that is not a real organization", async () => {
    const forged = randomUUID();
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: forged },
      }),
    ).resolves.toEqual(deny("unknown_resource"));
  });

  it("denies a swapped id that is a real organization the account is not a member of", async () => {
    // Org B exists but Alice is not a member: deny, never reveal membership.
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: orgB.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("denies deleted/stale membership (P0 negative)", async () => {
    await tenants.addMembership({ organizationId: orgB.id, accountId: alice.id });
    // Membership exists first: allowed.
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: orgB.id },
      }),
    ).resolves.toEqual(ALLOW);

    // Canonical membership row is deleted (revoked/stale): must fail closed.
    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [orgB.id, alice.id],
    );
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: orgB.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("denies malformed and unknown resource/action inputs (P0 negative)", async () => {
    // Unknown resource type: use a genuinely unknown/future type, not \"project\"
    // which is now a canonical supported type since M-012.
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact", id: orgA.id },
      }),
    ).resolves.toEqual(deny("unknown_resource_type"));

    // Unknown action.
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "transferOwnership",
        resource: { type: "organization", id: orgA.id },
      }),
    ).resolves.toEqual(deny("unknown_action"));

    // Malformed / non-canonical identifiers.
    await expect(
      authz.authorize({
        accountId: "client-id",
        action: "read",
        resource: { type: "organization", id: orgA.id },
      }),
    ).resolves.toEqual(deny("invalid_identifier"));
    await expect(
      authz.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "organization", id: "org-slug" },
      }),
    ).resolves.toEqual(deny("invalid_identifier"));
  });

  it("denies an authenticated account acting on a tenant it is not a member of (IDOR mutation)", async () => {
    const carol = await tenants.createAccount({ displayName: "Carol" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: carol.id });

    // Carol is a member of Org A only; Org B is a different tenant.
    await expect(
      authz.authorize({
        accountId: carol.id,
        action: "delete",
        resource: { type: "organization", id: orgB.id },
      }),
    ).resolves.toEqual(deny("no_membership"));
  });
});
