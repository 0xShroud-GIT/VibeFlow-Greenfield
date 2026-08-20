/**
 * M-014 structural archive scanner and deterministic manifest builder.
 *
 * This is the M-014 untrusted-input seam. Archive bytes are treated as
 * hostile: they are inspected entirely IN MEMORY, before any workspace
 * materialization and before any durable canonical Project state exists, and
 * a rejected archive therefore leaves nothing behind to clean up.
 *
 * The scanner NEVER:
 * - extracts content to a filesystem or workspace,
 * - executes, evaluates, or interprets archive content,
 * - trusts a declared size, path, mode, or manifest claim,
 * - lets archive content establish Organization/Project identity.
 *
 * It is a STRUCTURAL scanner, not a malware scanner. No signature database or
 * heuristic malware engine is integrated and none is claimed.
 */

import { createHash } from "node:crypto";

import { ArchiveRejectedError } from "./errors.js";
import { DEFAULT_ARCHIVE_SCAN_LIMITS, type ArchiveScanLimits } from "./limits.js";
import { normalizeArchivePath } from "./path-policy.js";
import { readTarEntries, readTarEntryContent, type RawTarEntry } from "./tar.js";
import { readZipEntries, readZipEntryContent, type RawZipEntry } from "./zip.js";

export const ARCHIVE_MANIFEST_VERSION = "vibeflow.archive.manifest.v1";

export type ArchiveFormatToken = "zip" | "tar";

export interface ArchiveManifestEntry {
  /** Position in the deterministic (path-sorted) manifest ordering. */
  readonly entryIndex: number;
  readonly normalizedPath: string;
  readonly kind: "file" | "directory";
  readonly declaredSize: number;
  readonly compressedSize: number;
  /** SHA-256 of the entry's real bytes. Directories have no content hash. */
  readonly contentSha256?: string;
}

export interface ArchiveManifest {
  readonly manifestVersion: typeof ARCHIVE_MANIFEST_VERSION;
  readonly format: ArchiveFormatToken;
  /** SHA-256 over the exact submitted archive bytes. */
  readonly archiveSha256: string;
  readonly archiveByteSize: number;
  /** Deterministic fingerprint over the normalized manifest. */
  readonly manifestSha256: string;
  readonly entries: readonly ArchiveManifestEntry[];
  readonly entryCount: number;
  readonly totalDeclaredSize: number;
}

export interface ScanArchiveInput {
  readonly bytes: Buffer;
  readonly format: ArchiveFormatToken;
  readonly limits?: Partial<ArchiveScanLimits> | undefined;
}

function sha256Hex(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex");
}

/**
 * Compute the deterministic manifest fingerprint.
 *
 * The digest is taken over a canonical newline-delimited serialization of the
 * SORTED normalized entries plus the archive digest. Two archives whose
 * accepted logical content matches therefore produce the same manifest hash
 * regardless of the order the container happened to store entries in, while
 * any change to a path, kind, size, or content hash changes it.
 *
 * The fingerprint is server-derived. No caller/provider claim contributes to
 * it, so no caller can forge or pin it.
 */
function computeManifestSha256(
  format: ArchiveFormatToken,
  archiveSha256: string,
  entries: readonly ArchiveManifestEntry[],
): string {
  const hash = createHash("sha256");
  hash.update(`${ARCHIVE_MANIFEST_VERSION}\n`);
  hash.update(`format:${format}\n`);
  hash.update(`archive:${archiveSha256}\n`);
  hash.update(`entries:${entries.length}\n`);
  for (const entry of entries) {
    hash.update(
      `${entry.normalizedPath}\u0000${entry.kind}\u0000${entry.declaredSize}\u0000${
        entry.contentSha256 ?? ""
      }\n`,
    );
  }
  return hash.digest("hex");
}

interface NormalizedEntry {
  readonly normalizedPath: string;
  readonly kind: "file" | "directory";
  readonly declaredSize: number;
  readonly compressedSize: number;
  readonly contentSha256?: string;
}

/**
 * Scan untrusted archive bytes and derive a normalized deterministic manifest.
 *
 * Throws `ArchiveRejectedError` with a specific rejection code for any unsafe
 * or malformed archive. A throw guarantees no durable state was created,
 * because this function creates none.
 */
