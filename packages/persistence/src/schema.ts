import { boolean, jsonb, pgTable, text, timestamp, unique, uuid } from "drizzle-orm/pg-core";

/**
 * Minimal durable Account / Organization / membership schema.
 *
 * Account is VibeFlow product identity, not a provider account.
 * Organization is the tenant boundary, including the personal-org case.
 * Membership is a relation only; it does not encode authorization roles.
 */

export const ORGANIZATION_KINDS = ["personal", "standard"] as const;
export type OrganizationKind = (typeof ORGANIZATION_KINDS)[number];

export const accounts = pgTable("accounts", {
  id: uuid("id").primaryKey(),
  displayName: text("display_name").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true, mode: "date" }).notNull(),
});

export const organizations = pgTable("organizations", {
  id: uuid("id").primaryKey(),
  name: text("name").notNull(),
  kind: text("kind").$type<OrganizationKind>().notNull(),
  createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true, mode: "date" }).notNull(),
});

export const organizationMemberships = pgTable(
  "organization_memberships",
  {
    id: uuid("id").primaryKey(),
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id),
    accountId: uuid("account_id")
      .notNull()
      .references(() => accounts.id),
    createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  },
  (table) => ({
    organizationAccountUnique: unique("organization_memberships_org_account_uidx").on(
      table.organizationId,
      table.accountId,
    ),
  }),
);

/**
 * Better Auth's library-owned user record. Its `vibeflowAccountId` is the
 * canonical server-side link to VibeFlow's product Account; it is not a
 * provider, tenant, project, or authorization identifier.
 */
export const identityUsers = pgTable("identity_users", {
  id: uuid("id").primaryKey(),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  emailVerified: boolean("email_verified").notNull(),
  image: text("image"),
  createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true, mode: "date" }).notNull(),
  vibeflowAccountId: uuid("vibeflow_account_id")
    .notNull()
    .unique()
    .references(() => accounts.id),
});

export const auditEvents = pgTable("audit_events", {
  id: uuid("id").primaryKey(),
  occurredAt: timestamp("occurred_at", { withTimezone: true, mode: "date" }).notNull(),
  actorAccountId: uuid("actor_account_id").references(() => accounts.id),
  subjectAccountId: uuid("subject_account_id")
    .notNull()
    .references(() => accounts.id),
  organizationId: uuid("organization_id").references(() => organizations.id),
  action: text("action").notNull(),
  resourceType: text("resource_type").notNull(),
  resourceId: uuid("resource_id"),
  outcome: text("outcome").notNull(),
  reason: text("reason"),
  requestId: uuid("request_id"),
  source: text("source").notNull(),
  metadata: jsonb("metadata").$type<Record<string, unknown>>().notNull(),
});

/**
 * M-012 authoritative Project resource.
 * VibeFlow-owned stable container with canonical Organization ownership.
 * Server-generated id, server-controlled timestamps, FK integrity, and
 * tenant indexes. No provider/external identifier ever establishes authority.
 */
export const projects = pgTable("projects", {
  id: uuid("id").primaryKey(),
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  name: text("name").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true, mode: "date" }).notNull(),
});

export type AccountRow = typeof accounts.$inferSelect;
export type OrganizationRow = typeof organizations.$inferSelect;
export type OrganizationMembershipRow = typeof organizationMemberships.$inferSelect;
export type IdentityUserRow = typeof identityUsers.$inferSelect;
export type AuditEventRow = typeof auditEvents.$inferSelect;
export type ProjectRow = typeof projects.$inferSelect;

/** M-008 tenant authority only; keep library session/auth tables out of it. */
export const TENANT_TABLES = {
  accounts,
  organizations,
  organizationMemberships,
} as const;

/** All Drizzle tables queried by VibeFlow control-plane modules through M-012. */
export const CONTROL_PLANE_TABLES = {
  ...TENANT_TABLES,
  identityUsers,
  auditEvents,
  projects,
} as const;
