# M-014 — Project Archive Import and Project Clone Plan Lifecycle

**Mission status: `REVIEW`** (never `DONE`). Machine-readable parity record:
[`IMPORT_CLONE_LIFECYCLE.json`](./IMPORT_CLONE_LIFECYCLE.json).

| Field | Value |
| --- | --- |
| Branch | `arena/01a0201f-vibeflow-greenfield` |
| Starting `main` SHA | `c46bb021eb05db3ffdef7970d78379abe0196473` |
| Mission-start commit | `6fb1fe236384fb3028ce9430c531c96618f2d6f5` |
| Implementation commit | `4b698d3` (M-014 implementation) |
| Capabilities advanced | `VF-PRJ-004` → `IMPLEMENTED`, `VF-PRJ-007` → `IMPLEMENTED` |
| Migration | `migrations/0006_project_import_clone.sql` |
| Database | PostgreSQL 18.4 (matches CI `foundation`) |

The final candidate head is whatever commit the pull request points at after the
evidence commit. This record deliberately makes no claim about its own
containing SHA; verification authority is the exact-head Actions run set.

---

## 1. Authority chain

`Account → Organization membership → canonical Project → canonical Artifact /
ArtifactRelation`.

Everything else is untrusted: archive bytes and every value derived from them,
entry paths and declared sizes, caller-supplied provider/external/repository/
workspace ids, URLs, filenames, manifests, user metadata, and a caller-asserted
destination Organization on clone. None of these ever establishes ownership or
authorization scope — scope is always derived from canonical persistence.

## 2. What M-014 deliberately did **not** invent

| Temptation | Decision |
| --- | --- |
| Canonical `Import` / `Template` / `Clone` resource | **Not added.** `CANONICAL_RESOURCE_MODEL.yaml` unchanged; lifecycle lives in project-domain internal records. |
| Public `import` / `template` authorization resource type | **Not registered.** Authorization reuses `organization`, `project`, `artifact`, `artifact_relation`. |
| `import.*` / `project.import.*` / `template.*` / `clone.*` events | **Not invented.** The catalog defines only `project.created` (EVT-001) and `project.updated` (EVT-002); M-014 uses canonical `project.created` semantics. |
| Import/Template/Clone state machine | **Not added.** `STATE_MACHINES.yaml` covers Task/Execution/Approval/Connection only. |
| New top-level package | **Not created.** `@vibeflow/project` and `@vibeflow/persistence` were extended. |

These are recorded as **canonical gaps for a future ratifying mission**, not
routed around with a parallel event or outbox system.

---

## 3. Project Archive Import (VF-PRJ-004 / R2V-083)

### 3.1 Command sequence

1. Validate request **syntax only**; reject authority-shaped fields
   (`providerId`, `externalId`, `repositoryId`, `workspaceId`, `projectId`,
   `archiveSha256`, `manifestSha256`, `actorAccountId`, `createdAt`, and their
   snake_case variants).
2. Authenticate the Account (M-009).
3. Authorize `create` on the canonical **target Organization** (M-010).
4. Idempotency replay lookup on `(organization, actor, key)` — a hit returns the
   original Project with `replayed: true` and does no new work.
5. **Structurally scan the untrusted archive** — before any workspace
   materialization and before any durable Project state.
6. Derive the server-owned manifest, digests and provenance. Caller claims are
   discarded, never merged.
7. Optionally stage raw bytes under their content address.
8. **One transaction**: canonical Project + internal import record + manifest
   entries.
9. Return the canonical Project and import result.

Server-generated: Project id, import id, timestamps, both SHA-256 digests,
manifest ordering and per-entry content hashes, and the staging reference.

The import path creates **no Artifact rows** — there is no Artifact-per-file and
no invented source-file Artifact type.

### 3.2 Structural archive scanner

The term is **structural archive scanner**. It is *not* a malware scanner and
M-014 makes no malware-detection claim.

Safety is decided from container metadata plus bounded in-memory decompression
with a hard `maxOutputLength`. **Nothing is written to a filesystem while
deciding, and imported content is never executed.**

* **ZIP** — hand-rolled central-directory reader (no new dependency). Rejects
  ZIP64, encrypted entries, non-UTF-8 names, and any method other than STORE and
  DEFLATE. Verifies decompressed length equals the declared uncompressed size.
* **tar** — hand-rolled header reader validating the header checksum, honouring
  GNU `L` long names, skipping PAX/`K` metadata, and rejecting symlink,
  hardlink, character device, block device, FIFO and unknown typeflags.