export function scanArchive(input: ScanArchiveInput): ArchiveManifest {
  const limits: ArchiveScanLimits = {
    ...DEFAULT_ARCHIVE_SCAN_LIMITS,
    ...(input.limits ?? {}),
  };

  const bytes = input.bytes;
  if (!Buffer.isBuffer(bytes) || bytes.length === 0) {
    throw new ArchiveRejectedError("malformed_archive", "archive is empty");
  }
  if (bytes.length > limits.maxArchiveBytes) {
    throw new ArchiveRejectedError(
      "archive_too_large",
      `archive is ${bytes.length} bytes, exceeding the limit of ${limits.maxArchiveBytes}`,
    );
  }
  if (input.format !== "zip" && input.format !== "tar") {
    throw new ArchiveRejectedError(
      "unsupported_format",
      "archive format must be 'zip' or 'tar'",
    );
  }

  // Fingerprint the exact submitted bytes before any interpretation, so the
  // archive digest describes what was actually received.
  const archiveSha256 = sha256Hex(bytes);

  const normalized =
    input.format === "zip"
      ? scanZip(bytes, limits)
      : scanTar(bytes, limits);

  // Deterministic ordering by normalized path. Byte-wise comparison keeps the
  // ordering locale-independent and therefore reproducible everywhere.
  const sorted = [...normalized].sort((a, b) =>
    a.normalizedPath < b.normalizedPath ? -1 : a.normalizedPath > b.normalizedPath ? 1 : 0,
  );

  const entries: ArchiveManifestEntry[] = sorted.map((entry, index) => ({
    entryIndex: index,
    normalizedPath: entry.normalizedPath,
    kind: entry.kind,
    declaredSize: entry.declaredSize,
    compressedSize: entry.compressedSize,
    ...(entry.contentSha256 === undefined ? {} : { contentSha256: entry.contentSha256 }),
  }));

  const totalDeclaredSize = entries.reduce((sum, entry) => sum + entry.declaredSize, 0);

  return {
    manifestVersion: ARCHIVE_MANIFEST_VERSION,
    format: input.format,
    archiveSha256,
    archiveByteSize: bytes.length,
    manifestSha256: computeManifestSha256(input.format, archiveSha256, entries),
    entries,
    entryCount: entries.length,
    totalDeclaredSize,
  };
}

/**
 * Enforce the bounded-resource limits shared by both formats.
 * Kept in one place so ZIP and tar cannot drift apart on safety.
 */
function enforceAggregateLimits(
  totalUncompressed: number,
  archiveBytes: number,
  limits: ArchiveScanLimits,
): void {
  if (totalUncompressed > limits.maxTotalUncompressedBytes) {
    throw new ArchiveRejectedError(
      "total_size_exceeded",
      `archive expands to ${totalUncompressed} bytes, exceeding the limit of ${limits.maxTotalUncompressedBytes}`,
    );
  }
  // Expansion-ratio (archive bomb) check.
  //
  // The denominator is floored rather than the check being skipped for small
  // archives. Skipping outright would leave a real blind spot: a 2 KiB
  // container that expands to 2 MiB would evade the ratio entirely. Flooring
  // keeps tiny archives from being judged on an unstable ratio dominated by
  // fixed container overhead, while still bounding their absolute expansion.
  const denominator = Math.max(archiveBytes, limits.compressionRatioFloorBytes);
  const ratio = totalUncompressed / denominator;
  if (ratio > limits.maxCompressionRatio) {
    throw new ArchiveRejectedError(
      "compression_ratio_exceeded",
      `archive expansion ratio ${ratio.toFixed(1)}:1 exceeds the limit of ${limits.maxCompressionRatio}:1`,
    );
  }
}

/** Reject duplicate normalized paths and file/directory collisions. */
function claimPath(
  seen: Map<string, "file" | "directory">,
  normalizedPath: string,
  kind: "file" | "directory",
): void {
  const existing = seen.get(normalizedPath);
  if (existing !== undefined) {
    throw new ArchiveRejectedError(
      "duplicate_path",
      `archive contains a duplicate normalized path: ${normalizedPath}`,
      normalizedPath,
    );
  }
  seen.set(normalizedPath, kind);
}

/**
 * A file may not occupy a path that another entry uses as a directory
 * component, and vice versa: that is a real extraction collision even though
 * neither path is a literal duplicate of the other.
 */
function enforceNoDirectoryFileCollisions(
  seen: Map<string, "file" | "directory">,
): void {
  const filePaths = new Set<string>();
  for (const [path, kind] of seen) {
    if (kind === "file") {
      filePaths.add(path);
    }
  }
  for (const [path] of seen) {
    const segments = path.split("/");
    // Every proper ancestor of any entry is used as a directory.
    for (let i = 1; i < segments.length; i += 1) {
      const ancestor = segments.slice(0, i).join("/");
      if (filePaths.has(ancestor)) {
        throw new ArchiveRejectedError(
          "path_collision",
          `archive entry '${path}' collides with file entry '${ancestor}' used as a directory`,
          path,
        );
      }
    }
  }
}

