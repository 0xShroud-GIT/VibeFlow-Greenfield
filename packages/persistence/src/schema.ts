import {
  bigint,
  boolean,
  foreignKey,
  integer,
  jsonb,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";

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

/**
 * M-014 archive intake vocabulary.
 *
 * Exactly the formats the capability ledger / evidence map prove for
 * VF-PRJ-004 (R2V-083): "ZIP/tar upload + scanner". The set is deliberately
 * not broadened for completeness.
 */
export const ARCHIVE_FORMATS = ["zip", "tar"] as const;
export type ArchiveFormat = (typeof ARCHIVE_FORMATS)[number];

/**
 * M-014 owns exactly one import source kind. Provider-specific adapters
 * (VF-PRJ-008 Bitbucket, VF-PRJ-009 builder migration, VF-PRJ-010 Figma,
 * VF-PRJ-011 Vercel, VF-PRJ-012 GitHub) are deferred and must not widen this
 * without their own mission.
 */
export const ARCHIVE_IMPORT_SOURCE_KINDS = ["archive"] as const;
export type ArchiveImportSourceKind = (typeof ARCHIVE_IMPORT_SOURCE_KINDS)[number];

/** Accepted manifest entry kinds. Every other entry type is rejected outright. */
export const ARCHIVE_ENTRY_KINDS = ["file", "directory"] as const;
export type ArchiveEntryKind = (typeof ARCHIVE_ENTRY_KINDS)[number];

/** M-014 defines exactly one internal plan kind; no public state machine. */
export const PROJECT_CLONE_PLAN_KINDS = ["project_clone"] as const;
export type ProjectClonePlanKind = (typeof PROJECT_CLONE_PLAN_KINDS)[number];

/**
 * Canonical relation kinds between Artifacts. These are the exact semantics
 * named by the canonical resource model: lineage, variant, derived-from,
 * contains. M-013 does not invent additional kinds.
 */
export const ARTIFACT_RELATION_KINDS = [
  "lineage",
  "variant",
  "derived-from",
  "contains",
] as const;
export type ArtifactRelationKind = (typeof ARTIFACT_RELATION_KINDS)[number];

/**
 * M-013 authoritative Artifact: VibeFlow-owned durable typed-output metadata
 * rooted in canonical Project ownership. Server-generated id, canonical
 * Project FK, bounded type token, server-controlled timestamps. Content bytes
 * remain owned by blob/provider and are never part of this metadata row.
 *
 * The composite unique (project_id, id) key is the authoritative target of the
 * ArtifactRelation composite foreign keys; it makes a cross-Project edge
 * impossible at the database level.
 */
export const artifacts = pgTable(
  "artifacts",
  {
    id: uuid("id").primaryKey(),
    projectId: uuid("project_id")
      .notNull()
      .references(() => projects.id),
    type: text("type").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true, mode: "date" }).notNull(),
  },
  (table) => ({
    projectIdIdUnique: unique("artifacts_project_id_id_uidx").on(
      table.projectId,
      table.id,
    ),
  }),
);

/**
 * M-013 authoritative ArtifactRelation: a durable directed subject/object edge
 * owned by a canonical Project. The Project is derived from the canonical
 * endpoint Artifacts (never a client claim), and the composite foreign keys
 * pin both endpoints to that same Project so a cross-Project edge is rejected
 * by the database even if service checks are bypassed.
 */
export const artifactRelations = pgTable(
  "artifact_relations",
  {
    id: uuid("id").primaryKey(),
    projectId: uuid("project_id").notNull(),
    subjectArtifactId: uuid("subject_artifact_id").notNull(),
    objectArtifactId: uuid("object_artifact_id").notNull(),
    relationKind: text("relation_kind").$type<ArtifactRelationKind>().notNull(),
    createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  },
  (table) => ({
    projectSubjectFk: foreignKey({
      name: "artifact_relations_project_subject_fk",
      columns: [table.projectId, table.subjectArtifactId],
      foreignColumns: [artifacts.projectId, artifacts.id],
    }),
    projectObjectFk: foreignKey({
      name: "artifact_relations_project_object_fk",
      columns: [table.projectId, table.objectArtifactId],
      foreignColumns: [artifacts.projectId, artifacts.id],
    }),
    uniqueEdge: unique("artifact_relations_unique_edge").on(
      table.projectId,
      table.subjectArtifactId,
      table.relationKind,
      table.objectArtifactId,
    ),
  }),
);

