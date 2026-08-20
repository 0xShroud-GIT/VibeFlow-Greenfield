/**
 * M-014 archive path normalization policy.
 *
 * Archive entry paths are HOSTILE UNTRUSTED INPUT. They are attacker-chosen
 * strings, not filesystem facts. This module reduces a raw archive path to a
 * single canonical relative form, or rejects it. It never touches the
 * filesystem and never resolves against a real directory.
 *
 * Rejection is preferred over silent repair everywhere it could change the
 * caller's meaning: a path that "looks like" traversal after normalization is
 * rejected rather than clamped, so an attacker cannot smuggle an escape past
 * a normalizer that quietly drops segments.
 */

import { ArchiveRejectedError } from "./errors.js";
import type { ArchiveScanLimits } from "./limits.js";

/**
 * Normalize one raw archive entry path to a safe canonical relative path.
 *
 * Rejects, in order:
 * - empty paths
 * - NUL and other control characters (C0 + DEL), including embedded ones
 * - backslashes (Windows separator / UNC confusion)
 * - Windows drive-letter prefixes (`C:`, `c:/...`) and drive-relative paths
 * - UNC prefixes (`\\server\share`, `//server/share`) and extended paths
 * - absolute POSIX paths
 * - `..` traversal that survives normalization
 * - over-long and over-deep paths
 *
 * Normalizes (without changing reachability):
 * - repeated separators (`a//b` -> `a/b`)
 * - `.` segments (`./a/./b` -> `a/b`)
 * - a single trailing slash on directory entries (reported separately)
 */
export function normalizeArchivePath(
  rawPath: string,
  limits: ArchiveScanLimits,
): string {
  if (typeof rawPath !== "string" || rawPath.length === 0) {
    throw new ArchiveRejectedError("path_empty", "archive entry path is empty");
  }

  // Control characters (including NUL) are never legitimate in a path we are
  // willing to materialize; they are a classic truncation/confusion vector.
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f]/.test(rawPath)) {
    throw new ArchiveRejectedError(
      "path_invalid_characters",
      "archive entry path contains NUL or control characters",
      rawPath,
    );
  }

  // Reject backslashes outright. Treating them as separators would create a
  // second, divergent path grammar; treating them as literals would let a
  // Windows extractor reinterpret them as separators later.
  if (rawPath.includes("\\")) {
    throw new ArchiveRejectedError(
      "path_backslash",
      "archive entry path contains a backslash",
      rawPath,
    );
  }

  // UNC / extended-length confusion. `\\?\`-style prefixes are already covered
  // by the backslash rule; `//server/share` is the forward-slash variant.
  if (rawPath.startsWith("//")) {
    throw new ArchiveRejectedError(
      "path_unc",
      "archive entry path is a UNC-style path",
      rawPath,
    );
  }

  // Windows drive letters, both absolute (`C:/x`) and drive-relative (`C:x`).
  if (/^[A-Za-z]:/.test(rawPath)) {
    throw new ArchiveRejectedError(
      "path_windows_drive",
      "archive entry path contains a Windows drive designator",
      rawPath,
    );
  }

  if (rawPath.startsWith("/")) {
    throw new ArchiveRejectedError(
      "path_absolute",
      "archive entry path is absolute",
      rawPath,
    );
  }

  const segments: string[] = [];
  for (const segment of rawPath.split("/")) {
    if (segment === "" || segment === ".") {
      // Collapse repeated separators and `.` segments.
      continue;
    }
    if (segment === "..") {
      // Never resolve upward. Even a `..` that a lenient normalizer would
      // cancel out (`a/../b`) is rejected: accepting it means trusting our own
      // normalizer to agree with every downstream extractor.
      throw new ArchiveRejectedError(
        "path_traversal",
        "archive entry path contains a '..' traversal segment",
        rawPath,
      );
    }
    segments.push(segment);
  }

  if (segments.length === 0) {
    throw new ArchiveRejectedError(
      "path_empty",
      "archive entry path normalizes to an empty path",
      rawPath,
    );
  }

  if (segments.length > limits.maxPathDepth) {
    throw new ArchiveRejectedError(
      "path_too_deep",
      `archive entry path exceeds the maximum depth of ${limits.maxPathDepth}`,
      rawPath,
    );
  }

  const normalized = segments.join("/");
  if (Buffer.byteLength(normalized, "utf8") > limits.maxPathLength) {
    throw new ArchiveRejectedError(
      "path_too_long",
      `archive entry path exceeds the maximum length of ${limits.maxPathLength} bytes`,
      rawPath,
    );
  }

  return normalized;
}

/** True when the raw archive path denotes a directory entry by convention. */
export function isDirectoryPath(rawPath: string): boolean {
  return rawPath.endsWith("/");
}
