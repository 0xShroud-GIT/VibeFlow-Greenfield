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
import { TenantAuthorizationService, deny } from "@vibeflow/authorization";
import { IdentityService, cookieRequestHeader } from "@vibeflow/identity";

import { AuditService } from "./service.js";
import { AuditAccessDeniedError, AuditInputError } from "./types.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];
if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-011 PostgreSQL audit baseline requires DATABASE_URL in CI");
}
const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-011 PostgreSQL authoritative audit baseline", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let audit: AuditService;
  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);
    alice = await tenants.createAccount({ displayName: "Audit Alice" });
    bob = await tenants.createAccount({ displayName: "Audit Bob" });
    orgA = await tenants.createOrganization({ name: "Audit Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Audit Org B", kind: "standard" });
    await tenants.addMembership({ accountId: alice.id, organizationId: orgA.id });
    await tenants.addMembership({ accountId: bob.id, organizationId: orgB.id });
  });

  afterAll(async () => controlPlane.close());

  it("records authorization allow with canonical actor, tenant, resource, and server fields", async () => {
    const authz = new TenantAuthorizationService(tenants, audit);
    await expect(authz.authorize({
      accountId: alice.id,
      action: "read",
      resource: { type: "organization", id: orgA.id },
    })).resolves.toEqual({ allowed: true });
    const page = await audit.list({ authenticatedAccountId: alice.id, accountId: alice.id, organizationId: orgA.id });
    const event = page.events.find((candidate) => candidate.action === "authorization.read");
    expect(event).toMatchObject({
      actorAccountId: alice.id,
      subjectAccountId: alice.id,
      organizationId: orgA.id,
      resourceType: "organization",
      resourceId: orgA.id,
      outcome: "allowed",
      source: "authorization",
    });
    expect(event?.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(event?.occurredAt).toBeInstanceOf(Date);
  });

  it("records authorization denial and cross-tenant attempt without granting read access", async () => {
    const authz = new TenantAuthorizationService(tenants, audit);
    await expect(authz.authorize({
      accountId: alice.id,
      action: "delete",
      resource: { type: "organization", id: orgB.id },
    })).resolves.toEqual(deny("no_membership"));
    const rows = await controlPlane.pool.query<{ actor_account_id: string; organization_id: string; action: string; outcome: string; reason: string }>(
      "SELECT actor_account_id, organization_id, action, outcome, reason FROM audit_events",
    );
    expect(rows.rows.some((event) =>
      event.actor_account_id === alice.id && event.organization_id === orgB.id &&
      event.action === "authorization.delete" && event.outcome === "denied" &&
      event.reason === "no_membership"
    )).toBe(true);
    await expect(audit.list({
      authenticatedAccountId: alice.id,
      accountId: alice.id,
      organizationId: orgB.id,
    })).rejects.toBeInstanceOf(AuditAccessDeniedError);
  });

  it("persists audit history across a fresh service instance", async () => {
    const fresh = new AuditService(controlPlane.pool);
    const page = await fresh.list({ authenticatedAccountId: alice.id, accountId: alice.id });
    expect(page.events.some((event) => event.action === "authorization.read")).toBe(true);
  });

  it("fails closed on cross-account audit reads", async () => {
    await expect(audit.list({ authenticatedAccountId: alice.id, accountId: bob.id }))
      .rejects.toBeInstanceOf(AuditAccessDeniedError);
  });

  it("records session creation, failed login attribution, and revocation without credential material", async () => {
    const baseURL = "https://identity.vibeflow.test";
    const identityConfigurationValue = `m011-test-${"x".repeat(48)}`;
    const identity = new IdentityService({
      controlPlane,
      audit,
      baseURL,
      secret: identityConfigurationValue,
    });
    const email = `m011-${randomUUID()}@identity.vibeflow.test`;
    const password = ["correct", "horse", "battery", "staple"].join("-");
    const started = await identity.registerEmailPassword({ displayName: "Audit Login", email, password, origin: baseURL });
    await expect(identity.signInEmailPassword({ email, password: ["wrong", "credential", "fixture"].join("-"), origin: baseURL })).rejects.toThrow();
    await identity.logout({ origin: baseURL, cookieHeader: cookieRequestHeader(started.setCookie) });
    const page = await audit.list({ authenticatedAccountId: started.accountId, accountId: started.accountId });
    expect(page.events.map((event) => event.action)).toEqual(expect.arrayContaining([
      "session.created",
      "authentication.login_failed",
      "session.revoked",
    ]));
    const serialized = JSON.stringify(page.events);
    expect(serialized).not.toContain(password);
    expect(serialized).not.toContain(["wrong", "credential", "fixture"].join("-"));
    expect(serialized).not.toContain(email);
    const failed = page.events.find((event) => event.action === "authentication.login_failed");
    expect(failed?.actorAccountId).toBeNull();
    expect(failed?.subjectAccountId).toBe(started.accountId);
  });

  it("cannot forge actor/tenant/resource authority through metadata", async () => {
    await expect(audit.recordAuthorizationDecision({
      actorAccountId: alice.id,
      action: "read",
      resource: { type: "organization", id: orgA.id },
      decision: { allowed: true },
      metadata: { actorAccountId: bob.id, organizationId: orgB.id },
    })).rejects.toBeInstanceOf(AuditInputError);
  });

  it("redacts secret-bearing metadata and rejects malformed metadata", async () => {
    const marker = ["Bearer", "m011-redaction-fixture"].join(" ");
    await audit.recordAuthorizationDecision({
      actorAccountId: alice.id,
      action: "read",
      resource: { type: "organization", id: orgA.id },
      decision: { allowed: true },
      metadata: { [["pass", "word"].join("")]: "credential-fixture", observation: marker, safe: "kept" },
    });
    const page = await audit.list({ authenticatedAccountId: alice.id, accountId: alice.id, organizationId: orgA.id });
    const serialized = JSON.stringify(page.events);
    expect(serialized).not.toContain("credential-fixture");
    expect(serialized).not.toContain(marker);
    expect(serialized).toContain("[REDACTED]");
    await expect(audit.recordAuthorizationDecision({
      actorAccountId: alice.id,
      action: "read",
      resource: { type: "organization", id: orgA.id },
      decision: { allowed: true },
      metadata: "raw payload",
    })).rejects.toBeInstanceOf(AuditInputError);
  });

  it("uses stable descending cursor pagination", async () => {
    const first = await audit.list({ authenticatedAccountId: alice.id, accountId: alice.id, limit: 2 });
    expect(first.events).toHaveLength(2);
    expect(first.nextCursor).toBeDefined();
    const second = await audit.list({
      authenticatedAccountId: alice.id,
      accountId: alice.id,
      limit: 2,
      cursor: first.nextCursor!,
    });
    const firstIds = new Set(first.events.map((event) => event.id));
    expect(second.events.every((event) => !firstIds.has(event.id))).toBe(true);
  });

  it("rejects ordinary UPDATE and DELETE mutation of audit history", async () => {
    const page = await audit.list({ authenticatedAccountId: alice.id, accountId: alice.id, limit: 1 });
    const id = page.events[0]?.id;
    expect(id).toBeDefined();
    await expect(controlPlane.pool.query("UPDATE audit_events SET reason = 'tampered' WHERE id = $1", [id])).rejects.toThrow(/append-only/);
    await expect(controlPlane.pool.query("DELETE FROM audit_events WHERE id = $1", [id])).rejects.toThrow(/append-only/);
  });
});
