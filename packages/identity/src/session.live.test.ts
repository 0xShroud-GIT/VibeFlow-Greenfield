import { randomUUID } from "node:crypto";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  createControlPlanePool,
  defaultMigrationsDirectory,
  type ControlPlanePool,
} from "@vibeflow/persistence";

import { cookieRequestHeader } from "./cookies.js";
import {
  AuthenticationRejectedError,
  UntrustedIdentityOriginError,
} from "./errors.js";
import { IdentityService } from "./service.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];
const baseURL = "https://identity.vibeflow.test";
const testSecret = `m009-test-${"x".repeat(48)}`;

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-009 PostgreSQL integration requires DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

function uniqueEmail(label: string): string {
  return `${label}-${randomUUID()}@identity.vibeflow.test`;
}

function password(): string {
  return "correct-horse-battery-staple";
}

describePostgres("M-009 Better Auth PostgreSQL session lifecycle", () => {
  let controlPlane: ControlPlanePool;
  let identity: IdentityService;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    identity = new IdentityService({
      controlPlane,
      baseURL,
      secret: testSecret,
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("creates a canonical Account link and emits secure HttpOnly session cookies", async () => {
    const forgedAccountId = randomUUID();
    const registration = await identity.registerEmailPassword({
      displayName: "Session Owner",
      email: uniqueEmail("register"),
      password: password(),
      origin: baseURL,
      // Runtime callers cannot establish an Account link through extra client fields.
      vibeflowAccountId: forgedAccountId,
    } as never);

    expect(registration.accountId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(registration.accountId).not.toBe(forgedAccountId);
    expect(registration.setCookie.length).toBeGreaterThan(0);
    const allCookieAttributes = registration.setCookie.join("\n");
    expect(allCookieAttributes).toMatch(/HttpOnly/i);
    expect(allCookieAttributes).toMatch(/Secure/i);
    expect(allCookieAttributes).toMatch(/SameSite=Lax/i);

    const canonicalLink = await controlPlane.pool.query<{ vibeflow_account_id: string }>(
      "SELECT vibeflow_account_id FROM identity_users WHERE vibeflow_account_id = $1",
      [registration.accountId],
    );
    expect(canonicalLink.rows).toEqual([{ vibeflow_account_id: registration.accountId }]);

    const session = await identity.validateSession({
      origin: baseURL,
      cookieHeader: cookieRequestHeader(registration.setCookie),
    });
    expect(session).toMatchObject({
      authenticated: true,
      accountId: registration.accountId,
    });
  });

  it("rejects credentials from an untrusted origin before session creation", async () => {
    await expect(
      identity.signInEmailPassword({
        email: uniqueEmail("untrusted"),
        password: password(),
        origin: "https://attacker.invalid",
      }),
    ).rejects.toBeInstanceOf(UntrustedIdentityOriginError);
  });

  it("rejects invalid credentials without exposing a session", async () => {
    await expect(
      identity.signInEmailPassword({
        email: uniqueEmail("missing"),
        password: password(),
        origin: baseURL,
      }),
    ).rejects.toBeInstanceOf(AuthenticationRejectedError);
  });

  it("revokes logout sessions and rejects replay of the prior cookie", async () => {
    const registration = await identity.registerEmailPassword({
      displayName: "Logout Owner",
      email: uniqueEmail("logout"),
      password: password(),
      origin: baseURL,
    });
    const cookieHeader = cookieRequestHeader(registration.setCookie);

    await expect(identity.validateSession({ origin: baseURL, cookieHeader })).resolves.toMatchObject({
      authenticated: true,
      accountId: registration.accountId,
    });
    const expiredCookies = await identity.logout({ origin: baseURL, cookieHeader });
    expect(expiredCookies.join("\n")).toMatch(/Max-Age=0|Expires=/i);
    await expect(identity.validateSession({ origin: baseURL, cookieHeader })).resolves.toEqual({
      authenticated: false,
    });
  });

  it("fails closed for an expired/stale persisted session", async () => {
    const registration = await identity.registerEmailPassword({
      displayName: "Stale Session Owner",
      email: uniqueEmail("stale"),
      password: password(),
      origin: baseURL,
    });
    const cookieHeader = cookieRequestHeader(registration.setCookie);

    await controlPlane.pool.query(
      `
        UPDATE identity_sessions
        SET expires_at = now() - interval '1 second'
        WHERE user_id = (
          SELECT id FROM identity_users WHERE vibeflow_account_id = $1
        )
      `,
      [registration.accountId],
    );

    await expect(identity.validateSession({ origin: baseURL, cookieHeader })).resolves.toEqual({
      authenticated: false,
    });
  });

  it("returns identity proof only and does not project tenant/resource authority", async () => {
    const registration = await identity.registerEmailPassword({
      displayName: "Identity Only",
      email: uniqueEmail("identity-only"),
      password: password(),
      origin: baseURL,
    });
    const session = await identity.validateSession({
      origin: baseURL,
      cookieHeader: cookieRequestHeader(registration.setCookie),
    });

    expect(session).toMatchObject({ authenticated: true, accountId: registration.accountId });
    expect(session).not.toHaveProperty("organizationId");
    expect(session).not.toHaveProperty("projectId");
    expect(session).not.toHaveProperty("role");
    expect(session).not.toHaveProperty("permissions");
  });
});
