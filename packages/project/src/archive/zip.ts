/**
 * M-014 minimal, bounded ZIP structural reader.
 *
 * Deliberately hand-rolled against the PKZIP APPNOTE container format rather
 * than pulling a new extraction dependency: M-014 never extracts to a
 * filesystem, so it needs a parser that reads structure and rejects, not an
 * extractor. Every read is bounds-checked against the supplied buffer and
 * every allocation is bounded by the caller's `ArchiveScanLimits`.
 *
 * The archive bytes are HOSTILE input. This reader:
 * - never writes to disk,
 * - never executes archive content,
 * - never trusts a declared size before it is enforced,
 * - treats the central directory as the entry list (a local-header-only entry
 *   is not reachable) and cross-checks each local header.
 */

import { inflateRawSync } from "node:zlib";

import { ArchiveRejectedError } from "./errors.js";
import type { ArchiveScanLimits } from "./limits.js";

const EOCD_SIGNATURE = 0x0605_4b50;
const EOCD64_LOCATOR_SIGNATURE = 0x0706_4b50;
const CENTRAL_HEADER_SIGNATURE = 0x0201_4b50;
const LOCAL_HEADER_SIGNATURE = 0x0403_4b50;

const EOCD_MIN_SIZE = 22;
const CENTRAL_HEADER_MIN_SIZE = 46;
const LOCAL_HEADER_MIN_SIZE = 30;

const METHOD_STORE = 0;
const METHOD_DEFLATE = 8;

/** POSIX file-type mask and the types we accept/reject. */
const S_IFMT = 0o170000;
const S_IFREG = 0o100000;
const S_IFDIR = 0o040000;
const S_IFLNK = 0o120000;

/** `version made by` high byte 3 == UNIX, which is when the mode bits apply. */
const MADE_BY_UNIX = 3;

export interface RawZipEntry {
  readonly rawPath: string;
  /** Uncompressed size declared by the central directory. */
  readonly declaredSize: number;
  readonly compressedSize: number;
  readonly compressionMethod: number;
  readonly crc32: number;
  /** True when the entry's POSIX mode marks it a symlink. */
  readonly isSymlink: boolean;
  /** True when the entry's POSIX mode marks it a device/FIFO/socket. */
  readonly isSpecial: boolean;
  /** True when the entry is a directory (by mode or trailing separator). */
  readonly isDirectory: boolean;
  /** Offset of the local file header. */
  readonly localHeaderOffset: number;
}

function requireRange(
  buffer: Buffer,
  offset: number,
  length: number,
  what: string,
): void {
  if (offset < 0 || length < 0 || offset + length > buffer.length) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      `ZIP ${what} extends past the end of the archive`,
    );
  }
}

/** Locate the End Of Central Directory record, scanning back over the comment. */
function findEndOfCentralDirectory(buffer: Buffer): number {
  if (buffer.length < EOCD_MIN_SIZE) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP archive is smaller than an end-of-central-directory record",
    );
  }
  // The ZIP comment is at most 0xFFFF bytes, so the EOCD starts no earlier.
  const earliest = Math.max(0, buffer.length - EOCD_MIN_SIZE - 0xffff);
  for (let offset = buffer.length - EOCD_MIN_SIZE; offset >= earliest; offset -= 1) {
    if (buffer.readUInt32LE(offset) === EOCD_SIGNATURE) {
      return offset;
    }
  }
  throw new ArchiveRejectedError(
    "malformed_archive",
    "ZIP archive has no end-of-central-directory record",
  );
}

/**
 * Read the ZIP central directory into raw entries, enforcing count/size limits
 * as it goes so a hostile header cannot drive unbounded work.
 */
