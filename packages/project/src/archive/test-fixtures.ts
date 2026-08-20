/**
 * M-014 archive test fixtures.
 *
 * Builds ZIP and tar containers byte-by-byte so tests can construct precisely
 * the hostile shapes a real attacker would send — absolute paths, `..`
 * traversal, Windows drive prefixes, symlink/hardlink/device entries,
 * duplicate normalized paths, lying size headers, and compression bombs —
 * without depending on a fixture archive checked into the repository.
 *
 * Test-support only. Not exported from the package root.
 */

import { crc32 as nodeCrc32 } from "node:zlib";
import { deflateRawSync } from "node:zlib";

// ---------------------------------------------------------------------------
// ZIP
// ---------------------------------------------------------------------------

export interface ZipFixtureEntry {
  /** Raw path exactly as it should appear in the container. */
  path: string;
  /** File content. Omit for a directory entry. */
  content?: Buffer | string;
  /** Mark the entry a directory (also implied by a trailing '/'). */
  directory?: boolean;
  /** POSIX mode bits, e.g. 0o120000 for a symlink, 0o020000 for a char device. */
  unixMode?: number;
  /** Force deflate instead of store. */
  deflate?: boolean;
  /** Override the declared uncompressed size to forge a lying header. */
  forgeDeclaredSize?: number;

  // -------------------------------------------------------------------------
  // Local-vs-central divergence forgeries.
  //
  // A hostile ZIP can present one interpretation to a reader that trusts the
  // central directory and a different one to a reader that walks local
  // headers. These options build exactly those ambiguous containers so the
  // scanner's reconciliation can be proven, not assumed.
  // -------------------------------------------------------------------------

  /** Write a DIFFERENT file name in the local header than in the central directory. */
  localPath?: string;
  /** Write a different compression method in the local header. */
  localMethod?: number;
  /** Write different general-purpose flags in the local header. */
  localFlags?: number;
  /** Write different general-purpose flags in the central directory. */
  centralFlags?: number;
  /** Write a different CRC-32 in the local header. */
  localCrc?: number;
  /** Write a different compressed size in the local header. */
  localCompressedSize?: number;
  /** Write a different uncompressed size in the local header. */
  localDeclaredSize?: number;
  /**
   * Corrupt the CRC-32 recorded in BOTH headers so they agree with each other
   * but disagree with the actual bytes.
   */
  corruptCrc?: boolean;
  /**
   * Emit the streaming/data-descriptor form: general-purpose flag bit 3 set,
   * local CRC and sizes zeroed, and a trailing data descriptor record.
   */
  dataDescriptor?: boolean;
}

function crc32(buffer: Buffer): number {
  return nodeCrc32(buffer) >>> 0;
}

/** Build a ZIP container from explicit entries. */
export function buildZip(entries: readonly ZipFixtureEntry[]): Buffer {
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let offset = 0;

  for (const entry of entries) {
    const isDirectory = entry.directory === true || entry.path.endsWith("/");
    const raw =
      entry.content === undefined
        ? Buffer.alloc(0)
        : Buffer.isBuffer(entry.content)
          ? entry.content
          : Buffer.from(entry.content, "utf8");

    const useDeflate = entry.deflate === true && !isDirectory;
    const stored = useDeflate ? deflateRawSync(raw) : raw;
    const method = useDeflate ? 8 : 0;
    const declaredSize = entry.forgeDeclaredSize ?? raw.length;
    const nameBytes = Buffer.from(entry.path, "utf8");
    const localNameBytes =
      entry.localPath === undefined ? nameBytes : Buffer.from(entry.localPath, "utf8");

    // A CRC corruption is written into BOTH headers so the two agree with each
    // other and only the actual bytes disprove them.
    const recordedCrc = entry.corruptCrc === true ? (crc32(raw) ^ 0xffff_ffff) >>> 0 : crc32(raw);

    const streaming = entry.dataDescriptor === true && !isDirectory;
    const centralFlags = entry.centralFlags ?? (streaming ? 0x0008 : 0);
    const localFlags = entry.localFlags ?? centralFlags;

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4); // version needed
    local.writeUInt16LE(localFlags, 6);
    local.writeUInt16LE(entry.localMethod ?? method, 8);
    local.writeUInt16LE(0, 10); // mod time
    local.writeUInt16LE(0, 12); // mod date
    // In the streaming form the local header carries zeros and the real values
    // live in the trailing data descriptor.
    local.writeUInt32LE(entry.localCrc ?? (streaming ? 0 : recordedCrc), 14);
    local.writeUInt32LE(entry.localCompressedSize ?? (streaming ? 0 : stored.length), 18);
    local.writeUInt32LE(entry.localDeclaredSize ?? (streaming ? 0 : declaredSize), 22);
    local.writeUInt16LE(localNameBytes.length, 26);
    local.writeUInt16LE(0, 28); // extra length

    const descriptor = Buffer.alloc(streaming ? 16 : 0);
    if (streaming) {
      descriptor.writeUInt32LE(0x08074b50, 0); // optional descriptor signature
      descriptor.writeUInt32LE(recordedCrc, 4);
      descriptor.writeUInt32LE(stored.length, 8);
      descriptor.writeUInt32LE(declaredSize, 12);
    }

    const localBlock = Buffer.concat([local, localNameBytes, stored, descriptor]);
    localParts.push(localBlock);

    const externalAttributes =
      entry.unixMode === undefined
        ? isDirectory
          ? (0o040755 << 16) >>> 0
          : (0o100644 << 16) >>> 0
        : (entry.unixMode << 16) >>> 0;

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4); // version made by (low)
    central.writeUInt8(3, 5); // host = UNIX so mode bits apply
    central.writeUInt16LE(20, 6); // version needed
    central.writeUInt16LE(centralFlags, 8);
    central.writeUInt16LE(method, 10);
    central.writeUInt16LE(0, 12);
    central.writeUInt16LE(0, 14);
    central.writeUInt32LE(recordedCrc, 16);
    central.writeUInt32LE(stored.length, 20);
    central.writeUInt32LE(declaredSize, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt16LE(0, 30); // extra
    central.writeUInt16LE(0, 32); // comment
    central.writeUInt16LE(0, 34); // disk number
    central.writeUInt16LE(0, 36); // internal attrs
    central.writeUInt32LE(externalAttributes, 38);
    central.writeUInt32LE(offset, 42);

    centralParts.push(Buffer.concat([central, nameBytes]));
    offset += localBlock.length;
  }

  const localBytes = Buffer.concat(localParts);
  const centralBytes = Buffer.concat(centralParts);

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralBytes.length, 12);
  eocd.writeUInt32LE(localBytes.length, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([localBytes, centralBytes, eocd]);
}

