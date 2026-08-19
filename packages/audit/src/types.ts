export class AuditError extends Error {
  override readonly name: string = "AuditError";
}
export class AuditInputError extends AuditError {
  override readonly name = "AuditInputError";
}
export class AuditAccessDeniedError extends AuditError {
  override readonly name = "AuditAccessDeniedError";
}

export type AuditOutcome = "allowed" | "denied" | "succeeded" | "failed";
export type AuditSource = "identity" | "authorization" | "audit";

export interface AuditEvent {
  readonly id: string;
  readonly occurredAt: Date;
  readonly actorAccountId: string | null;
  readonly subjectAccountId: string;
  readonly organizationId: string | null;
  readonly action: string;
  readonly resourceType: string;
  readonly resourceId: string | null;
  readonly outcome: string;
  readonly reason: string | null;
  readonly requestId: string | null;
  readonly source: string;
  readonly metadata: Record<string, unknown>;
}

export interface AuditCursor {
  readonly occurredAt: Date;
  readonly auditEventId: string;
}
export interface AuditPage {
  readonly events: readonly AuditEvent[];
  readonly nextCursor?: AuditCursor;
}
export interface AuthorizationAuditInput {
  readonly actorAccountId: string;
  readonly action: string;
  readonly resource: { readonly type: string; readonly id: string };
  readonly decision: { readonly allowed: boolean; readonly reason?: string };
  readonly requestId?: string;
  readonly metadata?: unknown;
}
export interface AuthenticationFailureInput {
  readonly email: string;
  readonly requestId?: string;
  readonly metadata?: unknown;
}
export interface AuditQuery {
  readonly authenticatedAccountId: string;
  readonly accountId: string;
  readonly organizationId?: string;
  readonly limit?: number;
  readonly cursor?: AuditCursor;
}
