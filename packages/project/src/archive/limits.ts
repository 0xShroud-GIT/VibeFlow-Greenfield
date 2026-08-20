/**
 * M-014 archive intake safety limits.
 *
 * IMPORTANT PROVENANCE NOTE: the Master Build System does NOT define numeric
 * thresholds for archive import. `01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER` and
 * `99_REFERENCE/REPLIT_TO_VIBEFLOW_390_EVIDENCE_MAP.csv` (R2V-083) prove only
 * the shape of the capability — "ZIP/tar upload + scanner", "Scan archive
 * before creating workspace". Every constant below is therefore an
 * IMPLEMENTATION SAFETY LIMIT chosen conservatively by M-014, not a ratified
 * master contract value, and a later mission may retune it with evidence.
 */

export interface ArchiveScanLimits {
  /** Maximum accepted compressed archive size in bytes. */
  readonly maxArchiveBytes: number;
  /** Maximum number of entries (files + directories) in one archive. */
  readonly maxEntryCount: number;
  /** Maximum uncompressed size of a single entry in bytes. */
  readonly maxEntryBytes: number;
  /** Maximum total uncompressed size across all entries in bytes. */
  readonly maxTotalUncompressedBytes: number;
  /** Maximum number of path segments in a normalized entry path. */
  readonly maxPathDepth: number;
  /** Maximum length in bytes of one normalized entry path. */
  readonly maxPathLength: number;
  /**
   * Maximum tolerated total expansion ratio
   * (total uncompressed bytes / compressed archive bytes).
   * Guards archive-bomb behaviour.
   */
  readonly maxCompressionRatio: number;
  /**
   * Floor, in bytes, applied to the DENOMINATOR of the expansion-ratio check.
   *
   * The ratio is `totalUncompressed / max(archiveBytes, floor)`. Flooring the
   * denominator (rather than skipping the check for small archives) keeps a
   * tiny container from being judged on a ratio dominated by fixed container
   * overhead, while still bounding how far a small archive may expand — a
   * skip would leave a genuine blind spot for small high-ratio bombs.
   */
  readonly compressionRatioFloorBytes: number;
}

/**
 * Conservative M-014 defaults. These are implementation safety limits, not
 * master-defined thresholds.
 */
export const DEFAULT_ARCHIVE_SCAN_LIMITS: ArchiveScanLimits = Object.freeze({
  maxArchiveBytes: 64 * 1024 * 1024, // 64 MiB compressed
  maxEntryCount: 10_000,
  maxEntryBytes: 32 * 1024 * 1024, // 32 MiB per file
  maxTotalUncompressedBytes: 256 * 1024 * 1024, // 256 MiB expanded
  maxPathDepth: 32,
  maxPathLength: 1024,
  maxCompressionRatio: 100,
  compressionRatioFloorBytes: 4096,
});

/** Resolve caller overrides against the conservative defaults. */
export function resolveArchiveScanLimits(
  overrides?: Partial<ArchiveScanLimits>,
): ArchiveScanLimits {
  if (overrides === undefined) {
    return DEFAULT_ARCHIVE_SCAN_LIMITS;
  }
  return Object.freeze({ ...DEFAULT_ARCHIVE_SCAN_LIMITS, ...overrides });
}
