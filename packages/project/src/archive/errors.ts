/**
 * M-014 structural archive scanner rejection vocabulary.
 *
 * This is a STRUCTURAL scanner. It proves archive container integrity, path
 * safety, entry-kind safety and bounded resource use. It is explicitly NOT a
 * malware scanner: no signature database, heuristic engine, or content
 * classification is integrated, and M-014 never claims malware detection.
 */

export const ARCHIVE_REJECTION_CODES = [
  // container integrity
  "malformed_archive",
  "unsupported_format",
  "unsupported_compression_method",
  // bounded resource use
  "archive_too_large",
  "too_many_entries",
  "entry_too_large",
  "total_size_exceeded",
  "compression_ratio_exceeded",
  // path safety
  "path_empty",
  "path_absolute",
  "path_traversal",
  "path_windows_drive",
  "path_unc",
  "path_backslash",
  "path_invalid_characters",
  "path_too_long",
  "path_too_deep",
  "duplicate_path",
  "path_collision",
  // entry-kind safety
  "symlink_entry",
  "hardlink_entry",
  "special_entry",
  // declared-vs-actual integrity
  "content_size_mismatch",
  "content_checksum_mismatch",
] as const;

export type ArchiveRejectionCode = (typeof ARCHIVE_REJECTION_CODES)[number];

/**
 * A hostile or malformed archive was rejected before any workspace
 * materialization and before any durable canonical Project state was created.
 */
export class ArchiveRejectedError extends Error {
  override readonly name = "ArchiveRejectedError";

  public constructor(
    public readonly code: ArchiveRejectionCode,
    message: string,
    /** Offending normalized/raw entry path when the rejection is entry-scoped. */
    public readonly entryPath?: string,
  ) {
    super(message);
  }
}