* **Paths** — `path-policy.ts` **rejects rather than repairs**. A path that would
  need sanitising is a rejected path, so normalization can never silently
  produce a different file than the archive declared.

Rejection vocabulary: `malformed_archive`, `unsupported_format`,
`unsupported_compression`, `encrypted_archive`, `path_absolute`,
`path_traversal`, `path_windows_drive`, `path_unc`, `path_backslash`,
`path_invalid_characters`, `path_too_long`, `path_too_deep`, `symlink_entry`,
`hardlink_entry`, `special_entry`, `duplicate_path`, `path_collision`,
`too_many_entries`, `entry_too_large`, `total_size_exceeded`,
`archive_too_large`, `compression_ratio_exceeded`, `content_size_mismatch`.

### 3.3 Limits — implementation constants, not master contract

> The Master Build System defines **no numeric thresholds** for archive import.
> R2V-083 proves only the capability shape ("ZIP/tar upload + scanner"). Every
> value below is a conservative **implementation safety limit** chosen by M-014
> and may be retuned by a later mission with evidence.

| Limit | Value |
| --- | --- |
| `maxArchiveBytes` | 64 MiB |
| `maxEntryCount` | 10 000 |
| `maxEntryBytes` | 32 MiB |
| `maxTotalUncompressedBytes` | 256 MiB |
| `maxPathDepth` | 32 segments |
| `maxPathLength` | 1024 bytes |
| `maxCompressionRatio` | 100:1 |
| `compressionRatioFloorBytes` | 4096 |

**Expansion-ratio design note.** The bomb check is
`totalUncompressed / max(archiveBytes, compressionRatioFloorBytes)`. Flooring the
*denominator* — rather than skipping the check for small archives — closes the
small-container/large-expansion blind spot while avoiding unstable ratios
dominated by fixed container overhead. An earlier "skip below the floor" variant
was rejected for exactly that blind spot.

### 3.4 Manifest, hashing and provenance

* Manifest version tag `vibeflow.archive.manifest.v1`.
* Per entry: normalized relative path, kind (`file`/`directory`), byte size,
  SHA-256 content hash.
* Entries are **sorted byte-wise by normalized path**, so the manifest and its
  digest are deterministic and independent of archive entry order.
* Archive fingerprint = SHA-256 over the raw bytes, computed **before** any
  interpretation of those bytes.
* Manifest digest = SHA-256 over version tag ‖ format ‖ archive hash ‖ entry
  count ‖ NUL-delimited `path|kind|size|contentHash` records.
* Organization, Project, actor and timestamps are server-controlled.

### 3.5 Blob / staging boundary

The staging port is the smallest private content-addressed `put`/`get`/`delete`
port plus an in-memory adapter for tests. It is **not** a canonical
`ObjectStorageBinding`, **not** a provider or credential surface, and **not** an
Artifact content store. References have the form `sha256:<64 hex>`, are derived
server-side, and are opaque internal state that can never establish ownership.

---

## 4. Project Clone Plan / template instantiation (VF-PRJ-007 / R2V-086)

A "template" in M-014 means exactly: **a new canonical Project created from an
authorized source Project through an explicit clone plan.** No canonical
`Template` resource, no catalog, no marketplace, no public sharing, and no
provider/Git/workspace action.

### 4.1 Fail-closed authorization ordering

This ordering exists specifically to prevent the class of authority leak fixed
during M-013:

1. Primitive syntax and idempotency validation **only**.
2. Authorize **READ of the source Project by its opaque canonical id**.
3. Only then load the canonical source Project row.
4. Derive the source **Organization from canonical persistence**.
5. Authorize **CREATE on that canonical destination Organization**.
6. Enforce the M-014 same-tenant template policy.
7. Transactional create.

A caller-provided destination Organization is only ever *compared* against the
canonical value; it is never used as the authorization scope. A cross-tenant
source probe returns the same opaque error as a non-existent id, so no existence
signal leaks before authorization.

**Mutation proof.** `clone-service.ts` was temporarily mutated to call
`getProjectById` before the READ authorization; the ordering test
(`authorizes the source Project before loading any canonical source detail`)
**failed** under the mutation and passes on the restored file. The test detects a
real authority leak rather than asserting a tautology. The file was restored from
backup and the full suite re-run green.

### 4.2 Materialization and remapping

* Target Project: **new** server-generated id and server timestamps; only
  already-accepted VibeFlow-owned metadata carries across.
* Artifacts: recreated with **new** server-generated ids inside the target,
  preserving the canonical type token.
* Relations: recreated **inside the target** by remapping subject and object
  through the old→new id map, preserving the relation kind.
