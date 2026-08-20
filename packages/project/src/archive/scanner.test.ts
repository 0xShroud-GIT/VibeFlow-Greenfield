/**
 * M-014 structural archive scanner unit tests.
 *
 * These prove the hostile-input contract WITHOUT a database: the scanner is
 * the boundary that must reject an archive before any durable state exists,
 * so its rejections are provable in isolation.
 */

import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import { ArchiveRejectedError, type ArchiveRejectionCode } from "./errors.js";
import { DEFAULT_ARCHIVE_SCAN_LIMITS } from "./limits.js";
import { scanArchive, ARCHIVE_MANIFEST_VERSION } from "./scanner.js";
import {
  buildTar,
  buildZip,
  validTarFixture,
  validZipFixture,
} from "./test-fixtures.js";

function expectRejection(
  run: () => unknown,
  code: ArchiveRejectionCode,
): ArchiveRejectedError {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  expect(caught).toBeInstanceOf(ArchiveRejectedError);
  const rejection = caught as ArchiveRejectedError;
  expect(rejection.code).toBe(code);
  return rejection;
}

describe("M-014 structural archive scanner — accepted archives", () => {
  it("accepts a valid ZIP and derives a normalized deterministic manifest", () => {
    const bytes = validZipFixture();
    const manifest = scanArchive({ bytes, format: "zip" });

    expect(manifest.manifestVersion).toBe(ARCHIVE_MANIFEST_VERSION);
    expect(manifest.format).toBe("zip");
    expect(manifest.entryCount).toBe(3);
    // Deterministic ordering is by normalized path, not container order.
    expect(manifest.entries.map((e) => e.normalizedPath)).toEqual([
      "README.md",
      "src",
      "src/index.ts",
    ]);
    expect(manifest.entries.map((e) => e.entryIndex)).toEqual([0, 1, 2]);
    expect(manifest.entries.find((e) => e.normalizedPath === "src")?.kind).toBe(
      "directory",
    );
  });

  it("accepts a valid tar and derives a normalized deterministic manifest", () => {
    const bytes = validTarFixture();
    const manifest = scanArchive({ bytes, format: "tar" });

    expect(manifest.format).toBe("tar");
    expect(manifest.entryCount).toBe(3);
    expect(manifest.entries.map((e) => e.normalizedPath)).toEqual([
      "app",
      "app/main.py",
      "requirements.txt",
    ]);
  });

  it("derives archive and per-entry SHA-256 from the real bytes", () => {
    const content = "export const answer = 42;\n";
    const bytes = validZipFixture();
    const manifest = scanArchive({ bytes, format: "zip" });

    expect(manifest.archiveSha256).toBe(
      createHash("sha256").update(bytes).digest("hex"),
    );
    expect(manifest.archiveByteSize).toBe(bytes.length);

    const entry = manifest.entries.find((e) => e.normalizedPath === "src/index.ts");
    expect(entry?.contentSha256).toBe(
      createHash("sha256").update(Buffer.from(content, "utf8")).digest("hex"),
    );
    // Directories carry no content hash.
    expect(manifest.entries.find((e) => e.normalizedPath === "src")?.contentSha256)
      .toBeUndefined();
  });

  it("produces a stable manifest fingerprint across repeated scans", () => {
    const bytes = validZipFixture();
    const first = scanArchive({ bytes, format: "zip" });
    const second = scanArchive({ bytes, format: "zip" });
    expect(first.manifestSha256).toBe(second.manifestSha256);
    expect(first.manifestSha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it("changes the manifest fingerprint when any content changes", () => {
    const original = scanArchive({ bytes: validZipFixture(), format: "zip" });
    const modified = scanArchive({
      bytes: buildZip([
        { path: "src/", directory: true },
        { path: "src/index.ts", content: "export const answer = 43;\n" },
        { path: "README.md", content: "# imported project\n" },
      ]),
      format: "zip",
    });
    expect(modified.manifestSha256).not.toBe(original.manifestSha256);
  });

  it("normalizes redundant './' and '//' segments without changing reachability", () => {
    const manifest = scanArchive({
      bytes: buildZip([{ path: "./src//deep/./file.txt", content: "x" }]),
      format: "zip",
    });
    expect(manifest.entries[0]?.normalizedPath).toBe("src/deep/file.txt");
  });

  it("normalizes a deflated entry and verifies its real inflated bytes", () => {
    const content = "y".repeat(5000);
    const manifest = scanArchive({
      bytes: buildZip([{ path: "big.txt", content, deflate: true }]),
      format: "zip",
    });
    expect(manifest.entries[0]?.declaredSize).toBe(5000);
    expect(manifest.entries[0]?.contentSha256).toBe(
      createHash("sha256").update(Buffer.from(content, "utf8")).digest("hex"),
    );
  });
});

describe("M-014 structural archive scanner — malformed containers", () => {
  it("rejects an empty archive", () => {
    expectRejection(
      () => scanArchive({ bytes: Buffer.alloc(0), format: "zip" }),
      "malformed_archive",
    );
  });

  it("rejects random bytes claiming to be a ZIP", () => {
    expectRejection(
      () => scanArchive({ bytes: Buffer.from("not a zip at all, truly"), format: "zip" }),
      "malformed_archive",
    );
  });

  it("rejects random bytes claiming to be a tar", () => {
    expectRejection(
      () => scanArchive({ bytes: Buffer.alloc(512, 0x41), format: "tar" }),
      "malformed_archive",
    );
  });

  it("rejects a truncated ZIP central directory", () => {
    const bytes = validZipFixture();
    expectRejection(
      () => scanArchive({ bytes: bytes.subarray(0, bytes.length - 30), format: "zip" }),
      "malformed_archive",
    );
  });

  it("rejects a tar whose length is not a multiple of 512", () => {
    const bytes = Buffer.concat([validTarFixture(), Buffer.from([1, 2, 3])]);
    expectRejection(() => scanArchive({ bytes, format: "tar" }), "malformed_archive");
  });

  it("rejects a tar with a corrupted header checksum", () => {
    const bytes = validTarFixture();
    bytes.write("zzz", 0, 3, "utf8"); // mutate the name, invalidating the checksum
    expectRejection(() => scanArchive({ bytes, format: "tar" }), "malformed_archive");
  });

  it("rejects an unsupported declared format", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: validZipFixture(),
          // deliberately outside the proven ZIP/tar set
          format: "rar" as unknown as "zip",
        }),
      "unsupported_format",
    );
  });
});

