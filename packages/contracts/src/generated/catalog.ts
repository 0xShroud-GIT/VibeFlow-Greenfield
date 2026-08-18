/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by scripts/generate-contracts.py from the VibeFlow Master Build System.
 * Authoritative inputs (routed by 00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml):
 *   resources -> 02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml
 *   states    -> 03_BACKEND/STATE_MACHINES.yaml
 *   events    -> 03_BACKEND/EVENT_CATALOG.yaml
 *
 * Contracts are JSON Schema first. Every TypeScript type below is derived
 * from its raw JSON Schema literal via TypeBox `Static<>` inference; no
 * parallel handwritten union vocabulary is maintained here.
 *
 * Regenerate:  pnpm run contracts:generate
 * Verify:      pnpm run contracts:check
 */

import type { Static } from "typebox";

/** Catalog identity, stable across regeneration of identical inputs. */
export const CONTRACT_CATALOG_ID = "urn:vibeflow:contracts:catalog:v1" as const;

export const CONTRACT_CATALOG_SCHEMA_VERSION = "1.0" as const;

// ---------------------------------------------------------------------------
// Canonical resources (02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml)
// ---------------------------------------------------------------------------

/** Canonical resource names in authoritative file order. */
export const CANONICAL_RESOURCES = [
  "Account",
  "Organization",
  "Project",
  "Artifact",
  "ArtifactRelation",
  "AgentBinding",
  "ModelBinding",
  "WorkspaceBinding",
  "RepositoryBinding",
  "DeploymentBinding",
  "DataBinding",
  "ObjectStorageBinding",
  "Connection",
  "ConnectionGrant",
  "SecretRef",
  "Policy",
  "Approval",
  "Task",
  "Execution",
  "ExecutionAttempt",
  "Event",
  "EventCursor",
  "WorkspaceRevision",
  "CheckpointManifest",
  "RecoveryRecord",
  "Evidence",
  "Verification",
  "VerificationCheck",
  "Release",
  "ProviderCapability",
  "Entitlement",
  "UsageRecord",
  "Notification",
  "AuditEvent",
  "SupportCase",
] as const;

/** JSON Schema for the canonical resource-name vocabulary. */
export const CanonicalResourceNameSchema = {
  type: "string",
  enum: [
    "Account",
    "Organization",
    "Project",
    "Artifact",
    "ArtifactRelation",
    "AgentBinding",
    "ModelBinding",
    "WorkspaceBinding",
    "RepositoryBinding",
    "DeploymentBinding",
    "DataBinding",
    "ObjectStorageBinding",
    "Connection",
    "ConnectionGrant",
    "SecretRef",
    "Policy",
    "Approval",
    "Task",
    "Execution",
    "ExecutionAttempt",
    "Event",
    "EventCursor",
    "WorkspaceRevision",
    "CheckpointManifest",
    "RecoveryRecord",
    "Evidence",
    "Verification",
    "VerificationCheck",
    "Release",
    "ProviderCapability",
    "Entitlement",
    "UsageRecord",
    "Notification",
    "AuditEvent",
    "SupportCase"
  ]
} as const;

export type CanonicalResourceName = Static<typeof CanonicalResourceNameSchema>;

// ---------------------------------------------------------------------------
// State machines (03_BACKEND/STATE_MACHINES.yaml)
// ---------------------------------------------------------------------------

/** Canonical state-machine names in authoritative file order. */
export const STATE_MACHINE_NAMES = [
  "Task",
  "Execution",
  "Approval",
  "Connection",
  "Verification",
  "Release",
  "RecoveryRecord",
] as const;

/** JSON Schema for the canonical state-machine-name vocabulary. */
export const StateMachineNameSchema = {
  type: "string",
  enum: [
    "Task",
    "Execution",
    "Approval",
    "Connection",
    "Verification",
    "Release",
    "RecoveryRecord"
  ]
} as const;

export type StateMachineName = Static<typeof StateMachineNameSchema>;

