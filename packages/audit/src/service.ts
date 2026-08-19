import { sanitizeAuditMetadata } from "./metadata.js";
import {
  AuditAccessDeniedError,
  AuditInputError,
  type AuditEvent,
  type AuditPage,
  type AuditQuery,
  type AuthenticationFailureInput,
  type AuthorizationAuditInput,
} from "./types.js";

const AUTHORIZATION_ACTIONS = new Set(["read", "create", "update", "delete", "list"]);
const PAGE_LIMIT_DEFAULT = 50;
const PAGE_LIMIT_MAX = 100;

/** VibeFlow authoritative audit boundary; intentionally no generic client create API. */
export interface AuditDatabase {
  query(text: string, values?: unknown[]): Promise<{ rows: unknown[] }>;
}

export class AuditService {
  public constructor(private readonly database: AuditDatabase) {}

  public async recordAuthorizationDecision(input: AuthorizationAuditInput): Promise<void> {
    const actorAccountId = requireUuid("actorAccountId", input.actorAccountId);
    const actorRows = await this.query<{ id: string }>("SELECT id FROM accounts WHERE id = $1", [actorAccountId]);
    const actor = actorRows[0];
    if (!actor) throw new AuditInputError("actor account is not canonical");
    if (!AUTHORIZATION_ACTIONS.has(input.action)) {
      throw new AuditInputError("authorization audit action is not registered");
    }
    const resourceId = requireUuid("resource.id", input.resource.id);
    const metadata = sanitizeAuditMetadata(input.metadata);
    let organizationId: string | null = null;
    if (input.resource.type === "organization") {
      const organizations = await this.query<{ id: string }>("SELECT id FROM organizations WHERE id = $1", [resourceId]);
      organizationId = organizations[0]?.id ?? null;
    } else if (input.resource.type === "project") {
      const projects = await this.query<{ organization_id: string }>(
        "SELECT organization_id FROM projects WHERE id = $1",
        [resourceId],
      );
      organizationId = projects[0]?.organization_id ?? null;
    }
    await this.insert({
      actorAccountId: actor.id,
      subjectAccountId: actor.id,
      organizationId,
      action: `authorization.${input.action}`,
      resourceType: input.resource.type,
      resourceId,
      outcome: input.decision.allowed ? "allowed" : "denied",
      reason: input.decision.allowed ? null : (input.decision.reason ?? "denied"),
      requestId: optionalUuid("requestId", input.requestId),
      source: "authorization",
      metadata,
    });
  }

  /** Failed credentials never become actor identity; only a canonical target account scopes the event. */
  public async recordAuthenticationFailure(input: AuthenticationFailureInput): Promise<void> {
    const email = input.email.trim().toLowerCase();
    if (email.length === 0) return;
    const result = await this.query<{ account_id: string }>(
      `SELECT vibeflow_account_id AS account_id FROM identity_users WHERE email = $1`,
      [email],
    );
    const link = result[0];
    if (!link) return;
    await this.insert({
      actorAccountId: null,
      subjectAccountId: link.account_id,
      organizationId: null,
      action: "authentication.login_failed",
      resourceType: "account",
      resourceId: link.account_id,
      outcome: "failed",
      reason: "invalid_credentials",
      requestId: optionalUuid("requestId", input.requestId),
      source: "identity",
      metadata: sanitizeAuditMetadata(input.metadata),
    });
  }

