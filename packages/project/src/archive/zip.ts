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
 *   is not reachable) and STRICTLY reconciles every local file header against
 *   its central-directory record before the entry is accepted.
 *
 * ZIP AMBIGUITY IS A SECURITY BOUNDARY. The container format stores entry
 * metadata twice, and nothing in the format forces the two copies to agree. A
 * hostile archive can therefore present a safe filename in the central
 * directory and a traversal-shaped filename in the local header, so a scanner
 * that trusts only one copy blesses bytes that a later consumer interprets
 * differently. This reader resolves that by requiring the two copies to agree
 * exactly — on raw filename BYTES (not normalized strings), compression
 * method, the semantically relevant general-purpose flag bits, CRC-32 and both
 * sizes — and by verifying the CRC-32 of the bytes it actually obtained. Any
 * disagreement is a rejection, never a repair or a preference for one copy.
 */

import { crc32 as computeCrc32, inflateRawSync } from "node:zlib";

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

/** General-purpose bit 0: the entry is encrypted. */
const FLAG_ENCRYPTED = 0x0001;
/**
 * General-purpose bit 3: sizes/CRC are zero in the local header and carried in
 * a trailing data descriptor instead.
 */
const FLAG_DATA_DESCRIPTOR = 0x0008;
/**
 * The general-purpose flag bits M-014 treats as semantically significant, i.e.
 * bits that change how the entry must be read or trusted:
 *   bit 0  encryption
 *   bit 3  data descriptor / streaming sizes
 *   bit 6  strong encryption
 *   bit 11 UTF-8 (EFS) filename encoding
 *   bit 13 masked local header values (central directory encryption)
 *
 * Bits 1-2 are compression tuning hints that legitimately differ between
 * writers and carry no security meaning, so they are excluded rather than
 * causing false rejections of well-formed archives.
 */
const SIGNIFICANT_FLAG_MASK = 0x0001 | 0x0008 | 0x0040 | 0x0800 | 0x2000;

/** POSIX file-type mask and the types we accept/reject. */
const S_IFMT = 0o170000;
const S_IFREG = 0o100000;
const S_IFDIR = 0o040000;
const S_IFLNK = 0o120000;

/** `version made by` high byte 3 == UNIX, which is when the mode bits apply. */
const MADE_BY_UNIX = 3;

export interface RawZipEntry {
  readonly rawPath: string;
  /**
   * The exact filename bytes from the central directory.
   *
   * Reconciliation compares these RAW BYTES against the local header rather
   * than comparing decoded/normalized strings, so no encoding round-trip or
   * normalization step can make two different names look equal.
   */
  readonly rawPathBytes: Buffer;
  /** General-purpose flags declared by the central directory. */
  readonly flags: number;
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
    if ((flags & FLAG_ENCRYPTED) !== 0) {
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
      // Copy: the entry outlives this loop and must not alias the archive.
      rawPathBytes: Buffer.from(nameBytes),
      flags,
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
 * Strictly reconcile an entry's local file header against its
 * central-directory record and return where the entry's data begins.
 *
 * The ZIP format stores this metadata twice and does not require the copies to
 * agree. Accepting an entry while the two copies disagree is exactly the
 * ambiguity that lets a hostile archive show a safe name to one reader and a
 * traversal-shaped name to another, so every disagreement below is a hard
 * rejection. Nothing here prefers one copy over the other or repairs a
 * mismatch.
 */
function reconcileLocalHeader(
  buffer: Buffer,
  entry: RawZipEntry,
): { dataStart: number } {
  const offset = entry.localHeaderOffset;
  requireRange(buffer, offset, LOCAL_HEADER_MIN_SIZE, "local file header");
  if (buffer.readUInt32LE(offset) !== LOCAL_HEADER_SIGNATURE) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP local file header has a bad signature",
      entry.rawPath,
    );
  }

  const localFlags = buffer.readUInt16LE(offset + 6);
  const localMethod = buffer.readUInt16LE(offset + 8);
  const localCrc = buffer.readUInt32LE(offset + 14);
  const localCompressedSize = buffer.readUInt32LE(offset + 18);
  const localDeclaredSize = buffer.readUInt32LE(offset + 22);
  const nameLength = buffer.readUInt16LE(offset + 26);
  const extraLength = buffer.readUInt16LE(offset + 28);