/** JSON Schema for the canonical Task states. */
export const TaskStateSchema = {
  type: "string",
  enum: [
    "DRAFT",
    "READY",
    "RUNNING",
    "BLOCKED",
    "CANDIDATE_COMPLETE",
    "VERIFIED",
    "FAILED",
    "CANCELLED"
  ]
} as const;

export type TaskState = Static<typeof TaskStateSchema>;

/** JSON Schema for the canonical Task terminal states. */
export const TaskTerminalStateSchema = {
  type: "string",
  enum: [
    "VERIFIED",
    "FAILED",
    "CANCELLED"
  ]
} as const;

export type TaskTerminalState = Static<typeof TaskTerminalStateSchema>;

/** JSON Schema for the canonical Execution states. */
export const ExecutionStateSchema = {
  type: "string",
  enum: [
    "QUEUED",
    "STARTING",
    "RUNNING",
    "WAITING_APPROVAL",
    "INTERRUPTED",
    "CANDIDATE_COMPLETE",
    "VERIFYING",
    "VERIFIED",
    "FAILED",
    "CANCELLED",
    "LOST"
  ]
} as const;

export type ExecutionState = Static<typeof ExecutionStateSchema>;

/** JSON Schema for the canonical Execution terminal states. */
export const ExecutionTerminalStateSchema = {
  type: "string",
  enum: [
    "VERIFIED",
    "FAILED",
    "CANCELLED",
    "LOST"
  ]
} as const;

export type ExecutionTerminalState = Static<typeof ExecutionTerminalStateSchema>;

/** JSON Schema for the canonical Approval states. */
export const ApprovalStateSchema = {
  type: "string",
  enum: [
    "PENDING",
    "APPROVED",
    "DENIED",
    "EXPIRED",
    "CANCELLED"
  ]
} as const;

export type ApprovalState = Static<typeof ApprovalStateSchema>;

/** JSON Schema for the canonical Approval terminal states. */
export const ApprovalTerminalStateSchema = {
  type: "string",
  enum: [
    "APPROVED",
    "DENIED",
    "EXPIRED",
    "CANCELLED"
  ]
} as const;

export type ApprovalTerminalState = Static<typeof ApprovalTerminalStateSchema>;

/** JSON Schema for the canonical Connection states. */
export const ConnectionStateSchema = {
  type: "string",
  enum: [
    "UNLINKED",
    "LINKING",
    "ACTIVE",
    "DEGRADED",
    "REAUTH_REQUIRED",
    "REVOKED"
  ]
} as const;

export type ConnectionState = Static<typeof ConnectionStateSchema>;

/** JSON Schema for the canonical Connection terminal states. */
export const ConnectionTerminalStateSchema = {
  type: "string",
  enum: [
    "REVOKED"
  ]
} as const;

export type ConnectionTerminalState = Static<typeof ConnectionTerminalStateSchema>;

/** JSON Schema for the canonical Verification states. */
export const VerificationStateSchema = {
  type: "string",
  enum: [
    "PENDING",
    "RUNNING",
    "PASSED",
    "FAILED",
    "INTERRUPTED",
    "STALE"
  ]
} as const;

export type VerificationState = Static<typeof VerificationStateSchema>;

/** JSON Schema for the canonical Verification terminal states. */
export const VerificationTerminalStateSchema = {
  type: "string",
  enum: [
    "PASSED",
    "FAILED",
    "STALE"
  ]
} as const;

export type VerificationTerminalState = Static<typeof VerificationTerminalStateSchema>;

/** JSON Schema for the canonical Release states. */
export const ReleaseStateSchema = {
  type: "string",
  enum: [
    "DRAFT",
    "READY",
    "DEPLOYING",
    "DEPLOYED",
    "DEGRADED",
    "ROLLED_BACK",
    "FAILED"
  ]
} as const;

export type ReleaseState = Static<typeof ReleaseStateSchema>;

/** JSON Schema for the canonical Release terminal states. */
export const ReleaseTerminalStateSchema = {
  type: "string",
  enum: [
    "ROLLED_BACK",
    "FAILED"
  ]
} as const;

export type ReleaseTerminalState = Static<typeof ReleaseTerminalStateSchema>;