* Forbidden and asserted: no reuse of a source Artifact id, no
  source→target cross-Project relation, no copying of provider/repository/
  workspace identifiers as authority.
* The source→target artifact mapping lives in `project_clone_artifact_map`,
  **not** in `ArtifactRelation`.
* M-013 integrity is untouched: `artifacts` UNIQUE `(project_id, id)` and the
  `artifact_relations` composite FKs keep cross-Project edges impossible.

### 4.3 Tenant policy

Clone is restricted to the **same canonical Organization**. No authoritative
master contract proves broader scope, so cross-Organization clone and any public
template catalog remain **deferred** — and are additionally unrepresentable at
the database level (§5).

---

## 5. Persistence — `migrations/0006_project_import_clone.sql`

Adds four **internal project-domain** tables plus one supporting index:

* `projects_organization_id_id_uidx` — UNIQUE `(organization_id, id)` on
  `projects`, enabling tenant-pinned composite foreign keys.
* `project_archive_imports` — server id, Organization FK, Project FK, actor
  Account FK, `source_kind` fixed to `'archive'`, `archive_format IN ('zip',
  'tar')`, both digests constrained to `^[0-9a-f]{64}$`, `archive_byte_size`,
  opaque `staged_blob_ref`, `idempotency_key`, server timestamps.
* `project_archive_import_entries` — `entry_index`, `normalized_path`,
  `entry_kind IN ('file','directory')`, `byte_size`, `content_sha256`.
* `project_clone_plans` — `plan_kind` fixed to `'project_clone'`, Organization
  FK, source/target Project ids, actor FK, `idempotency_key`, timestamps.
* `project_clone_artifact_map` — source→target artifact id provenance.

Database-level authority constraints:

| Constraint | Effect |
| --- | --- |
| `project_archive_imports` composite FK `(organization_id, project_id)` | An import can never point at another tenant's Project. |
| `project_archive_imports_idempotency_uidx` | One import per `(org, actor, key)`. |
| `project_archive_import_entries_path_relative` CHECK | Re-rejects absolute, `..`, backslash and drive-letter paths as a backstop behind the scanner. |
| `project_archive_import_entries_path_uidx` | Duplicate normalized paths impossible. |
| `project_clone_plans_org_source_fk` **and** `..._org_target_fk` | **Both** endpoints composite-FK'd to `projects (organization_id, id)` using the plan's single `organization_id` → a cross-Organization clone plan is unrepresentable. |
| `project_clone_plans_distinct_projects` | Self-clone rejected. |
| `project_clone_plans_idempotency_uidx`, UNIQUE `(target_project_id)` | No second clone from a replayed command. |

**No archive bytes in any row.** No `bytea`/content/payload column exists on any
M-014 table; `packages/persistence/src/lifecycle.live.test.ts` proves it by
introspecting `information_schema.columns`.

---

## 6. Transactions and idempotency

* **Import** — Project row, import record and every manifest entry commit in one
  transaction. A duplicate idempotency key returns the original Project with
  `replayed: true`; no second Project or import is created.
* **Clone** — target Project, all cloned Artifacts, all remapped relations, the
  clone plan and the artifact map commit in one transaction. A duplicate key
  replays the original plan.
* **Races** — a command that loses the unique-constraint race surfaces the typed
  `DuplicateIdempotentCommandError`, which the services resolve by re-reading the
  winner's row. Two concurrent same-key commands are executed in the live suite
  and exactly one durable row survives.
* **Rollback** — an injected mid-clone (and mid-import) failure leaves zero
  Project, Artifact, relation, plan and import rows.

---

## 7. Audit and fail-closed posture

Authorization and audit reuse only the canonical resource types `organization`,
`project`, `artifact`, `artifact_relation`; no public `import`/`template`/
`clone`/`archive` resource type is registered. Audit scope is derived
**server-side** from canonical persistence. An audit failure on an otherwise
valid privileged allow keeps the decision **fail-closed** — the M-011 behaviour
is retained and unweakened, as are all M-010..M-013 boundaries.

---

## 8. Package-root export surface

`packages/project/src/index.ts` exports intentionally and only:

* Services — `ProjectService`, `ArtifactService`, `ProjectImportService`,
  `ProjectCloneService`.
* Vocabulary — `ARTIFACT_RELATION_KINDS`, `ARCHIVE_FORMATS` (re-exported from the
  canonical persistence vocabulary, not duplicated).
* Domain errors — including `ProjectImportError`, `ProjectCloneError`,
  `ArchiveRejectedError`.
