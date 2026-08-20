export class PersistenceError extends Error {
  override readonly name: string = "PersistenceError";
}

export class PersistenceInputError extends PersistenceError {
  override readonly name = "PersistenceInputError";
}

export class NotFoundError extends PersistenceError {
  override readonly name = "NotFoundError";
}

export class DuplicateMembershipError extends PersistenceError {
  override readonly name = "DuplicateMembershipError";
}

export class ForeignKeyViolationError extends PersistenceError {
  override readonly name = "ForeignKeyViolationError";
}

export class ProviderAuthorityRejectedError extends PersistenceError {
  override readonly name = "ProviderAuthorityRejectedError";
}

/** A relation whose endpoints resolve to different canonical Projects. */
export class CrossProjectArtifactRelationError extends PersistenceError {
  override readonly name = "CrossProjectArtifactRelationError";
}

/** A duplicate (project, subject, kind, object) relation edge. */
export class DuplicateArtifactRelationError extends PersistenceError {
  override readonly name = "DuplicateArtifactRelationError";
}

const PROVIDER_AUTHORITY_KEYS = [
  "providerId",
  "provider_id",
  "externalId",
  "external_id",
  "clientTenantId",
  "client_tenant_id",
  "providerAccountId",
  "provider_account_id",
  "providerOrganizationId",
  "provider_organization_id",
] as const;

export function rejectProviderAuthority(input: Record<string, unknown>): void {
  const present = PROVIDER_AUTHORITY_KEYS.filter((key) => {
    return Object.prototype.hasOwnProperty.call(input, key) && input[key] !== undefined;
  });
  if (present.length > 0) {
    throw new ProviderAuthorityRejectedError(
      `Client/provider identifiers never establish tenant authority: ${present.join(", ")}`,
    );
  }
}

interface PgLikeError {
  code?: string;
  constraint?: string;
  cause?: unknown;
}

function postgresErrorCode(error: unknown): string | undefined {
  let current: unknown = error;
  const seen = new Set<unknown>();
  while (current && typeof current === "object" && !seen.has(current)) {
    seen.add(current);
    const candidate = current as PgLikeError;
    if (typeof candidate.code === "string" && /^\d{5}$/.test(candidate.code)) {
      return candidate.code;
    }
    current = candidate.cause;
  }
  return undefined;
}

export function mapDatabaseError(error: unknown): never {
  const code = postgresErrorCode(error);
  if (code === "23505") {
    throw new DuplicateMembershipError("organization membership already exists");
  }
  if (code === "23503") {
    throw new ForeignKeyViolationError("referenced account or organization does not exist");
  }
  if (error instanceof PersistenceError) {
    throw error;
  }
  throw new PersistenceError(error instanceof Error ? error.message : "persistence operation failed");
}