export function readZipEntries(
  buffer: Buffer,
  limits: ArchiveScanLimits,
): RawZipEntry[] {
  const eocd = findEndOfCentralDirectory(buffer);

  // ZIP64 is not accepted: the sizes it exists to express are far beyond the
  // M-014 safety limits, so supporting it would only add parser attack surface.
  if (
    eocd >= 20 &&
    buffer.readUInt32LE(eocd - 20) === EOCD64_LOCATOR_SIGNATURE
  ) {
    throw new ArchiveRejectedError(
      "unsupported_format",
      "ZIP64 archives are not accepted by the M-014 archive scanner",
    );
  }

  const entryCount = buffer.readUInt16LE(eocd + 10);
  const directorySize = buffer.readUInt32LE(eocd + 12);
  const directoryOffset = buffer.readUInt32LE(eocd + 16);

  if (entryCount > limits.maxEntryCount) {
    throw new ArchiveRejectedError(
      "too_many_entries",
      `ZIP archive declares ${entryCount} entries, exceeding the limit of ${limits.maxEntryCount}`,
    );
  }
  requireRange(buffer, directoryOffset, directorySize, "central directory");

  const entries: RawZipEntry[] = [];
  let cursor = directoryOffset;

  for (let index = 0; index < entryCount; index += 1) {
    requireRange(buffer, cursor, CENTRAL_HEADER_MIN_SIZE, "central directory header");
    if (buffer.readUInt32LE(cursor) !== CENTRAL_HEADER_SIGNATURE) {
      throw new ArchiveRejectedError(
        "malformed_archive",
        "ZIP central directory header has a bad signature",
      );
    }

    const versionMadeByHost = buffer.readUInt8(cursor + 5);
    const flags = buffer.readUInt16LE(cursor + 8);
    const compressionMethod = buffer.readUInt16LE(cursor + 10);
    const crc32 = buffer.readUInt32LE(cursor + 16);
    const compressedSize = buffer.readUInt32LE(cursor + 20);
    const declaredSize = buffer.readUInt32LE(cursor + 24);
    const nameLength = buffer.readUInt16LE(cursor + 28);
    const extraLength = buffer.readUInt16LE(cursor + 30);
    const commentLength = buffer.readUInt16LE(cursor + 32);
    const externalAttributes = buffer.readUInt32LE(cursor + 38);
    const localHeaderOffset = buffer.readUInt32LE(cursor + 42);

    // Encrypted entries cannot be structurally inspected, so they cannot be
    // proven safe and are rejected rather than imported unverified.
    if ((flags & 0x0001) !== 0) {
      throw new ArchiveRejectedError(
        "unsupported_format",
        "encrypted ZIP entries cannot be structurally verified",
      );
    }

    const nameStart = cursor + CENTRAL_HEADER_MIN_SIZE;
    requireRange(buffer, nameStart, nameLength, "central directory file name");
    // Decode strictly: a name that is not valid UTF-8 round-trips differently
    // and would create a normalized path we cannot faithfully reproduce.
    const nameBytes = buffer.subarray(nameStart, nameStart + nameLength);
    const rawPath = nameBytes.toString("utf8");
    if (!Buffer.from(rawPath, "utf8").equals(nameBytes)) {
      throw new ArchiveRejectedError(
        "path_invalid_characters",
        "ZIP entry name is not valid UTF-8",
      );
    }

    const unixMode =
      versionMadeByHost === MADE_BY_UNIX ? (externalAttributes >>> 16) & 0xffff : 0;
    const fileType = unixMode & S_IFMT;
    const isSymlink = fileType === S_IFLNK;
    const isSpecial =
      unixMode !== 0 &&
      fileType !== 0 &&
      fileType !== S_IFREG &&
      fileType !== S_IFDIR &&
      fileType !== S_IFLNK;
    const isDirectory = fileType === S_IFDIR || rawPath.endsWith("/");

    entries.push({
      rawPath,
      declaredSize,
      compressedSize,
      compressionMethod,
      crc32,
      isSymlink,
      isSpecial,
      isDirectory,
      localHeaderOffset,
    });

    cursor = nameStart + nameLength + extraLength + commentLength;
  }

  return entries;
}

/**
 * Decompress one entry's bytes with a hard output ceiling.
 *
 * `maxOutputLength` makes zlib abort a decompression bomb instead of
 * allocating the attacker's chosen size, so the ceiling is enforced by the
 * decompressor itself rather than checked after the damage is done.
 */
export function readZipEntryContent(
  buffer: Buffer,
  entry: RawZipEntry,
  limits: ArchiveScanLimits,
): Buffer {
  const offset = entry.localHeaderOffset;
  requireRange(buffer, offset, LOCAL_HEADER_MIN_SIZE, "local file header");
  if (buffer.readUInt32LE(offset) !== LOCAL_HEADER_SIGNATURE) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP local file header has a bad signature",
      entry.rawPath,
    );
  }

  const nameLength = buffer.readUInt16LE(offset + 26);
  const extraLength = buffer.readUInt16LE(offset + 28);
  const dataStart = offset + LOCAL_HEADER_MIN_SIZE + nameLength + extraLength;
  requireRange(buffer, dataStart, entry.compressedSize, "entry data");

  const compressed = buffer.subarray(dataStart, dataStart + entry.compressedSize);

  if (entry.compressionMethod === METHOD_STORE) {
    if (entry.compressedSize !== entry.declaredSize) {
      throw new ArchiveRejectedError(
        "content_size_mismatch",
        "stored ZIP entry compressed and uncompressed sizes disagree",
        entry.rawPath,
      );
    }
    return Buffer.from(compressed);
  }

  if (entry.compressionMethod !== METHOD_DEFLATE) {
    throw new ArchiveRejectedError(
      "unsupported_compression_method",
      `ZIP compression method ${entry.compressionMethod} is not accepted`,
      entry.rawPath,
    );
  }

  try {
    return inflateRawSync(compressed, { maxOutputLength: limits.maxEntryBytes });
  } catch (error) {
    const message = error instanceof Error ? error.message : "inflate failed";
    if (/maxOutputLength|buffer.*larger|output length/i.test(message)) {
      throw new ArchiveRejectedError(
        "entry_too_large",
        `ZIP entry expands beyond the per-entry limit of ${limits.maxEntryBytes} bytes`,
        entry.rawPath,
      );
    }
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP entry could not be decompressed",
      entry.rawPath,
    );
  }
}