* Per-service input/result types.
* Scanner surface — `scanArchive`, `ARCHIVE_MANIFEST_VERSION`,
  `ARCHIVE_REJECTION_CODES`, `DEFAULT_ARCHIVE_SCAN_LIMITS`,
  `resolveArchiveScanLimits`.
* Staging — `ArchiveStagingPort`, `InMemoryArchiveStaging`, `stagedArchiveRefFor`.

**Excluded by design:** repositories (including `ProjectLifecycleRepository`),
Drizzle tables and row types, `ControlPlaneDatabase`, pools,
`CONTROL_PLANE_TABLES`, `applyCommittedSqlMigrations`.
`packages/project/src/exports.test.ts` asserts both the intended surface and the
negative cases.

---

## 9. Test results (PostgreSQL 18.4)

| Suite | Kind | Tests | Result |
| --- | --- | --- | --- |
| `packages/project/src/archive/scanner.test.ts` | unit, hostile input | 50 | pass |
| `packages/project/src/exports.test.ts` | unit, package surface | 10 | pass |
| `packages/project/src/import.live.test.ts` | live PG 18.4 | 30 | pass |
| `packages/project/src/clone.live.test.ts` | live PG 18.4 | 22 | pass |
| `packages/persistence/src/lifecycle.live.test.ts` | live PG 18.4, DB backstops | 16 | pass |
| `packages/project` (all) | aggregate | 142 | pass |
| `tests/contract/test_m014_import_clone.py` | contract | 43 | pass |

Negative coverage includes: malformed archives; absolute, traversal,
Windows-drive, UNC, backslash and NUL paths; symlink, hardlink and device
entries; duplicate normalized paths and file/directory collisions; entry-count,
entry-size, total-size, depth and expansion-ratio limits; declared-size lies;
forged Organization; cross-tenant target Organization; revoked membership; random
ids; authority-shaped field rejection; duplicate idempotency keys; cross-tenant
source probes; cross-Organization clone; and injected mid-command rollback.

All M-008..M-013 contract suites and M-009..M-013 live integration runners remain
wired into the root `check` script and pass unchanged. **No retained test was
weakened.**

`scripts/run-m014-import-clone-integration.py` hard-fails when `DATABASE_URL` is
absent under `CI=true`, because a skipped live suite is not verification
evidence. Outside CI it reports the skip loudly and returns 0, matching the
established M-009..M-013 runner convention — this is required because the dev
container's `postCreateCommand` runs `pnpm run check` inside an image with no
PostgreSQL service. The CI `foundation` job always supplies `DATABASE_URL`, so
the live suites are never silently skipped where they count.

> **First exact-head run set (head `c910d9a`).** `verify`, `sanitize` and
> `security-gate` passed; `foundation` failed *only* at the dev-container build
> step for exactly the reason above. The runner was aligned with the retained
> convention and a fresh exact-head run set was required — any push obsoletes
> prior CI.

---

## 10. Capability ledger delta

| VF ID | Capability | From | To |
| --- | --- | --- | --- |
| `VF-PRJ-004` | Project Archive Import | `NOT_STARTED` | `IMPLEMENTED` |
| `VF-PRJ-007` | Project Clone Plan | `NOT_STARTED` | `IMPLEMENTED` |

Nothing is claimed `VERIFIED` or `COMPLETE`. Deliberately **not** advanced:
`VF-PRJ-001/002/003/008/009/010/011/012/014/016/017`. CSV, YAML and
`CAPABILITY_CONTRACT_TRACE.csv` rows 84 and 87 are updated in parity and the
contract test enforces it.

---

## 11. Known limitations

* Staging ships only an in-memory adapter; a durable object-store adapter is
  later infrastructure work and is not a canonical resource.
* Archive limits are implementation constants, not ratified master values.
* Import creates a Project and its manifest record but performs **no workspace
  materialization** by design, so imported file content is not yet reachable as
  Artifacts.
* No import/template/clone event is emitted, because the canonical catalog
  defines none.

## 12. Deferred / non-goal scope (unchanged)

VF-PRJ-008..012; `RepositoryBinding`; `WorkspaceBinding`; provider credentials;
Git clone/fetch; GitHub/Bitbucket/Vercel/Figma APIs or MCP; workspace
provisioning; agent or model execution; cross-Organization clone and public
template catalogs.

## 13. Handoff

M-014 → **`REVIEW`**. M-015 and later remain `LOCKED`. One implementation branch,
one pull request, **not merged and not self-approved**. Required exact-head
checks: `verify`, `foundation`, `sanitize`, `security-gate` — any later push
obsoletes prior CI.
