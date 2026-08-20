/**
 * M-014 Project Archive Import live PostgreSQL 18.4 authority tests.
 *
 * Proves the VF-PRJ-004 authority contract against real PostgreSQL: tenant
 * authorization, hostile-archive rejection with NO canonical side effects,
 * server-owned identity/provenance, idempotency, and cross-tenant/IDOR
 * fail-closed behaviour.
 */

import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  ArtifactRepository,
  createControlPlanePool,
  defaultMigrationsDirectory,
  ProjectLifecycleRepository,
  ProjectRepository,
  TenantRepository,
  type AccountRow,
  type ControlPlanePool,
  type OrganizationRow,
} from "@vibeflow/persistence";
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ArchiveRejectedError } from "./archive/errors.js";
import { InMemoryArchiveStaging } from "./archive/staging.js";
import {
  buildTar,
  buildZip,
  validTarFixture,
  validZipFixture,
} from "./archive/test-fixtures.js";
import { ProjectImportService } from "./import-service.js";
import { ProjectAuthorizationError, ProjectImportError, ProjectInputError } from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-014 archive import PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-014 Project Archive Import authority", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;
  let lifecycle: ProjectLifecycleRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let staging: InMemoryArchiveStaging;
  let service: ProjectImportService;

  let alice: AccountRow;
  let bob: AccountRow;
  let revoked: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;

  /** Count canonical Projects in an organization — the side-effect probe. */
  async function projectCount(organizationId: string): Promise<number> {
    const rows = await projects.listProjectsForOrganization(organizationId);
    return rows.length;
  }

  async function importCount(organizationId: string): Promise<number> {
    const rows = await lifecycle.listArchiveImportsForOrganization(organizationId);
    return rows.length;
  }

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);
    lifecycle = new ProjectLifecycleRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);

    const membershipAuthority = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projects.getProjectById.bind(projects),
      getArtifactById: artifacts.getArtifactById.bind(artifacts),
      getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
    };

    authz = new TenantAuthorizationService(membershipAuthority, audit);
    staging = new InMemoryArchiveStaging();
    service = new ProjectImportService({ lifecycle, authz, staging });

    alice = await tenants.createAccount({ displayName: "Import Alice" });
    bob = await tenants.createAccount({ displayName: "Import Bob" });
    revoked = await tenants.createAccount({ displayName: "Import Revoked" });
    orgA = await tenants.createOrganization({ name: "Import Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Import Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  // -------------------------------------------------------------------------
  // Happy path
  // -------------------------------------------------------------------------

  it("imports a valid ZIP into a new canonical Project", async () => {
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Imported ZIP Project",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: `zip-${randomUUID()}`,
    });

    expect(result.replayed).toBe(false);
    expect(result.project.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(result.project.organizationId).toBe(orgA.id);
    expect(result.project.name).toBe("Imported ZIP Project");
    expect(result.import.sourceKind).toBe("archive");
    expect(result.import.archiveFormat).toBe("zip");
    expect(result.import.projectId).toBe(result.project.id);
    expect(result.import.actorAccountId).toBe(alice.id);
    expect(result.manifestEntries).toHaveLength(3);
  });

  it("imports a valid tar into a new canonical Project", async () => {
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Imported tar Project",
      archive: validTarFixture(),
      format: "tar",
      idempotencyKey: `tar-${randomUUID()}`,
    });

    expect(result.import.archiveFormat).toBe("tar");
    expect(result.manifestEntries.map((e) => e.normalizedPath).sort()).toEqual([
      "app",
      "app/main.py",
      "requirements.txt",
    ]);
  });

  it("derives server-owned identity, provenance and timestamps", async () => {
    const before = new Date();
    const archive = validZipFixture();
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Provenance Project",
      archive,
      format: "zip",
      idempotencyKey: `prov-${randomUUID()}`,
    });

    // Fingerprints are derived from the real bytes, server-side.
    const { createHash } = await import("node:crypto");
    expect(result.import.archiveSha256).toBe(
      createHash("sha256").update(archive).digest("hex"),
    );
    expect(result.import.archiveByteSize).toBe(archive.length);
    expect(result.import.manifestSha256).toMatch(/^[0-9a-f]{64}$/);
    expect(result.import.createdAt.getTime()).toBeGreaterThanOrEqual(before.getTime() - 1000);
    expect(result.project.createdAt).toBeInstanceOf(Date);
  });

  it("keeps archive bytes out of canonical rows and in private staging only", async () => {
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Staged Project",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: `stage-${randomUUID()}`,
    });

    // The canonical Project row carries no archive content, only a name.
    expect(Object.keys(result.project).sort()).toEqual([
      "createdAt",
      "id",
      "name",
      "organizationId",
      "updatedAt",
    ]);
    // The staged ref is an opaque content address, not a provider identifier.
    expect(result.import.stagedBlobRef).toMatch(/^sha256:[0-9a-f]{64}$/);
    const staged = await staging.get(result.import.stagedBlobRef as string);
    expect(staged).toBeDefined();
  });

  it("creates no Artifact per archive file", async () => {
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "No Artifacts Project",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: `noart-${randomUUID()}`,
    });

    // Artifact remains M-013 typed-output metadata; M-014 invents no
    // source-file Artifact type.
    const rows = await artifacts.listArtifactsForProject(result.project.id);
    expect(rows).toHaveLength(0);
  });

  // -------------------------------------------------------------------------
  // Hostile archives leave no canonical side effects
  // -------------------------------------------------------------------------

  const hostileArchives: ReadonlyArray<{
    name: string;
    bytes: () => Buffer;
    format: "zip" | "tar";
    code: string;
  }> = [
    {
      name: "malformed archive",
      bytes: () => Buffer.from("definitely not an archive"),
      format: "zip",
      code: "malformed_archive",
    },
    {
      name: "traversal path",
      bytes: () => buildZip([{ path: "../../etc/passwd", content: "x" }]),
      format: "zip",
      code: "path_traversal",
    },
    {
      name: "absolute path",
      bytes: () => buildZip([{ path: "/etc/shadow", content: "x" }]),
      format: "zip",
      code: "path_absolute",
    },
    {
      name: "Windows drive confusion",
      bytes: () => buildZip([{ path: "C:/Windows/evil.dll", content: "x" }]),
      format: "zip",
      code: "path_windows_drive",
    },
    {
      name: "UNC path confusion",
      bytes: () => buildZip([{ path: "//host/share/x", content: "x" }]),
      format: "zip",
      code: "path_unc",
    },
    {
      name: "NUL/control character path",
      bytes: () => buildZip([{ path: "a\u0000b", content: "x" }]),
      format: "zip",
      code: "path_invalid_characters",
    },
    {
      name: "symlink entry",
      bytes: () => buildTar([{ path: "l", type: "symlink", linkTarget: "/etc/passwd" }]),
      format: "tar",
      code: "symlink_entry",
    },
    {
      name: "hardlink entry",
      bytes: () => buildTar([{ path: "h", type: "hardlink", linkTarget: "/etc/passwd" }]),
      format: "tar",
      code: "hardlink_entry",
    },
    {
      name: "device/special entry",
      bytes: () => buildTar([{ path: "dev/sda", type: "block_device" }]),
      format: "tar",
      code: "special_entry",
    },
    {
      name: "duplicate normalized path",
      bytes: () =>
        buildZip([
          { path: "a/b.txt", content: "1" },
          { path: "./a/b.txt", content: "2" },
        ]),
      format: "zip",
      code: "duplicate_path",
    },
    {
      name: "extraction collision",
      bytes: () =>
        buildZip([
          { path: "cfg", content: "file" },
          { path: "cfg/x.yml", content: "dir" },
        ]),
      format: "zip",
      code: "path_collision",
    },
  ];

  for (const hostile of hostileArchives) {
    it(`rejects ${hostile.name} and creates no canonical Project`, async () => {
      const projectsBefore = await projectCount(orgA.id);
      const importsBefore = await importCount(orgA.id);

      await expect(
        service.importProjectArchive({
          accountId: alice.id,
          organizationId: orgA.id,
          projectName: `Hostile ${hostile.name}`,
          archive: hostile.bytes(),
          format: hostile.format,
          idempotencyKey: `hostile-${randomUUID()}`,
        }),
      ).rejects.toBeInstanceOf(ArchiveRejectedError);

      // The side-effect rule: a rejected import leaves NO durable state.
      expect(await projectCount(orgA.id)).toBe(projectsBefore);
      expect(await importCount(orgA.id)).toBe(importsBefore);
    });
  }

  it("rejects abusive size/count/depth/expansion archives with no side effects", async () => {
    const projectsBefore = await projectCount(orgA.id);
    const limitedService = new ProjectImportService({
      lifecycle,
      authz,
      staging,
      limits: {
        maxEntryCount: 3,
        maxEntryBytes: 512,
        maxTotalUncompressedBytes: 1024,
        maxPathDepth: 3,
        maxCompressionRatio: 20,
      },
    });

    const abusive: ReadonlyArray<{ name: string; bytes: Buffer }> = [
      {
        name: "too many entries",
        bytes: buildZip(
          Array.from({ length: 10 }, (_, i) => ({ path: `f${i}`, content: "x" })),
        ),
      },
      {
        name: "entry too large",
        bytes: buildZip([{ path: "big", content: "z".repeat(4096) }]),
      },
      {
        name: "path too deep",
        bytes: buildZip([{ path: "a/b/c/d/e/f.txt", content: "x" }]),
      },
      {
        name: "compression bomb",
        bytes: buildZip([
          { path: "bomb", content: "\u0000".repeat(200_000), deflate: true },
        ]),
      },
    ];

    for (const archive of abusive) {
      await expect(
        limitedService.importProjectArchive({
          accountId: alice.id,
          organizationId: orgA.id,
          projectName: `Abusive ${archive.name}`,
          archive: archive.bytes,
          format: "zip",
          idempotencyKey: `abusive-${randomUUID()}`,
        }),
      ).rejects.toBeInstanceOf(ArchiveRejectedError);
    }

    expect(await projectCount(orgA.id)).toBe(projectsBefore);
  });

  // -------------------------------------------------------------------------
  // Tenant authorization / IDOR
  // -------------------------------------------------------------------------

  it("denies a forged (non-existent) Organization", async () => {
    const forged = randomUUID();
    await expect(
      service.importProjectArchive({
        accountId: alice.id,
        organizationId: forged,
        projectName: "Forged Org Import",
        archive: validZipFixture(),
        format: "zip",
        idempotencyKey: `forged-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("denies importing into another tenant's Organization", async () => {
    const before = await projectCount(orgB.id);
    await expect(
      service.importProjectArchive({
        accountId: alice.id, // member of orgA only
        organizationId: orgB.id,
        projectName: "Cross Tenant Import",
        archive: validZipFixture(),
        format: "zip",
        idempotencyKey: `cross-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
    expect(await projectCount(orgB.id)).toBe(before);
  });

  it("denies an account whose membership was revoked", async () => {
    const org = await tenants.createOrganization({
      name: "Revocation Org",
      kind: "standard",
    });
    await tenants.addMembership({ organizationId: org.id, accountId: revoked.id });

    // Membership proven at decision time -> allowed.
    const allowed = await service.importProjectArchive({
      accountId: revoked.id,
      organizationId: org.id,
      projectName: "Before Revocation",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: `rev-ok-${randomUUID()}`,
    });
    expect(allowed.project.organizationId).toBe(org.id);

    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [org.id, revoked.id],
    );

    await expect(
      service.importProjectArchive({
        accountId: revoked.id,
        organizationId: org.id,
        projectName: "After Revocation",
        archive: validZipFixture(),
        format: "zip",
        idempotencyKey: `rev-no-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("fails closed for random account and organization ids", async () => {
    await expect(
      service.importProjectArchive({
        accountId: randomUUID(),
        organizationId: randomUUID(),
        projectName: "Random Ids",
        archive: validZipFixture(),
        format: "zip",
        idempotencyKey: `rand-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("rejects authority-shaped provider/client fields instead of honoring them", async () => {
    const attempts: ReadonlyArray<Record<string, unknown>> = [
      { providerId: "gh_12345" },
      { externalId: "ext-1" },
      { repositoryId: randomUUID() },
      { workspaceId: randomUUID() },
      { projectId: randomUUID() },
      { manifestSha256: "0".repeat(64) },
      { archiveSha256: "1".repeat(64) },
      { actorAccountId: bob.id },
      { createdAt: new Date(0) },
    ];

    for (const extra of attempts) {
      await expect(
        service.importProjectArchive({
          accountId: alice.id,
          organizationId: orgA.id,
          projectName: "Authority Shaped",
          archive: validZipFixture(),
          format: "zip",
          idempotencyKey: `auth-${randomUUID()}`,
          ...extra,
        } as Parameters<typeof service.importProjectArchive>[0]),
      ).rejects.toBeInstanceOf(ProjectInputError);
    }
  });

  it("cannot let archive content override canonical tenant scope", async () => {
    // An archive whose file names impersonate identifiers must not change
    // where the Project lands or what it is called.
    const hostileNames = buildZip([
      { path: `${orgB.id}/organization_id`, content: orgB.id },
      { path: "vibeflow/project_id", content: randomUUID() },
    ]);

    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Impersonating Archive",
      archive: hostileNames,
      format: "zip",
      idempotencyKey: `imp-${randomUUID()}`,
    });

    expect(result.project.organizationId).toBe(orgA.id);
    expect(result.project.name).toBe("Impersonating Archive");
  });

  // -------------------------------------------------------------------------
  // Idempotency and transactional integrity
  // -------------------------------------------------------------------------

  it("does not create a second Project for a duplicate idempotency key", async () => {
    const key = `idem-${randomUUID()}`;
    const first = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Idempotent Project",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: key,
    });
    const second = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Idempotent Project Retried",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: key,
    });

    expect(second.replayed).toBe(true);
    expect(second.project.id).toBe(first.project.id);
    expect(second.import.id).toBe(first.import.id);
    // The retry must not have renamed or duplicated anything.
    expect(second.project.name).toBe("Idempotent Project");
  });

  it("scopes idempotency keys per actor so members cannot collide or probe", async () => {
    const key = `shared-key-${randomUUID()}`;
    const carol = await tenants.createAccount({ displayName: "Import Carol" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: carol.id });

    const aliceImport = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Alice Key Project",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: key,
    });
    const carolImport = await service.importProjectArchive({
      accountId: carol.id,
      organizationId: orgA.id,
      projectName: "Carol Key Project",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: key,
    });

    expect(carolImport.replayed).toBe(false);
    expect(carolImport.project.id).not.toBe(aliceImport.project.id);
  });

  it("rolls back the whole import when the transaction fails mid-flight", async () => {
    const projectsBefore = await projectCount(orgA.id);
    const importsBefore = await importCount(orgA.id);

    await expect(
      lifecycle.applyArchiveImport({
        organizationId: orgA.id,
        actorAccountId: alice.id,
        projectName: "Rollback Project",
        archiveFormat: "zip",
        archiveSha256: "a".repeat(64),
        archiveByteSize: 100,
        manifestSha256: "b".repeat(64),
        manifestEntries: [
          {
            entryIndex: 0,
            normalizedPath: "x.txt",
            kind: "file",
            declaredSize: 1,
            compressedSize: 1,
            contentSha256: "c".repeat(64),
          },
        ],
        idempotencyKey: `rollback-${randomUUID()}`,
        failAfterProjectCreate: async () => {
          throw new Error("injected mid-import failure");
        },
      }),
    ).rejects.toThrow(/injected mid-import failure/);

    // No partial Project or manifest survives.
    expect(await projectCount(orgA.id)).toBe(projectsBefore);
    expect(await importCount(orgA.id)).toBe(importsBefore);
  });

  it("persists a deterministic manifest that matches the scanner output", async () => {
    const archive = validZipFixture();
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Manifest Project",
      archive,
      format: "zip",
      idempotencyKey: `man-${randomUUID()}`,
    });

    const entries = await service.getImportManifest({
      accountId: alice.id,
      importId: result.import.id,
    });
    const paths = [...entries]
      .sort((a, b) => a.entryIndex - b.entryIndex)
      .map((e) => e.normalizedPath);
    expect(paths).toEqual(["README.md", "src", "src/index.ts"]);
  });

  it("does not disclose another tenant's import through the manifest read", async () => {
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Private Manifest",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: `priv-${randomUUID()}`,
    });

    // Bob is a member of orgB only. An existing foreign import and a random
    // non-existent id must be indistinguishable.
    const foreign = service.getImportManifest({
      accountId: bob.id,
      importId: result.import.id,
    });
    const missing = service.getImportManifest({
      accountId: bob.id,
      importId: randomUUID(),
    });

    await expect(foreign).rejects.toBeInstanceOf(ProjectImportError);
    await expect(missing).rejects.toBeInstanceOf(ProjectImportError);
    const foreignMessage = await foreign.catch((e: Error) => e.message);
    const missingMessage = await missing.catch((e: Error) => e.message);
    expect(foreignMessage).toBe(missingMessage);
  });

  // -------------------------------------------------------------------------
  // Audit
  // -------------------------------------------------------------------------

  it("records the import authorization decision under the canonical org scope", async () => {
    const result = await service.importProjectArchive({
      accountId: alice.id,
      organizationId: orgA.id,
      projectName: "Audited Import",
      archive: validZipFixture(),
      format: "zip",
      idempotencyKey: `audit-${randomUUID()}`,
    });
    expect(result.project.organizationId).toBe(orgA.id);

    const rows = await controlPlane.pool.query(
      `SELECT organization_id, resource_type, outcome
         FROM audit_events
        WHERE actor_account_id = $1
          AND resource_type = 'organization'
          AND resource_id = $2
          AND outcome = 'allowed'
        ORDER BY occurred_at DESC
        LIMIT 1`,
      [alice.id, orgA.id],
    );
    expect(rows.rows).toHaveLength(1);
    // Tenant scope is derived server-side from the canonical organization.
    expect((rows.rows[0] as { organization_id: string }).organization_id).toBe(orgA.id);
  });

  it("fails closed when the required audit record cannot be written", async () => {
    const failingAudit = {
      async recordAuthorizationDecision(): Promise<void> {
        throw new Error("audit unavailable");
      },
    };
    const failClosedAuthz = new TenantAuthorizationService(
      {
        getOrganizationById: tenants.getOrganizationById.bind(tenants),
        getMembership: tenants.getMembership.bind(tenants),
        getProjectById: projects.getProjectById.bind(projects),
        getArtifactById: artifacts.getArtifactById.bind(artifacts),
        getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
      },
      failingAudit,
    );
    const failClosedService = new ProjectImportService({
      lifecycle,
      authz: failClosedAuthz,
      staging,
    });

    const before = await projectCount(orgA.id);
    // An otherwise-valid privileged allow must NOT proceed without its
    // required durable security record.
    await expect(
      failClosedService.importProjectArchive({
        accountId: alice.id,
        organizationId: orgA.id,
        projectName: "Audit Unavailable",
        archive: validZipFixture(),
        format: "zip",
        idempotencyKey: `auditfail-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
    expect(await projectCount(orgA.id)).toBe(before);
  });
});