/** JSON Schema for the canonical RecoveryRecord states. */
export const RecoveryRecordStateSchema = {
  type: "string",
  enum: [
    "STARTED",
    "REPLAYING_EVENTS",
    "RECONCILING_WORKSPACE",
    "REATTACHING_PROVIDER",
    "REVERIFYING",
    "RECOVERED",
    "BLOCKED",
    "EXECUTION_LOST"
  ]
} as const;

export type RecoveryRecordState = Static<typeof RecoveryRecordStateSchema>;

/** JSON Schema for the canonical RecoveryRecord terminal states. */
export const RecoveryRecordTerminalStateSchema = {
  type: "string",
  enum: [
    "RECOVERED",
    "BLOCKED",
    "EXECUTION_LOST"
  ]
} as const;

export type RecoveryRecordTerminalState = Static<typeof RecoveryRecordTerminalStateSchema>;

// ---------------------------------------------------------------------------
// Events (03_BACKEND/EVENT_CATALOG.yaml)
// ---------------------------------------------------------------------------

/** Canonical event IDs in authoritative file order. */
export const EVENT_IDS = [
  "EVT-001",
  "EVT-002",
  "EVT-003",
  "EVT-004",
  "EVT-005",
  "EVT-006",
  "EVT-007",
  "EVT-008",
  "EVT-009",
  "EVT-010",
  "EVT-011",
  "EVT-012",
  "EVT-013",
  "EVT-014",
  "EVT-015",
  "EVT-016",
  "EVT-017",
  "EVT-018",
  "EVT-019",
  "EVT-020",
  "EVT-021",
  "EVT-022",
  "EVT-023",
  "EVT-024",
  "EVT-025",
  "EVT-026",
  "EVT-027",
  "EVT-028",
  "EVT-029",
  "EVT-030",
  "EVT-031",
  "EVT-032",
  "EVT-033",
  "EVT-034",
  "EVT-035",
  "EVT-036",
  "EVT-037",
] as const;

/** Canonical event names in authoritative file order. */
export const EVENT_NAMES = [
  "project.created",
  "project.updated",
  "binding.created",
  "binding.updated",
  "task.created",
  "execution.queued",
  "execution.started",
  "execution.output",
  "execution.waiting_for_approval",
  "execution.interrupted",
  "execution.candidate_complete",
  "execution.failed",
  "execution.cancelled",
  "approval.requested",
  "approval.decided",
  "verification.started",
  "verification.check_started",
  "verification.check_passed",
  "verification.check_failed",
  "verification.completed",
  "workspace.reconciled",
  "checkpoint.created",
  "recovery.started",
  "recovery.completed",
  "recovery.blocked",
  "connection.linked",
  "grant.created",
  "grant.revoked",
  "provider.capability_changed",
  "release.created",
  "deployment.started",
  "deployment.completed",
  "deployment.failed",
  "deployment.rolled_back",
  "usage.recorded",
  "notification.created",
  "audit.recorded",
] as const;

/** JSON Schema for canonical event IDs. */
export const EventIdSchema = {
  type: "string",
  enum: [
    "EVT-001",
    "EVT-002",
    "EVT-003",
    "EVT-004",
    "EVT-005",
    "EVT-006",
    "EVT-007",
    "EVT-008",
    "EVT-009",
    "EVT-010",
    "EVT-011",
    "EVT-012",
    "EVT-013",
    "EVT-014",
    "EVT-015",
    "EVT-016",
    "EVT-017",
    "EVT-018",
    "EVT-019",
    "EVT-020",
    "EVT-021",
    "EVT-022",
    "EVT-023",
    "EVT-024",
    "EVT-025",
    "EVT-026",
    "EVT-027",
    "EVT-028",
    "EVT-029",
    "EVT-030",
    "EVT-031",
    "EVT-032",
    "EVT-033",
    "EVT-034",
    "EVT-035",
    "EVT-036",
    "EVT-037"
  ]
} as const;

export type EventId = Static<typeof EventIdSchema>;