  // --- filename: compare RAW BYTES, never normalized strings ---------------
  const nameStart = offset + LOCAL_HEADER_MIN_SIZE;
  requireRange(buffer, nameStart, nameLength, "local file header name");
  const localNameBytes = buffer.subarray(nameStart, nameStart + nameLength);
  if (!localNameBytes.equals(entry.rawPathBytes)) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP local file header name does not match the central directory name; " +
        "the archive is ambiguous and cannot be structurally validated",
      entry.rawPath,
    );
  }

  // --- compression method --------------------------------------------------
  if (localMethod !== entry.compressionMethod) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      `ZIP local file header compression method ${localMethod} does not match ` +
        `central directory method ${entry.compressionMethod}`,
      entry.rawPath,
    );
  }

  // --- semantically significant general-purpose flags ----------------------
  const localSignificant = localFlags & SIGNIFICANT_FLAG_MASK;
  const centralSignificant = entry.flags & SIGNIFICANT_FLAG_MASK;
  if (localSignificant !== centralSignificant) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP local file header general-purpose flags do not match the central directory",
      entry.rawPath,
    );
  }
  if ((localFlags & FLAG_ENCRYPTED) !== 0) {
    throw new ArchiveRejectedError(
      "unsupported_format",
      "encrypted ZIP entries cannot be structurally verified",
      entry.rawPath,
    );
  }

  // --- data descriptor (streaming) form ------------------------------------
  //
  // With flag bit 3 the local header legitimately carries zeros and the real
  // CRC/sizes trail the data. Locating that descriptor requires scanning for a
  // signature that may also occur inside compressed data, which is itself an
  // ambiguity. M-014 therefore does not guess: it rejects the streaming form
  // explicitly instead of silently accepting zeroed local values while
  // trusting the central directory.
  if ((entry.flags & FLAG_DATA_DESCRIPTOR) !== 0) {
    throw new ArchiveRejectedError(
      "unsupported_format",
      "ZIP entries using a streaming data descriptor (general-purpose bit 3) are " +
        "not accepted: their local header sizes/CRC are unauthoritative, so the " +
        "entry cannot be unambiguously validated",
      entry.rawPath,
    );
  }

  // Without bit 3 the local values are authoritative and MUST agree. Zeros are
  // not a permitted "unknown" here — that is precisely the ambiguous shape the
  // reconciliation exists to reject.
  if (localCrc !== entry.crc32) {
    throw new ArchiveRejectedError(
      "malformed_archive",
      "ZIP local file header CRC-32 does not match the central directory",
      entry.rawPath,
    );
  }
  if (localCompressedSize !== entry.compressedSize) {
    throw new ArchiveRejectedError(
      "content_size_mismatch",
      `ZIP local file header compressed size ${localCompressedSize} does not match ` +
        `central directory size ${entry.compressedSize}`,
      entry.rawPath,
    );
  }
  if (localDeclaredSize !== entry.declaredSize) {
    throw new ArchiveRejectedError(
      "content_size_mismatch",
      `ZIP local file header uncompressed size ${localDeclaredSize} does not match ` +
        `central directory size ${entry.declaredSize}`,
      entry.rawPath,
    );
  }

  return { dataStart: nameStart + nameLength + extraLength };
}

/**
 * Decompress one entry's bytes with a hard output ceiling, after proving the
 * local and central metadata agree, and verify the result's CRC-32.
 *
 * `maxOutputLength` makes zlib abort a decompression bomb instead of
 * allocating the attacker's chosen size, so the ceiling is enforced by the
 * decompressor itself rather than checked after the damage is done. No buffer
 * is ever allocated from a declared size before that ceiling applies.
 */
export function readZipEntryContent(
  buffer: Buffer,
  entry: RawZipEntry,
  limits: ArchiveScanLimits,
): Buffer {
  const { dataStart } = reconcileLocalHeader(buffer, entry);
  requireRange(buffer, dataStart, entry.compressedSize, "entry data");

  const compressed = buffer.subarray(dataStart, dataStart + entry.compressedSize);

  const content = ((): Buffer => {
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
  })();

  // Verify the bytes we actually obtained against the authoritative ZIP CRC.
  // This supplements — and never replaces — the SHA-256 manifest hash: the CRC
  // proves the container's own integrity claim, the SHA-256 is VibeFlow's
  // server-derived content identity.
  const actualCrc = computeCrc32(content) >>> 0;
  if (actualCrc !== entry.crc32) {
    throw new ArchiveRejectedError(
      "content_checksum_mismatch",
      "ZIP entry content CRC-32 does not match the value recorded in the archive",
      entry.rawPath,
    );
  }

  return content;
}
