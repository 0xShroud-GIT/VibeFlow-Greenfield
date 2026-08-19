import { and, eq } from "drizzle-orm";

import type { ControlPlaneDatabase } from "./client.js";
import {
  DuplicateMembershipError,
  ForeignKeyViolationError,
  mapDatabaseError,
  NotFoundError,
  PersistenceInputError,
  rejectProviderAuthority,
} from "./errors.js";
import { newId, requireId, requireNonEmpty } from "./ids.js";
import {
  accounts,
  ORGANIZATION_KINDS,
  organizationMemberships,
  organizations,
  type AccountRow,
  type OrganizationKind,
  type OrganizationMembershipRow,
  type OrganizationRow,
} from "./schema.js";

export interface CreateAccountInput {
  displayName: string;
}

export interface CreateOrganizationInput {
  name: string;
  kind: OrganizationKind;
}

export interface CreateMembershipInput {
  organizationId: string;
  accountId: string;
}

function now(): Date {
  return new Date();
}

function isOrganizationKind(value: string): value is OrganizationKind {
  return (ORGANIZATION_KINDS as readonly string[]).includes(value);
}

export class TenantRepository {
  public constructor(private readonly db: ControlPlaneDatabase) {}

  public async createAccount(input: CreateAccountInput): Promise<AccountRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const displayName = requireNonEmpty("displayName", input.displayName);
    const createdAt = now();
    const row = {
      id: newId(),
      displayName,
      createdAt,
      updatedAt: createdAt,
    };
    try {
      const inserted = await this.db.insert(accounts).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("account insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }

  public async getAccountById(accountId: string): Promise<AccountRow> {
    const id = requireId("accountId", accountId);
    const rows = await this.db.select().from(accounts).where(eq(accounts.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`account not found: ${id}`);
    }
    return row;
  }

  public async createOrganization(input: CreateOrganizationInput): Promise<OrganizationRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const name = requireNonEmpty("name", input.name);
    if (!isOrganizationKind(input.kind)) {
      throw new PersistenceInputError("organization kind must be personal or standard");
    }
    const createdAt = now();
    const row = {
      id: newId(),
      name,
      kind: input.kind,
      createdAt,
      updatedAt: createdAt,
    };
    try {
      const inserted = await this.db.insert(organizations).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("organization insert returned no row");
      }
      return created;
    } catch (error) {
      mapDatabaseError(error);
    }
  }

  public async getOrganizationById(organizationId: string): Promise<OrganizationRow> {
    const id = requireId("organizationId", organizationId);
    const rows = await this.db.select().from(organizations).where(eq(organizations.id, id));
    const row = rows[0];
    if (!row) {
      throw new NotFoundError(`organization not found: ${id}`);
    }
    return row;
  }

  public async addMembership(input: CreateMembershipInput): Promise<OrganizationMembershipRow> {
    rejectProviderAuthority(input as unknown as Record<string, unknown>);
    const organizationId = requireId("organizationId", input.organizationId);
    const accountId = requireId("accountId", input.accountId);
    const row = {
      id: newId(),
      organizationId,
      accountId,
      createdAt: now(),
    };
    try {
      const inserted = await this.db.insert(organizationMemberships).values(row).returning();
      const created = inserted[0];
      if (!created) {
        throw new PersistenceInputError("membership insert returned no row");
      }
      return created;
    } catch (error) {
      if (error instanceof DuplicateMembershipError || error instanceof ForeignKeyViolationError) {
        throw error;
      }
      mapDatabaseError(error);
    }
  }

  public async getMembership(input: CreateMembershipInput): Promise<OrganizationMembershipRow> {
    const organizationId = requireId("organizationId", input.organizationId);
    const accountId = requireId("accountId", input.accountId);
    const rows = await this.db
      .select()
      .from(organizationMemberships)
      .where(
        and(
          eq(organizationMemberships.organizationId, organizationId),
          eq(organizationMemberships.accountId, accountId),
        ),
      );
    const row = rows[0];
    if (!row) {
      throw new NotFoundError("organization membership not found");
    }
    return row;
  }

  /**
   * Persistence-boundary isolation: memberships are listed only for one
   * canonical organization id. There is no unscoped membership catalog.
   */
  public async listMembershipsForOrganization(organizationId: string): Promise<OrganizationMembershipRow[]> {
    const id = requireId("organizationId", organizationId);
    return this.db
      .select()
      .from(organizationMemberships)
      .where(eq(organizationMemberships.organizationId, id));
  }

  public async listOrganizationsForAccount(accountId: string): Promise<OrganizationRow[]> {
    const id = requireId("accountId", accountId);
    return this.db
      .select({
        id: organizations.id,
        name: organizations.name,
        kind: organizations.kind,
        createdAt: organizations.createdAt,
        updatedAt: organizations.updatedAt,
      })
      .from(organizationMemberships)
      .innerJoin(organizations, eq(organizations.id, organizationMemberships.organizationId))
      .where(eq(organizationMemberships.accountId, id));
  }

  public async createPersonalOrganizationForAccount(
    accountId: string,
    name: string,
  ): Promise<{ organization: OrganizationRow; membership: OrganizationMembershipRow }> {
    const account = await this.getAccountById(accountId);
    return this.db.transaction(async (tx) => {
      const scoped = new TenantRepository(tx);
      const organization = await scoped.createOrganization({
        name,
        kind: "personal",
      });
      const membership = await scoped.addMembership({
        organizationId: organization.id,
        accountId: account.id,
      });
      return { organization, membership };
    });
  }
}