describe("M-014 structural archive scanner — path safety", () => {
  it("rejects an absolute POSIX path", () => {
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "/etc/passwd", content: "x" }]), format: "zip" }),
      "path_absolute",
    );
  });

  it("rejects '..' traversal", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "../../etc/passwd", content: "x" }]),
          format: "zip",
        }),
      "path_traversal",
    );
  });

  it("rejects traversal that a lenient normalizer would cancel out", () => {
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "a/../b.txt", content: "x" }]), format: "zip" }),
      "path_traversal",
    );
  });

  it("rejects traversal in a tar entry", () => {
    expectRejection(
      () => scanArchive({ bytes: buildTar([{ path: "../escape.txt", content: "x" }]), format: "tar" }),
      "path_traversal",
    );
  });

  it("rejects a Windows drive-absolute path", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "C:/Windows/system32/evil.dll", content: "x" }]),
          format: "zip",
        }),
      "path_windows_drive",
    );
  });

  it("rejects a Windows drive-relative path", () => {
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "D:evil.txt", content: "x" }]), format: "zip" }),
      "path_windows_drive",
    );
  });

  it("rejects a UNC-style path", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "//attacker/share/payload", content: "x" }]),
          format: "zip",
        }),
      "path_unc",
    );
  });

  it("rejects a backslash-separated path", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "windows\\system32\\evil.dll", content: "x" }]),
          format: "zip",
        }),
      "path_backslash",
    );
  });

  it("rejects a path containing a NUL character", () => {
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "safe.txt\u0000.exe", content: "x" }]), format: "zip" }),
      "path_invalid_characters",
    );
  });

  it("rejects a path containing control characters", () => {
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "a\u0007b.txt", content: "x" }]), format: "zip" }),
      "path_invalid_characters",
    );
  });

  it("rejects an over-deep path", () => {
    const deep = Array.from({ length: 40 }, (_, i) => `d${i}`).join("/") + "/f.txt";
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: deep, content: "x" }]), format: "zip" }),
      "path_too_deep",
    );
  });

  it("rejects an over-long path", () => {
    const long = `${"a".repeat(300)}/${"b".repeat(300)}/${"c".repeat(500)}.txt`;
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: long, content: "x" }]), format: "zip" }),
      "path_too_long",
    );
  });

  it("rejects an entry whose path normalizes to nothing", () => {
    expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "./", content: "" }]), format: "zip" }),
      "path_empty",
    );
  });
});