function scanZip(bytes: Buffer, limits: ArchiveScanLimits): NormalizedEntry[] {
  const raw: RawZipEntry[] = readZipEntries(bytes, limits);

  if (raw.length > limits.maxEntryCount) {
    throw new ArchiveRejectedError(
      "too_many_entries",
      `archive contains ${raw.length} entries, exceeding the limit of ${limits.maxEntryCount}`,
    );
  }

  const seen = new Map<string, "file" | "directory">();
  const results: NormalizedEntry[] = [];
  let totalUncompressed = 0;

  for (const entry of raw) {
    // Dangerous entry kinds are rejected before their path is even considered.
    if (entry.isSymlink) {
      throw new ArchiveRejectedError(
        "symlink_entry",
        "archive contains a symbolic link entry",
        entry.rawPath,
      );
    }
    if (entry.isSpecial) {
      throw new ArchiveRejectedError(
        "special_entry",
        "archive contains a device or special filesystem entry",
        entry.rawPath,
      );
    }

    const normalizedPath = normalizeArchivePath(entry.rawPath, limits);
    const kind: "file" | "directory" = entry.isDirectory ? "directory" : "file";

    if (kind === "directory") {
      claimPath(seen, normalizedPath, kind);
      results.push({ normalizedPath, kind, declaredSize: 0, compressedSize: 0 });
      continue;
    }

    if (entry.declaredSize > limits.maxEntryBytes) {
      throw new ArchiveRejectedError(
        "entry_too_large",
        `archive entry declares ${entry.declaredSize} bytes, exceeding the per-entry limit of ${limits.maxEntryBytes}`,
        normalizedPath,
      );
    }

    // Decompress with a hard ceiling, then verify the declared size actually
    // matches the real bytes. A lying header is an integrity failure, not a
    // rounding difference.
    const content = readZipEntryContent(bytes, entry, limits);
    if (content.length !== entry.declaredSize) {
      throw new ArchiveRejectedError(
        "content_size_mismatch",
        "archive entry content size does not match its declared size",
        normalizedPath,
      );
    }

    totalUncompressed += content.length;
    enforceAggregateLimits(totalUncompressed, bytes.length, limits);

    claimPath(seen, normalizedPath, kind);
    results.push({
      normalizedPath,
      kind,
      declaredSize: entry.declaredSize,
      compressedSize: entry.compressedSize,
      contentSha256: sha256Hex(content),
    });
  }

  enforceNoDirectoryFileCollisions(seen);
  return results;
}

function scanTar(bytes: Buffer, limits: ArchiveScanLimits): NormalizedEntry[] {
  const raw: RawTarEntry[] = readTarEntries(bytes, limits);

  const seen = new Map<string, "file" | "directory">();
  const results: NormalizedEntry[] = [];
  let totalUncompressed = 0;

  for (const entry of raw) {
    switch (entry.entryType) {
      case "symlink":
        throw new ArchiveRejectedError(
          "symlink_entry",
          "archive contains a symbolic link entry",
          entry.rawPath,
        );
      case "hardlink":
        throw new ArchiveRejectedError(
          "hardlink_entry",
          "archive contains a hard link entry",
          entry.rawPath,
        );
      case "character_device":
      case "block_device":
      case "fifo":
        throw new ArchiveRejectedError(
          "special_entry",
          "archive contains a device or special filesystem entry",
          entry.rawPath,
        );
      case "unknown":
        throw new ArchiveRejectedError(
          "special_entry",
          "archive contains an unrecognized entry type",
          entry.rawPath,
        );
      default:
        break;
    }

    const normalizedPath = normalizeArchivePath(entry.rawPath, limits);

    if (entry.entryType === "directory") {
      claimPath(seen, normalizedPath, "directory");
      results.push({
        normalizedPath,
        kind: "directory",
        declaredSize: 0,
        compressedSize: 0,
      });
      continue;
    }

    if (entry.declaredSize > limits.maxEntryBytes) {
      throw new ArchiveRejectedError(
        "entry_too_large",
        `archive entry declares ${entry.declaredSize} bytes, exceeding the per-entry limit of ${limits.maxEntryBytes}`,
        normalizedPath,
      );
    }

    const content = readTarEntryContent(bytes, entry);
    if (content.length !== entry.declaredSize) {
      throw new ArchiveRejectedError(
        "content_size_mismatch",
        "archive entry content size does not match its declared size",
        normalizedPath,
      );
    }

    totalUncompressed += content.length;
    enforceAggregateLimits(totalUncompressed, bytes.length, limits);

    claimPath(seen, normalizedPath, "file");
    results.push({
      normalizedPath,
      kind: "file",
      // tar is uncompressed: the stored size is the content size.
      declaredSize: entry.declaredSize,
      compressedSize: entry.declaredSize,
      contentSha256: sha256Hex(content),
    });
  }

  enforceNoDirectoryFileCollisions(seen);
  return results;
}