/**
 * M-014 PROJECT-DOMAIN INTERNAL archive-import record.
 *
 * This is NOT a canonical resource. `CANONICAL_RESOURCE_MODEL.yaml` defines no
 * top-level Import/Template/ProjectImport resource and M-014 does not add one.
 * The row exists only to make archive-import provenance and command
 * idempotency durable. Canonical authority remains
 * Account -> Organization membership -> Project -> Artifact/ArtifactRelation.
 *
 * Archive bytes are never stored here. Only server-derived normalized metadata
 * and cryptographic fingerprints are. `stagedBlobRef` is an opaque reference
 * into a private content-addressed staging namespace; it is explicitly NOT a
 * canonical ObjectStorageBinding and advances no storage/provider capability.
 */
export const projectArchiveImports = pgTable(
  "project_archive_imports",
  {
    id: uuid("id").primaryKey(),
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id),
    projectId: uuid("project_id").notNull(),
    actorAccountId: uuid("actor_account_id")
      .notNull()
      .references(() => accounts.id),
    sourceKind: text("source_kind").$type<ArchiveImportSourceKind>().notNull(),
    archiveFormat: text("archive_format").$type<ArchiveFormat>().notNull(),
    archiveSha256: text("archive_sha256").notNull(),
    archiveByteSize: bigint("archive_byte_size", { mode: "number" }).notNull(),
    manifestSha256: text("manifest_sha256").notNull(),
    manifestEntryCount: integer("manifest_entry_count").notNull(),
    manifestTotalDeclaredSize: bigint("manifest_total_declared_size", {
      mode: "number",
    }).notNull(),
    stagedBlobRef: text("staged_blob_ref"),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  },
  (table) => ({
    orgProjectFk: foreignKey({
      name: "project_archive_imports_org_project_fk",
      columns: [table.organizationId, table.projectId],
      foreignColumns: [projects.organizationId, projects.id],
    }),
    idempotencyUnique: unique("project_archive_imports_idempotency_uidx").on(
      table.organizationId,
      table.actorAccountId,
      table.idempotencyKey,
    ),
    projectUnique: unique("project_archive_imports_project_uidx").on(table.projectId),
  }),
);

/**
 * One normalized, already-accepted manifest entry. The structural scanner
 * rejects the whole archive before anything reaches this table, so every row
 * here has a normalized relative traversal-free path.
 */
export const projectArchiveImportEntries = pgTable(
  "project_archive_import_entries",
  {
    id: uuid("id").primaryKey(),
    importId: uuid("import_id")
      .notNull()
      .references(() => projectArchiveImports.id, { onDelete: "cascade" }),
    entryIndex: integer("entry_index").notNull(),
    normalizedPath: text("normalized_path").notNull(),
    entryKind: text("entry_kind").$type<ArchiveEntryKind>().notNull(),
    declaredSize: bigint("declared_size", { mode: "number" }).notNull(),
    compressedSize: bigint("compressed_size", { mode: "number" }).notNull(),
    contentSha256: text("content_sha256"),
    crc32: text("crc32"),
  },
  (table) => ({
    indexUnique: unique("project_archive_import_entries_index_uidx").on(
      table.importId,
      table.entryIndex,
    ),
    pathUnique: unique("project_archive_import_entries_path_uidx").on(
      table.importId,
      table.normalizedPath,
    ),
  }),
);

/**
 * M-014 PROJECT-DOMAIN INTERNAL Project Clone Plan record (VF-PRJ-007 /
 * R2V-086 fork/remix/template). Not a canonical `Template` resource, catalog,
 * or marketplace: a template operation in M-014 is exactly "create a new
 * canonical Project from an authorized source Project".
 *
 * Both endpoints are pinned to the plan's single canonical Organization by
 * composite foreign keys, so the M-014 same-tenant template policy holds at
 * the database level even if service checks are bypassed. Cross-Organization
 * / public template semantics remain deferred.
 */