describe("M-014 structural archive scanner — dangerous entry kinds", () => {
  it("rejects a ZIP symlink entry", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "link", content: "/etc/passwd", unixMode: 0o120777 }]),
          format: "zip",
        }),
      "symlink_entry",
    );
  });

  it("rejects a tar symlink entry", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildTar([{ path: "link", type: "symlink", linkTarget: "/etc/passwd" }]),
          format: "tar",
        }),
      "symlink_entry",
    );
  });

  it("rejects a tar hardlink entry", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildTar([{ path: "hard", type: "hardlink", linkTarget: "/etc/shadow" }]),
          format: "tar",
        }),
      "hardlink_entry",
    );
  });

  it("rejects a tar character-device entry", () => {
    expectRejection(
      () => scanArchive({ bytes: buildTar([{ path: "dev/zero", type: "character_device" }]), format: "tar" }),
      "special_entry",
    );
  });

  it("rejects a tar block-device entry", () => {
    expectRejection(
      () => scanArchive({ bytes: buildTar([{ path: "dev/sda", type: "block_device" }]), format: "tar" }),
      "special_entry",
    );
  });

  it("rejects a tar FIFO entry", () => {
    expectRejection(
      () => scanArchive({ bytes: buildTar([{ path: "pipe", type: "fifo" }]), format: "tar" }),
      "special_entry",
    );
  });

  it("rejects a ZIP device/special entry by mode", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "dev/null", content: "", unixMode: 0o020666 }]),
          format: "zip",
        }),
      "special_entry",
    );
  });
});

describe("M-014 structural archive scanner — collisions", () => {
  it("rejects duplicate normalized paths", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([
            { path: "src/app.ts", content: "one" },
            { path: "./src/app.ts", content: "two" },
          ]),
          format: "zip",
        }),
      "duplicate_path",
    );
  });

  it("rejects a duplicate normalized path in a tar", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildTar([
            { path: "a/b.txt", content: "one" },
            { path: "./a//b.txt", content: "two" },
          ]),
          format: "tar",
        }),
      "duplicate_path",
    );
  });

  it("rejects a file/directory extraction collision", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([
            { path: "config", content: "i am a file" },
            { path: "config/db.yml", content: "i need config to be a directory" },
          ]),
          format: "zip",
        }),
      "path_collision",
    );
  });
});