  public async list(input: AuditQuery): Promise<AuditPage> {
    const authenticated = requireUuid("authenticatedAccountId", input.authenticatedAccountId);
    const accountId = requireUuid("accountId", input.accountId);
    if (authenticated !== accountId) throw new AuditAccessDeniedError("cross-account audit access denied");
    const accounts = await this.query<{ id: string }>("SELECT id FROM accounts WHERE id = $1", [authenticated]);
    if (!accounts[0]) throw new AuditAccessDeniedError("audit account is not canonical");
    const organizationId = input.organizationId === undefined ? undefined : requireUuid("organizationId", input.organizationId);
    if (organizationId !== undefined) {
      try {
        const memberships = await this.query<{ id: string }>(
          "SELECT id FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
          [organizationId, authenticated],
        );
        if (!memberships[0]) throw new Error("membership absent");
      } catch {
        throw new AuditAccessDeniedError("cross-tenant audit access denied");
      }
    }
    const limit = input.limit ?? PAGE_LIMIT_DEFAULT;
    if (!Number.isInteger(limit) || limit < 1 || limit > PAGE_LIMIT_MAX) {
      throw new AuditInputError("audit page limit must be an integer from 1 to 100");
    }

    const values: unknown[] = [accountId];
    const predicates = ["subject_account_id = $1"];
    if (organizationId !== undefined) {
      values.push(organizationId);
      predicates.push(`organization_id = $${values.length}`);
    }
    if (input.cursor !== undefined) {
      if (!(input.cursor.occurredAt instanceof Date) || !Number.isFinite(input.cursor.occurredAt.getTime())) {
        throw new AuditInputError("audit cursor timestamp is invalid");
      }
      const cursorId = requireUuid("cursor.auditEventId", input.cursor.auditEventId);
      values.push(input.cursor.occurredAt, cursorId);
      const timestampPosition = values.length - 1;
      const idPosition = values.length;
      predicates.push(`(occurred_at < $${timestampPosition} OR (occurred_at = $${timestampPosition} AND id < $${idPosition}))`);
    }
    values.push(limit + 1);
    const result = await this.query<AuditDatabaseRow>(
      `SELECT id, occurred_at, actor_account_id, subject_account_id, organization_id,
              action, resource_type, resource_id, outcome, reason, request_id, source, metadata
       FROM audit_events
       WHERE ${predicates.join(" AND ")}
       ORDER BY occurred_at DESC, id DESC
       LIMIT $${values.length}`,
      values,
    );
    const mapped = result.map(mapRow);
    const hasMore = mapped.length > limit;
    const events = hasMore ? mapped.slice(0, limit) : mapped;
    const last = events.at(-1);
    return {
      events,
      ...(hasMore && last ? { nextCursor: { occurredAt: last.occurredAt, auditEventId: last.id } } : {}),
    };
  }

  private async query<Row>(text: string, values: unknown[] = []): Promise<Row[]> {
    const result = await this.database.query(text, values);
    return result.rows as Row[];
  }

  private async insert(input: Omit<AuditEvent, "id" | "occurredAt">): Promise<void> {
    // PostgreSQL generates id and occurred_at; no client/provider value can override them.
    await this.database.query(
      `INSERT INTO audit_events (
         actor_account_id, subject_account_id, organization_id, action, resource_type,
         resource_id, outcome, reason, request_id, source, metadata
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)`,
      [input.actorAccountId, input.subjectAccountId, input.organizationId, input.action,
       input.resourceType, input.resourceId, input.outcome, input.reason, input.requestId,
       input.source, JSON.stringify(input.metadata)],
    );
  }
}

interface AuditDatabaseRow {
  id: string; occurred_at: Date; actor_account_id: string | null; subject_account_id: string;
  organization_id: string | null; action: string; resource_type: string; resource_id: string | null;
  outcome: string; reason: string | null; request_id: string | null; source: string;
  metadata: Record<string, unknown>;
}
function mapRow(row: AuditDatabaseRow): AuditEvent {
  return { id: row.id, occurredAt: row.occurred_at, actorAccountId: row.actor_account_id,
    subjectAccountId: row.subject_account_id, organizationId: row.organization_id,
    action: row.action, resourceType: row.resource_type, resourceId: row.resource_id,
    outcome: row.outcome, reason: row.reason, requestId: row.request_id,
    source: row.source, metadata: row.metadata };
}
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function requireUuid(name: string, value: string): string {
  if (!UUID_RE.test(value)) throw new AuditInputError(`${name} must be a canonical UUID`);
  return value;
}
function optionalUuid(name: string, value: string | undefined): string | null {
  return value === undefined ? null : requireUuid(name, value);
}