export const projectClonePlans = pgTable(
  "project_clone_plans",
  {
    id: uuid("id").primaryKey(),
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id),
    sourceProjectId: uuid("source_project_id").notNull(),
    targetProjectId: uuid("target_project_id").notNull(),
    actorAccountId: uuid("actor_account_id")
      .notNull()
      .references(() => accounts.id),
    planKind: text("plan_kind").$type<ProjectClonePlanKind>().notNull(),
    artifactCount: integer("artifact_count").notNull(),
    relationCount: integer("relation_count").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).notNull(),
  },
  (table) => ({
    orgSourceFk: foreignKey({
      name: "project_clone_plans_org_source_fk",
      columns: [table.organizationId, table.sourceProjectId],
      foreignColumns: [projects.organizationId, projects.id],
    }),
    orgTargetFk: foreignKey({
      name: "project_clone_plans_org_target_fk",
      columns: [table.organizationId, table.targetProjectId],
      foreignColumns: [projects.organizationId, projects.id],
    }),
    idempotencyUnique: unique("project_clone_plans_idempotency_uidx").on(
      table.organizationId,
      table.actorAccountId,
      table.idempotencyKey,
    ),
    targetUnique: unique("project_clone_plans_target_uidx").on(table.targetProjectId),
  }),
);

/**
 * Clone provenance: the source -> target Artifact id remapping.
 *
 * Deliberately NOT an ArtifactRelation. ArtifactRelation is M-013 same-Project
 * canonical graph state and is never cross-Project clone provenance.
 */
export const projectCloneArtifactMap = pgTable(
  "project_clone_artifact_map",
  {
    id: uuid("id").primaryKey(),
    clonePlanId: uuid("clone_plan_id")
      .notNull()
      .references(() => projectClonePlans.id, { onDelete: "cascade" }),
    sourceArtifactId: uuid("source_artifact_id")
      .notNull()
      .references(() => artifacts.id),
    targetArtifactId: uuid("target_artifact_id")
      .notNull()
      .references(() => artifacts.id),
  },
  (table) => ({
    sourceUnique: unique("project_clone_artifact_map_source_uidx").on(
      table.clonePlanId,
      table.sourceArtifactId,
    ),
    targetUnique: unique("project_clone_artifact_map_target_uidx").on(
      table.clonePlanId,
      table.targetArtifactId,
    ),
  }),
);

export type AccountRow = typeof accounts.$inferSelect;
export type OrganizationRow = typeof organizations.$inferSelect;
export type OrganizationMembershipRow = typeof organizationMemberships.$inferSelect;
export type IdentityUserRow = typeof identityUsers.$inferSelect;
export type AuditEventRow = typeof auditEvents.$inferSelect;
export type ProjectRow = typeof projects.$inferSelect;
export type ArtifactRow = typeof artifacts.$inferSelect;
export type ArtifactRelationRow = typeof artifactRelations.$inferSelect;
export type ProjectArchiveImportRow = typeof projectArchiveImports.$inferSelect;
export type ProjectArchiveImportEntryRow = typeof projectArchiveImportEntries.$inferSelect;
export type ProjectClonePlanRow = typeof projectClonePlans.$inferSelect;
export type ProjectCloneArtifactMapRow = typeof projectCloneArtifactMap.$inferSelect;

/** M-008 tenant authority only; keep library session/auth tables out of it. */
export const TENANT_TABLES = {
  accounts,
  organizations,
  organizationMemberships,
} as const;

/** All Drizzle tables queried by VibeFlow control-plane modules through M-014. */
export const CONTROL_PLANE_TABLES = {
  ...TENANT_TABLES,
  identityUsers,
  auditEvents,
  projects,
  artifacts,
  artifactRelations,
  projectArchiveImports,
  projectArchiveImportEntries,
  projectClonePlans,
  projectCloneArtifactMap,
} as const;