describe("M-014 structural archive scanner — bounded resource use", () => {
  it("rejects an archive larger than the configured limit", () => {
    const bytes = validZipFixture();
    expectRejection(
      () => scanArchive({ bytes, format: "zip", limits: { maxArchiveBytes: 10 } }),
      "archive_too_large",
    );
  });

  it("rejects an archive with too many entries", () => {
    const entries = Array.from({ length: 12 }, (_, i) => ({
      path: `f${i}.txt`,
      content: "x",
    }));
    expectRejection(
      () => scanArchive({ bytes: buildZip(entries), format: "zip", limits: { maxEntryCount: 5 } }),
      "too_many_entries",
    );
  });

  it("rejects an individual entry larger than the configured limit", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "big.bin", content: "z".repeat(4096) }]),
          format: "zip",
          limits: { maxEntryBytes: 1024 },
        }),
      "entry_too_large",
    );
  });

  it("rejects an oversized entry in a tar", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildTar([{ path: "big.bin", content: "z".repeat(4096) }]),
          format: "tar",
          limits: { maxEntryBytes: 1024 },
        }),
      "entry_too_large",
    );
  });

  it("rejects an archive exceeding the total uncompressed limit", () => {
    const entries = Array.from({ length: 8 }, (_, i) => ({
      path: `f${i}.txt`,
      content: "q".repeat(1000),
    }));
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip(entries),
          format: "zip",
          limits: { maxEntryBytes: 4096, maxTotalUncompressedBytes: 3000 },
        }),
      "total_size_exceeded",
    );
  });

  it("rejects archive-bomb expansion ratios", () => {
    // Highly compressible content: a small container expanding enormously.
    const bomb = buildZip([
      { path: "bomb.bin", content: "\u0000".repeat(2_000_000), deflate: true },
    ]);
    expectRejection(
      () =>
        scanArchive({
          bytes: bomb,
          format: "zip",
          limits: { maxCompressionRatio: 50 },
        }),
      "compression_ratio_exceeded",
    );
  });

  it("does not penalize an ordinary small archive with a stable ratio", () => {
    // Below the ratio floor the check is skipped; absolute limits still apply.
    const manifest = scanArchive({ bytes: validZipFixture(), format: "zip" });
    expect(manifest.entryCount).toBe(3);
  });

  it("uses conservative documented defaults", () => {
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxArchiveBytes).toBe(64 * 1024 * 1024);
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxEntryCount).toBe(10_000);
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxEntryBytes).toBe(32 * 1024 * 1024);
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxTotalUncompressedBytes).toBe(256 * 1024 * 1024);
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxPathDepth).toBe(32);
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxPathLength).toBe(1024);
    expect(DEFAULT_ARCHIVE_SCAN_LIMITS.maxCompressionRatio).toBe(100);
  });
});

describe("M-014 structural archive scanner — declared-vs-actual integrity", () => {
  it("rejects a ZIP entry whose declared size lies about its content", () => {
    expectRejection(
      () =>
        scanArchive({
          bytes: buildZip([{ path: "liar.txt", content: "short", forgeDeclaredSize: 999_999 }]),
          format: "zip",
        }),
      "content_size_mismatch",
    );
  });

  it("rejects a tar entry whose declared size lies about its content", () => {
    // A tar header that under-declares its payload yields a short read.
    expectRejection(
      () =>
        scanArchive({
          bytes: buildTar([{ path: "liar.txt", content: "0123456789", forgeDeclaredSize: 4096 }]),
          format: "tar",
        }),
      "malformed_archive",
    );
  });

  it("rejects an encrypted ZIP entry it cannot structurally verify", () => {
    const bytes = validZipFixture();
    // Set the encryption bit in the first central directory header.
    const centralOffset = bytes.indexOf(Buffer.from([0x50, 0x4b, 0x01, 0x02]));
    bytes.writeUInt16LE(0x0001, centralOffset + 8);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "unsupported_format");
  });
});

describe("M-014 structural archive scanner — no side effects", () => {
  it("never mutates the caller's archive buffer", () => {
    const bytes = validZipFixture();
    const before = Buffer.from(bytes);
    scanArchive({ bytes, format: "zip" });
    expect(bytes.equals(before)).toBe(true);
  });

  it("rejections carry a specific machine-readable code and offending path", () => {
    const rejection = expectRejection(
      () => scanArchive({ bytes: buildZip([{ path: "../x", content: "y" }]), format: "zip" }),
      "path_traversal",
    );
    expect(rejection.entryPath).toBe("../x");
    expect(rejection.name).toBe("ArchiveRejectedError");
  });
});

// ---------------------------------------------------------------------------
// ZIP local-header / central-directory ambiguity (M-014 review remediation)
//
// The ZIP format stores entry metadata twice and does not require the copies
// to agree. A scanner that trusts only the central directory can therefore
// bless bytes that a later ZIP consumer reads completely differently — the
// classic case being a safe central name paired with a traversal-shaped local
// name. Every test below builds exactly that ambiguity and proves the scanner
// rejects it rather than picking a copy.
// ---------------------------------------------------------------------------