/** JSON Schema for canonical event names. */
export const EventNameSchema = {
  type: "string",
  enum: [
    "project.created",
    "project.updated",
    "binding.created",
    "binding.updated",
    "task.created",
    "execution.queued",
    "execution.started",
    "execution.output",
    "execution.waiting_for_approval",
    "execution.interrupted",
    "execution.candidate_complete",
    "execution.failed",
    "execution.cancelled",
    "approval.requested",
    "approval.decided",
    "verification.started",
    "verification.check_started",
    "verification.check_passed",
    "verification.check_failed",
    "verification.completed",
    "workspace.reconciled",
    "checkpoint.created",
    "recovery.started",
    "recovery.completed",
    "recovery.blocked",
    "connection.linked",
    "grant.created",
    "grant.revoked",
    "provider.capability_changed",
    "release.created",
    "deployment.started",
    "deployment.completed",
    "deployment.failed",
    "deployment.rolled_back",
    "usage.recorded",
    "notification.created",
    "audit.recorded"
  ]
} as const;

export type EventName = Static<typeof EventNameSchema>;

/**
 * Canonical event catalog metadata in authoritative file order.
 *
 * Only metadata that EVENT_CATALOG.yaml actually defines is projected here.
 * Event payload schemas are intentionally absent: no authoritative domain
 * mission has defined them yet, and M-005 does not manufacture authority.
 */
export const EVENT_CATALOG = [
  { id: "EVT-001", name: "project.created", resource: "Project", producer: "project", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-002", name: "project.updated", resource: "Project", producer: "project", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-003", name: "binding.created", resource: "*Binding", producer: "project", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-004", name: "binding.updated", resource: "*Binding", producer: "project", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-005", name: "task.created", resource: "Task", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-006", name: "execution.queued", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-007", name: "execution.started", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-008", name: "execution.output", resource: "Execution", producer: "gateway", envelope: "VibeFlowEventV1", durable: false },
  { id: "EVT-009", name: "execution.waiting_for_approval", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-010", name: "execution.interrupted", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-011", name: "execution.candidate_complete", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-012", name: "execution.failed", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-013", name: "execution.cancelled", resource: "Execution", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-014", name: "approval.requested", resource: "Approval", producer: "policy", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-015", name: "approval.decided", resource: "Approval", producer: "policy", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-016", name: "verification.started", resource: "Verification", producer: "verification", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-017", name: "verification.check_started", resource: "VerificationCheck", producer: "verification", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-018", name: "verification.check_passed", resource: "VerificationCheck", producer: "verification", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-019", name: "verification.check_failed", resource: "VerificationCheck", producer: "verification", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-020", name: "verification.completed", resource: "Verification", producer: "verification", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-021", name: "workspace.reconciled", resource: "WorkspaceRevision", producer: "workspace", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-022", name: "checkpoint.created", resource: "CheckpointManifest", producer: "repository", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-023", name: "recovery.started", resource: "RecoveryRecord", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-024", name: "recovery.completed", resource: "RecoveryRecord", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-025", name: "recovery.blocked", resource: "RecoveryRecord", producer: "execution", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-026", name: "connection.linked", resource: "Connection", producer: "connection", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-027", name: "grant.created", resource: "ConnectionGrant", producer: "connection", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-028", name: "grant.revoked", resource: "ConnectionGrant", producer: "connection", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-029", name: "provider.capability_changed", resource: "ProviderCapability", producer: "provider-registry", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-030", name: "release.created", resource: "Release", producer: "release", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-031", name: "deployment.started", resource: "Release", producer: "release", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-032", name: "deployment.completed", resource: "Release", producer: "release", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-033", name: "deployment.failed", resource: "Release", producer: "release", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-034", name: "deployment.rolled_back", resource: "Release", producer: "release", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-035", name: "usage.recorded", resource: "UsageRecord", producer: "billing", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-036", name: "notification.created", resource: "Notification", producer: "notification", envelope: "VibeFlowEventV1", durable: true },
  { id: "EVT-037", name: "audit.recorded", resource: "AuditEvent", producer: "audit", envelope: "VibeFlowEventV1", durable: true },
] as const;

/** One canonical event-catalog row, derived from the generated catalog data. */
export type EventCatalogEntry = (typeof EVENT_CATALOG)[number];
