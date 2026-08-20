/**
 * M-014 private content-addressed archive staging port.
 *
 * SCOPE WARNING: this is the smallest possible infrastructure port needed to
 * keep archive bytes OUT of canonical Project/Artifact metadata rows. It is
 * deliberately NOT:
 * - a canonical `ObjectStorageBinding` (that resource belongs to the deferred
 *   provider-binding missions, M-016+),
 * - a provider integration or credential surface,
 * - an Artifact content/version store,
 * - a public package export beyond the port type and the in-memory adapter
 *   used by tests.
 *
 * It advances no storage/provider capability and confers no provider
 * authority. A staged reference is opaque VibeFlow-internal state: it can
 * never establish Organization/Project ownership.
 */

import { createHash } from "node:crypto";

/**
 * An opaque, content-addressed staging reference. The value is derived
 * server-side from the content digest; a caller cannot choose it.
 */
export type StagedArchiveRef = string;

export interface ArchiveStagingPort {
  /**
   * Stage archive bytes under their content address and return the opaque
   * reference. Staging the same bytes twice is idempotent.
   */
  put(bytes: Buffer): Promise<StagedArchiveRef>;
  /** Read staged bytes back, or `undefined` when the ref is unknown. */
  get(ref: StagedArchiveRef): Promise<Buffer | undefined>;
  /** Remove staged bytes. Removing an unknown ref is a no-op. */
  delete(ref: StagedArchiveRef): Promise<void>;
}

/** Build the opaque content-addressed reference for some bytes. */
export function stagedArchiveRefFor(bytes: Buffer): StagedArchiveRef {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

/**
 * In-memory staging adapter.
 *
 * Sufficient for tests and for a single-process control plane; a durable
 * object-store adapter is a later infrastructure concern and does NOT belong
 * to the canonical resource model.
 */
export class InMemoryArchiveStaging implements ArchiveStagingPort {
  private readonly blobs = new Map<StagedArchiveRef, Buffer>();

  public async put(bytes: Buffer): Promise<StagedArchiveRef> {
    const ref = stagedArchiveRefFor(bytes);
    if (!this.blobs.has(ref)) {
      this.blobs.set(ref, Buffer.from(bytes));
    }
    return ref;
  }

  public async get(ref: StagedArchiveRef): Promise<Buffer | undefined> {
    const stored = this.blobs.get(ref);
    return stored === undefined ? undefined : Buffer.from(stored);
  }

  public async delete(ref: StagedArchiveRef): Promise<void> {
    this.blobs.delete(ref);
  }

  /** Test/diagnostic helper: how many distinct blobs are currently staged. */
  public get size(): number {
    return this.blobs.size;
  }
}
