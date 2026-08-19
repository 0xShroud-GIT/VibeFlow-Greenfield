import { readFile } from "node:fs/promises";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { defaultMigrationsDirectory, listCommittedSqlMigrations } from "./migrate.js";

describe("M-008 committed SQL migrations", () => {
  it("includes the Account/Organization membership migration", async () => {
    const files = await listCommittedSqlMigrations(defaultMigrationsDirectory());
    expect(files).toContain("0001_account_organization.sql");
  });

  it("declares FKs and unique membership without provider or role columns", async () => {
    const sql = await readFile(
      path.join(defaultMigrationsDirectory(), "0001_account_organization.sql"),
      "utf8",
    );
    expect(sql).toContain("CREATE TABLE accounts");
    expect(sql).toContain("CREATE TABLE organizations");
    expect(sql).toContain("CREATE TABLE organization_memberships");
    expect(sql).toContain("REFERENCES organizations");
    expect(sql).toContain("REFERENCES accounts");
    expect(sql).toContain("UNIQUE (organization_id, account_id)");
    expect(sql).toContain("kind IN ('personal', 'standard')");
    expect(sql).not.toMatch(/provider_id/i);
    expect(sql).not.toMatch(/external_id/i);
    expect(sql).not.toMatch(/\brole\b/i);
    expect(sql).not.toMatch(/password/i);
    expect(sql).not.toMatch(/openfga/i);
    expect(sql).not.toMatch(/session/i);
  });
});
