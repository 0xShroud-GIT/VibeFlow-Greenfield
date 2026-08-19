import { pgTable, text, timestamp, unique, uuid } from "drizzle-orm/pg-core";

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

export type AccountRow = typeof accounts.$inferSelect;
export type OrganizationRow = typeof organizations.$inferSelect;
export type OrganizationMembershipRow = typeof organizationMemberships.$inferSelect;

export const TENANT_TABLES = {
  accounts,
  organizations,
  organizationMemberships,
} as const;