describe("M-014 structural archive scanner — ZIP local/central reconciliation", () => {
  it("rejects a safe central-directory name paired with a traversal local name", () => {
    // THE headline attack: central says "notes.txt", the local header the
    // extractor would honour says "../../etc/cron.d/pwn".
    const bytes = buildZip([
      {
        path: "notes.txt",
        localPath: "../../etc/cron.d/pwn",
        content: "harmless looking\n",
      },
    ]);
    const rejection = expectRejection(
      () => scanArchive({ bytes, format: "zip" }),
      "malformed_archive",
    );
    expect(rejection.message).toMatch(/name does not match/i);
  });

  it("rejects a safe central-directory name paired with an absolute local name", () => {
    const bytes = buildZip([
      { path: "config.json", localPath: "/etc/passwd", content: "{}\n" },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "malformed_archive");
  });

  it("rejects central and local filenames that differ without any traversal", () => {
    // No traversal at all: mere disagreement is still unresolvable ambiguity.
    const bytes = buildZip([
      { path: "a.txt", localPath: "b.txt", content: "same length names\n" },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "malformed_archive");
  });

  it("compares raw filename bytes rather than normalized strings", () => {
    // Both names normalize to the same visible text but differ in raw bytes
    // (NFC vs NFD encoding of "é"). A string-normalizing comparison would
    // wrongly treat these as equal.
    const bytes = buildZip([
      { path: "caf\u00e9.txt", localPath: "cafe\u0301.txt", content: "x\n" },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "malformed_archive");
  });

  it("rejects a compression-method mismatch between local and central headers", () => {
    const bytes = buildZip([
      { path: "data.bin", content: "compressible ".repeat(64), deflate: true, localMethod: 0 },
    ]);
    const rejection = expectRejection(
      () => scanArchive({ bytes, format: "zip" }),
      "malformed_archive",
    );
    expect(rejection.message).toMatch(/compression method/i);
  });

  it("rejects a significant general-purpose flag mismatch", () => {
    // Bit 11 (UTF-8 name encoding) is semantically significant: disagreement
    // means the two copies describe the name differently.
    const bytes = buildZip([
      { path: "flagged.txt", content: "x\n", localFlags: 0x0800, centralFlags: 0x0000 },
    ]);
    const rejection = expectRejection(
      () => scanArchive({ bytes, format: "zip" }),
      "malformed_archive",
    );
    expect(rejection.message).toMatch(/general-purpose flags/i);
  });

  it("rejects a local-header CRC that disagrees with the central directory", () => {
    const bytes = buildZip([
      { path: "crc.txt", content: "payload\n", localCrc: 0x1234_5678 },
    ]);
    const rejection = expectRejection(
      () => scanArchive({ bytes, format: "zip" }),
      "malformed_archive",
    );
    expect(rejection.message).toMatch(/CRC-32/i);
  });

  it("rejects a local-header compressed size that disagrees with the central directory", () => {
    const bytes = buildZip([
      { path: "size.txt", content: "payload\n", localCompressedSize: 999 },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "content_size_mismatch");
  });

  it("rejects a local-header uncompressed size that disagrees with the central directory", () => {
    const bytes = buildZip([
      { path: "size2.txt", content: "payload\n", localDeclaredSize: 999 },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "content_size_mismatch");
  });

  it("does not accept zeroed local-header values while trusting the central directory", () => {
    // Zeros are the ambiguous shape an attacker reaches for when bit 3 is NOT
    // set. They must not be silently treated as "unknown, trust central".
    const bytes = buildZip([
      {
        path: "zeroed.txt",
        content: "payload\n",
        localCrc: 0,
        localCompressedSize: 0,
        localDeclaredSize: 0,
      },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "malformed_archive");
  });

  it("explicitly rejects the streaming data-descriptor form rather than guessing", () => {
    // Bit 3 makes the local sizes/CRC unauthoritative and locating the trailing
    // descriptor requires scanning for a signature that can occur inside
    // compressed data. M-014 rejects instead of guessing.
    const bytes = buildZip([{ path: "streamed.txt", content: "payload\n", dataDescriptor: true }]);
    const rejection = expectRejection(
      () => scanArchive({ bytes, format: "zip" }),
      "unsupported_format",
    );
    expect(rejection.message).toMatch(/data descriptor/i);
  });
});

describe("M-014 structural archive scanner — ZIP payload CRC verification", () => {
  it("rejects a stored entry whose content CRC does not match the archive metadata", () => {
    // Both headers agree with each other and only the actual bytes disprove
    // them, so nothing but real CRC verification can catch this.
    const bytes = buildZip([{ path: "corrupt.txt", content: "payload\n", corruptCrc: true }]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "content_checksum_mismatch");
  });

  it("rejects a deflated entry whose content CRC does not match the archive metadata", () => {
    const bytes = buildZip([
      {
        path: "corrupt-deflated.txt",
        content: "compressible ".repeat(64),
        deflate: true,
        corruptCrc: true,
      },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "content_checksum_mismatch");
  });

  it("rejects an entry whose stored bytes were tampered with after the CRC was written", () => {
    // Flip a byte inside the stored payload; headers still describe the
    // original content.
    const bytes = buildZip([{ path: "tampered.txt", content: "AAAAAAAAAAAA\n" }]);
    const payloadAt = bytes.indexOf(Buffer.from("AAAAAAAAAAAA\n", "utf8"));
    expect(payloadAt).toBeGreaterThan(0);
    bytes[payloadAt] = 0x42; // 'B'
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "content_checksum_mismatch");
  });

  it("still accepts valid ZIPs, including deflated entries, after CRC verification", () => {
    const manifest = scanArchive({ bytes: validZipFixture(), format: "zip" });
    expect(manifest.entryCount).toBe(3);

    const deflated = scanArchive({
      bytes: buildZip([
        { path: "big.txt", content: "compressible ".repeat(256), deflate: true },
        { path: "small.txt", content: "stored\n" },
      ]),
      format: "zip",
    });
    expect(deflated.entryCount).toBe(2);
    // SHA-256 manifest hashing is preserved: CRC verification supplements it.
    for (const entry of deflated.entries) {
      expect(entry.contentSha256).toMatch(/^[0-9a-f]{64}$/);
    }
  });

  it("keeps the SHA-256 manifest digest stable and independent of the CRC check", () => {
    const first = scanArchive({ bytes: validZipFixture(), format: "zip" });
    const second = scanArchive({ bytes: validZipFixture(), format: "zip" });
    expect(first.manifestSha256).toBe(second.manifestSha256);
    expect(first.manifestSha256).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("M-014 structural archive scanner — limits preserved under reconciliation", () => {
  it("still enforces the per-entry decompression ceiling via the decompressor", () => {
    // A deflate bomb must still be stopped by maxOutputLength, not by a
    // post-hoc size check and not by the new CRC path.
    const limits = { ...DEFAULT_ARCHIVE_SCAN_LIMITS, maxEntryBytes: 1024 };
    const bytes = buildZip([
      { path: "bomb.txt", content: Buffer.alloc(512 * 1024, 0x41), deflate: true },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip", limits }), "entry_too_large");
  });

  it("still enforces the entry-count limit before reading any entry content", () => {
    const limits = { ...DEFAULT_ARCHIVE_SCAN_LIMITS, maxEntryCount: 2 };
    const bytes = buildZip([
      { path: "a.txt", content: "a\n" },
      { path: "b.txt", content: "b\n" },
      { path: "c.txt", content: "c\n" },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip", limits }), "too_many_entries");
  });

  it("still enforces the aggregate uncompressed-size limit", () => {
    const limits = { ...DEFAULT_ARCHIVE_SCAN_LIMITS, maxTotalUncompressedBytes: 16 };
    const bytes = buildZip([
      { path: "a.txt", content: "aaaaaaaaaa\n" },
      { path: "b.txt", content: "bbbbbbbbbb\n" },
    ]);
    expectRejection(() => scanArchive({ bytes, format: "zip", limits }), "total_size_exceeded");
  });

  it("still rejects path traversal declared consistently in both headers", () => {
    // Reconciliation must not become the ONLY path check: a consistently
    // hostile name is still a path rejection.
    const bytes = buildZip([{ path: "../escape.txt", content: "x\n" }]);
    expectRejection(() => scanArchive({ bytes, format: "zip" }), "path_traversal");
  });
});
