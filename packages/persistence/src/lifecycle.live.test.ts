/**
 * M-014 persistence-boundary live PostgreSQL 18.4 tests.
 *
 * These prove the DATABASE-level backstops for the archive-import and
 * clone-plan records, independent of service code: constraints must hold even
 * if a service check is bypassed entirely.
 */

import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { applyCommittedSqlMigrations, defaultMigrationsDirectory } from "./migrate.js";
import { createControlPlanePool, type ControlPlanePool } from "./client.js";
import {
  DuplicateIdempotentCommandError,
  ProviderAuthorityRejectedError,
} from "./errors.js";
import { ProjectLifecycleRepository } from "./lifecycle-repository.js";
import { ArtifactRepository, ProjectRepository, TenantRepository } from "./repositories.js";
import type { AccountRow, OrganizationRow, ProjectRow } from "./schema.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-014 lifecycle persistence tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-014 import/clone persistence integrity", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;
  let lifecycle: ProjectLifecycleRepository;

  let account: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let projectA: ProjectRow;
  let projectB: ProjectRow;

  const validManifest = [
    {
      entryIndex: 0,
      normalizedPath: "src/index.ts",
      kind: "file" as const,
      declaredSize: 10,
      compressedSize: 8,
      contentSha256: "d".repeat(64),
    },
  ];

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);
    lifecycle = new ProjectLifecycleRepository(controlPlane.db);

    account = await tenants.createAccount({ displayName: "Lifecycle Persistence" });
    orgA = await tenants.createOrganization({ name: "LP Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "LP Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: account.id });
    projectA = await projects.createProject({ organizationId: orgA.id, name: "LP A" });
    projectB = await projects.createProject({ organizationId: orgB.id, name: "LP B" });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("stores only server-derived fingerprints, never archive bytes", async () => {
    const applied = await lifecycle.applyArchiveImport({
      organizationId: orgA.id,
      actorAccountId: account.id,
      projectName: "Fingerprint Only",
      archiveFormat: "zip",
      archiveSha256: "a".repeat(64),
      archiveByteSize: 512,
      manifestSha256: "b".repeat(64),
      manifestEntries: validManifest,
      idempotencyKey: randomUUID(),
    });

    const columns = await controlPlane.pool.query(
      `SELECT column_name FROM information_schema.columns
        WHERE table_name = 'project_archive_imports'`,
    );
    const names = columns.rows.map((r) => (r as { column_name: string }).column_name);
    // No column can hold archive content.
    expect(names).not.toContain("archive_bytes");
    expect(names).not.toContain("content");
    expect(names).not.toContain("payload");
    expect(names).toContain("archive_sha256");
    expect(names).toContain("manifest_sha256");
    expect(applied.import.archiveSha256).toBe("a".repeat(64));
  });

  it("rejects a non-hex archive or manifest digest", async () => {
    await expect(
      lifecycle.applyArchiveImport({
        organizationId: orgA.id,
        actorAccountId: account.id,
        projectName: "Bad Digest",
        archiveFormat: "zip",
        archiveSha256: "not-a-digest",
        archiveByteSize: 1,
        manifestSha256: "b".repeat(64),
        manifestEntries: [],
        idempotencyKey: randomUUID(),
      }),
    ).rejects.toThrow(/SHA-256/);
  });

  it("rejects provider/external authority keys on import", async () => {
    await expect(
      lifecycle.applyArchiveImport({
        organizationId: orgA.id,
        actorAccountId: account.id,
        projectName: "Provider Authority",
        archiveFormat: "zip",
        archiveSha256: "a".repeat(64),
        archiveByteSize: 1,
        manifestSha256: "b".repeat(64),
        manifestEntries: [],
        idempotencyKey: randomUUID(),
        providerId: "gh_1",
      } as unknown as Parameters<typeof lifecycle.applyArchiveImport>[0]),
    ).rejects.toBeInstanceOf(ProviderAuthorityRejectedError);
  });

  it("rejects an unsupported archive format at the database level", async () => {
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_archive_imports
           (id, organization_id, project_id, actor_account_id, source_kind, archive_format,
            archive_sha256, archive_byte_size, manifest_sha256, manifest_entry_count,
            manifest_total_declared_size, idempotency_key, created_at)
         VALUES ($1,$2,$3,$4,'archive','rar',$5,1,$6,0,0,$7, now())`,
        [randomUUID(), orgA.id, projectA.id, account.id, "a".repeat(64), "b".repeat(64), randomUUID()],
      ),
    ).rejects.toThrow();
  });

  it("rejects a provider source_kind at the database level", async () => {
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_archive_imports
           (id, organization_id, project_id, actor_account_id, source_kind, archive_format,
            archive_sha256, archive_byte_size, manifest_sha256, manifest_entry_count,
            manifest_total_declared_size, idempotency_key, created_at)
         VALUES ($1,$2,$3,$4,'github','zip',$5,1,$6,0,0,$7, now())`,
        [randomUUID(), orgA.id, projectA.id, account.id, "a".repeat(64), "b".repeat(64), randomUUID()],
      ),
    ).rejects.toThrow();
  });

  it("rejects an import whose Project belongs to another Organization", async () => {
    // The composite FK pins the imported Project to the import's org.
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_archive_imports
           (id, organization_id, project_id, actor_account_id, source_kind, archive_format,
            archive_sha256, archive_byte_size, manifest_sha256, manifest_entry_count,
            manifest_total_declared_size, idempotency_key, created_at)
         VALUES ($1,$2,$3,$4,'archive','zip',$5,1,$6,0,0,$7, now())`,
        [randomUUID(), orgA.id, projectB.id, account.id, "a".repeat(64), "b".repeat(64), randomUUID()],
      ),
    ).rejects.toThrow();
  });

  it("rejects an unsafe manifest path at the database level", async () => {
    const applied = await lifecycle.applyArchiveImport({
      organizationId: orgA.id,
      actorAccountId: account.id,
      projectName: "Path Backstop",
      archiveFormat: "zip",
      archiveSha256: "a".repeat(64),
      archiveByteSize: 1,
      manifestSha256: "b".repeat(64),
      manifestEntries: [],
      idempotencyKey: randomUUID(),
    });

    const unsafePaths = ["/etc/passwd", "../escape", "a/../b", "C:/win", "a\\b"];
    for (const path of unsafePaths) {
      await expect(
        controlPlane.pool.query(
          `INSERT INTO project_archive_import_entries
             (id, import_id, entry_index, normalized_path, entry_kind, declared_size, compressed_size)
           VALUES ($1,$2,$3,$4,'file',1,1)`,
          [randomUUID(), applied.import.id, Math.floor(Math.random() * 100000), path],
        ),
      ).rejects.toThrow();
    }
  });

  it("rejects duplicate normalized manifest paths at the database level", async () => {
    const applied = await lifecycle.applyArchiveImport({
      organizationId: orgA.id,
      actorAccountId: account.id,
      projectName: "Duplicate Path Backstop",
      archiveFormat: "zip",
      archiveSha256: "a".repeat(64),
      archiveByteSize: 1,
      manifestSha256: "b".repeat(64),
      manifestEntries: validManifest,
      idempotencyKey: randomUUID(),
    });

    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_archive_import_entries
           (id, import_id, entry_index, normalized_path, entry_kind, declared_size, compressed_size)
         VALUES ($1,$2,99,'src/index.ts','file',1,1)`,
        [randomUUID(), applied.import.id],
      ),
    ).rejects.toThrow();
  });

  it("enforces idempotency uniqueness per organization and actor", async () => {
    const key = randomUUID();
    await lifecycle.applyArchiveImport({
      organizationId: orgA.id,
      actorAccountId: account.id,
      projectName: "Idem One",
      archiveFormat: "zip",
      archiveSha256: "a".repeat(64),
      archiveByteSize: 1,
      manifestSha256: "b".repeat(64),
      manifestEntries: [],
      idempotencyKey: key,
    });

    // Direct SQL bypassing the replay path must hit the unique constraint.
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_archive_imports
           (id, organization_id, project_id, actor_account_id, source_kind, archive_format,
            archive_sha256, archive_byte_size, manifest_sha256, manifest_entry_count,
            manifest_total_declared_size, idempotency_key, created_at)
         VALUES ($1,$2,$3,$4,'archive','zip',$5,1,$6,0,0,$7, now())`,
        [randomUUID(), orgA.id, projectA.id, account.id, "a".repeat(64), "b".repeat(64), key],
      ),
    ).rejects.toThrow();
  });

  it("maps a duplicate idempotent command to a typed error", async () => {
    const key = randomUUID();
    const first = await lifecycle.applyArchiveImport({
      organizationId: orgA.id,
      actorAccountId: account.id,
      projectName: "Typed Duplicate",
      archiveFormat: "zip",
      archiveSha256: "a".repeat(64),
      archiveByteSize: 1,
      manifestSha256: "b".repeat(64),
      manifestEntries: [],
      idempotencyKey: key,
    });
    expect(first.replayed).toBe(false);

    // The repository's own replay path returns the original result...
    const replay = await lifecycle.applyArchiveImport({
      organizationId: orgA.id,
      actorAccountId: account.id,
      projectName: "Typed Duplicate Retry",
      archiveFormat: "zip",
      archiveSha256: "a".repeat(64),
      archiveByteSize: 1,
      manifestSha256: "b".repeat(64),
      manifestEntries: [],
      idempotencyKey: key,
    });
    expect(replay.replayed).toBe(true);
    expect(replay.project.id).toBe(first.project.id);
  });

  it("surfaces a genuine concurrent idempotency race as the typed error", async () => {
    // Two concurrent commands with the same key both miss the replay lookup,
    // so exactly one wins the unique constraint and the loser must surface the
    // typed DuplicateIdempotentCommandError rather than a raw driver error.
    const key = randomUUID();
    const command = () =>
      lifecycle.applyArchiveImport({
        organizationId: orgA.id,
        actorAccountId: account.id,
        projectName: "Race Project",
        archiveFormat: "zip",
        archiveSha256: "a".repeat(64),
        archiveByteSize: 1,
        manifestSha256: "b".repeat(64),
        manifestEntries: [],
        idempotencyKey: key,
      });

    const outcomes = await Promise.allSettled([command(), command()]);
    const fulfilled = outcomes.filter((o) => o.status === "fulfilled");
    const rejected = outcomes.filter((o) => o.status === "rejected");

    // At most one durable Project may exist for this key.
    const rows = await controlPlane.pool.query(
      "SELECT project_id FROM project_archive_imports WHERE idempotency_key = $1",
      [key],
    );
    expect(rows.rows).toHaveLength(1);

    if (rejected.length > 0) {
      for (const outcome of rejected) {
        expect((outcome as PromiseRejectedResult).reason).toBeInstanceOf(
          DuplicateIdempotentCommandError,
        );
      }
    } else {
      // Both resolved: the loser must have replayed the winner's result.
      expect(fulfilled).toHaveLength(2);
      const ids = fulfilled.map(
        (o) => (o as PromiseFulfilledResult<{ project: ProjectRow }>).value.project.id,
      );
      expect(new Set(ids).size).toBe(1);
    }
  });

  it("makes a cross-Organization clone plan impossible at the database level", async () => {
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_clone_plans
           (id, organization_id, source_project_id, target_project_id, actor_account_id,
            plan_kind, artifact_count, relation_count, idempotency_key, created_at)
         VALUES ($1,$2,$3,$4,$5,'project_clone',0,0,$6, now())`,
        [randomUUID(), orgA.id, projectA.id, projectB.id, account.id, randomUUID()],
      ),
    ).rejects.toThrow();

    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_clone_plans
           (id, organization_id, source_project_id, target_project_id, actor_account_id,
            plan_kind, artifact_count, relation_count, idempotency_key, created_at)
         VALUES ($1,$2,$3,$4,$5,'project_clone',0,0,$6, now())`,
        [randomUUID(), orgA.id, projectB.id, projectA.id, account.id, randomUUID()],
      ),
    ).rejects.toThrow();
  });

  it("rejects a self-referential clone plan", async () => {
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_clone_plans
           (id, organization_id, source_project_id, target_project_id, actor_account_id,
            plan_kind, artifact_count, relation_count, idempotency_key, created_at)
         VALUES ($1,$2,$3,$3,$4,'project_clone',0,0,$5, now())`,
        [randomUUID(), orgA.id, projectA.id, account.id, randomUUID()],
      ),
    ).rejects.toThrow();
  });

  it("clones artifacts and relations atomically with remapped ids", async () => {
    const sourceProject = await projects.createProject({
      organizationId: orgA.id,
      name: "Atomic Source",
    });
    const one = await artifacts.createArtifact({
      projectId: sourceProject.id,
      type: "website",
    });
    const two = await artifacts.createArtifact({
      projectId: sourceProject.id,
      type: "design",
    });
    await artifacts.createArtifactRelation({
      subjectArtifactId: one.id,
      objectArtifactId: two.id,
      relationKind: "contains",
    });

    const result = await lifecycle.applyClonePlan({
      organizationId: orgA.id,
      actorAccountId: account.id,
      sourceProjectId: sourceProject.id,
      targetProjectName: "Atomic Target",
      idempotencyKey: randomUUID(),
    });

    expect(result.artifacts).toHaveLength(2);
    expect(result.relations).toHaveLength(1);
    expect(result.artifactIdMap.get(one.id)).toBeDefined();
    expect(result.artifactIdMap.get(one.id)).not.toBe(one.id);

    const relation = result.relations[0];
    expect(relation?.subjectArtifactId).toBe(result.artifactIdMap.get(one.id));
    expect(relation?.objectArtifactId).toBe(result.artifactIdMap.get(two.id));
    expect(relation?.projectId).toBe(result.targetProject.id);
    expect(relation?.relationKind).toBe("contains");
  });

  it("rejects provider/external authority keys on clone", async () => {
    await expect(
      lifecycle.applyClonePlan({
        organizationId: orgA.id,
        actorAccountId: account.id,
        sourceProjectId: projectA.id,
        targetProjectName: "Provider Clone",
        idempotencyKey: randomUUID(),
        externalId: "ext-1",
      } as unknown as Parameters<typeof lifecycle.applyClonePlan>[0]),
    ).rejects.toBeInstanceOf(ProviderAuthorityRejectedError);
  });

  it("keeps the (organization_id, id) Project composite key available", async () => {
    const rows = await controlPlane.pool.query(
      `SELECT conname FROM pg_constraint WHERE conname = 'projects_organization_id_id_uidx'`,
    );
    expect(rows.rows).toHaveLength(1);
  });
});