/** A small, entirely valid ZIP with a nested directory and two files. */
export function validZipFixture(): Buffer {
  return buildZip([
    { path: "src/", directory: true },
    { path: "src/index.ts", content: "export const answer = 42;\n" },
    { path: "README.md", content: "# imported project\n" },
  ]);
}

// ---------------------------------------------------------------------------
// tar
// ---------------------------------------------------------------------------

export type TarFixtureType =
  | "file"
  | "directory"
  | "symlink"
  | "hardlink"
  | "character_device"
  | "block_device"
  | "fifo";

export interface TarFixtureEntry {
  path: string;
  content?: Buffer | string;
  type?: TarFixtureType;
  /** Override the declared size octal field to forge a lying header. */
  forgeDeclaredSize?: number;
  /** Link target for symlink/hardlink entries. */
  linkTarget?: string;
}

const TAR_TYPEFLAGS: Record<TarFixtureType, string> = {
  file: "0",
  directory: "5",
  symlink: "2",
  hardlink: "1",
  character_device: "3",
  block_device: "4",
  fifo: "6",
};

function writeOctal(buffer: Buffer, value: number, offset: number, length: number): void {
  const text = value.toString(8).padStart(length - 1, "0");
  buffer.write(text, offset, length - 1, "ascii");
  buffer.writeUInt8(0, offset + length - 1);
}

function buildTarHeader(entry: TarFixtureEntry, contentLength: number): Buffer {
  const header = Buffer.alloc(512);
  const type = entry.type ?? "file";

  header.write(entry.path, 0, 100, "utf8");
  writeOctal(header, 0o644, 100, 8); // mode
  writeOctal(header, 0, 108, 8); // uid
  writeOctal(header, 0, 116, 8); // gid
  writeOctal(header, entry.forgeDeclaredSize ?? contentLength, 124, 12);
  writeOctal(header, 0, 136, 12); // mtime
  header.write(TAR_TYPEFLAGS[type], 156, 1, "ascii");
  if (entry.linkTarget !== undefined) {
    header.write(entry.linkTarget, 157, 100, "utf8");
  }
  header.write("ustar\0", 257, 6, "ascii");
  header.write("00", 263, 2, "ascii");

  // Checksum is computed with the checksum field treated as spaces.
  header.write("        ", 148, 8, "ascii");
  let sum = 0;
  for (let i = 0; i < 512; i += 1) {
    sum += header[i] as number;
  }
  const checksum = sum.toString(8).padStart(6, "0");
  header.write(checksum, 148, 6, "ascii");
  header.writeUInt8(0, 154);
  header.writeUInt8(0x20, 155);

  return header;
}

/** Build a tar container from explicit entries. */
export function buildTar(entries: readonly TarFixtureEntry[]): Buffer {
  const parts: Buffer[] = [];

  for (const entry of entries) {
    const raw =
      entry.content === undefined
        ? Buffer.alloc(0)
        : Buffer.isBuffer(entry.content)
          ? entry.content
          : Buffer.from(entry.content, "utf8");

    parts.push(buildTarHeader(entry, raw.length));
    if (raw.length > 0) {
      const padded = Math.ceil(raw.length / 512) * 512;
      const block = Buffer.alloc(padded);
      raw.copy(block);
      parts.push(block);
    }
  }

  // Two zero blocks terminate the archive.
  parts.push(Buffer.alloc(1024));
  return Buffer.concat(parts);
}

/** A small, entirely valid tar with a directory and two files. */
export function validTarFixture(): Buffer {
  return buildTar([
    { path: "app/", type: "directory" },
    { path: "app/main.py", content: "print('hello')\n" },
    { path: "requirements.txt", content: "flask==3.0.0\n" },
  ]);
}
