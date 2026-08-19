import { randomUUID } from "node:crypto";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { createControlPlanePool, type ControlPlanePool } from "./client.js";
import {
  DuplicateMembershipError,
  ForeignKeyViolationError,
  NotFoundError,
  PersistenceInputError,
  ProviderAuthorityRejectedError,
} from "./errors.js";
import { applyCommittedSqlMigrations, defaultMigrationsDirectory } from "./migrate.js";
import { TenantRepository } from "./repositories.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

describe.skipIf(!connectionString)("M-008 live PostgreSQL persistence", () => {
  let pool: ControlPlanePool;
  let tenants: TenantRepository;

  beforeAll(async () => {
    pool = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(pool.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(pool.db);
  });

  afterAll(async () => {
    await pool.close();
  });

  it("creates and reads a durable account", async () => {
    const created = await tenants.createAccount({ displayName: "Ada Lovelace" });
    const read = await tenants.getAccountById(created.id);
    expect(read.id).toBe(created.id);
    expect(read.displayName).toBe("Ada Lovelace");
    expect(read.createdAt).toBeInstanceOf(Date);
  });

  it("creates and reads a durable organization, including personal orgs", async () => {
    const standard = await tenants.createOrganization({ name: "VibeFlow Labs", kind: "standard" });
    const personal = await tenants.createOrganization({ name: "Ada", kind: "personal" });
    expect((await tenants.getOrganizationById(standard.id)).name).toBe("VibeFlow Labs");
    expect((await tenants.getOrganizationById(personal.id)).kind).toBe("personal");
  });

  it("persists membership as a relation and rejects duplicates", async () => {
    const account = await tenants.createAccount({ displayName: "Member" });
    const organization = await tenants.createOrganization({ name: "Tenant", kind: "standard" });
    const membership = await tenants.addMembership({
      organizationId: organization.id,
      accountId: account.id,
    });
    const read = await tenants.getMembership({
      organizationId: organization.id,
      accountId: account.id,
    });
    expect(read.id).toBe(membership.id);
    await expect(
      tenants.addMembership({
        organizationId: organization.id,
        accountId: account.id,
      }),
    ).rejects.toBeInstanceOf(DuplicateMembershipError);
  });

  it("enforces foreign keys for unknown account or organization ids", async () => {
    const account = await tenants.createAccount({ displayName: "FK Account" });
    const organization = await tenants.createOrganization({ name: "FK Org", kind: "standard" });
    await expect(
      tenants.addMembership({
        organizationId: organization.id,
        accountId: randomUUID(),
      }),
    ).rejects.toBeInstanceOf(ForeignKeyViolationError);
    await expect(
      tenants.addMembership({
        organizationId: randomUUID(),
        accountId: account.id,
      }),
    ).rejects.toBeInstanceOf(ForeignKeyViolationError);
  });

  it("separates membership rows across organizations at the persistence boundary", async () => {
    const alice = await tenants.createAccount({ displayName: "Alice" });
    const bob = await tenants.createAccount({ displayName: "Bob" });
    const orgA = await tenants.createOrganization({ name: "Org A", kind: "standard" });
    const orgB = await tenants.createOrganization({ name: "Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });

    const aMembers = await tenants.listMembershipsForOrganization(orgA.id);
    const bMembers = await tenants.listMembershipsForOrganization(orgB.id);
    expect(aMembers.map((row) => row.accountId)).toEqual([alice.id]);
    expect(bMembers.map((row) => row.accountId)).toEqual([bob.id]);
    expect(aMembers.some((row) => row.accountId === bob.id)).toBe(false);

    const aliceOrgs = await tenants.listOrganizationsForAccount(alice.id);
    expect(aliceOrgs.map((row) => row.id)).toEqual([orgA.id]);
  });

  it("rejects provider/client IDs and unscoped identifiers", async () => {
    await expect(
      tenants.createAccount({ displayName: "Nope", providerId: "prov_1" } as never),
    ).rejects.toBeInstanceOf(ProviderAuthorityRejectedError);
    await expect(tenants.listMembershipsForOrganization("client-org")).rejects.toBeInstanceOf(
      PersistenceInputError,
    );
    await expect(tenants.getAccountById(randomUUID())).rejects.toBeInstanceOf(NotFoundError);
  });

  it("creates a personal organization membership in one transaction", async () => {
    const account = await tenants.createAccount({ displayName: "Solo" });
    const result = await tenants.createPersonalOrganizationForAccount(account.id, "Solo");
    expect(result.organization.kind).toBe("personal");
    expect(result.membership.accountId).toBe(account.id);
    expect(result.membership.organizationId).toBe(result.organization.id);
  });

  it("applies committed SQL migrations idempotently", async () => {
    const first = await applyCommittedSqlMigrations(pool.pool, defaultMigrationsDirectory());
    const second = await applyCommittedSqlMigrations(pool.pool, defaultMigrationsDirectory());
    expect(first.applied.length + first.skipped.length).toBeGreaterThan(0);
    expect(second.applied).toEqual([]);
    expect(second.skipped).toContain("0001_account_organization.sql");
  });
});
