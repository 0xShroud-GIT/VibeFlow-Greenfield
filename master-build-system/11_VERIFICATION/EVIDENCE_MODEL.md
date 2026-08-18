# Evidence Model

An Evidence item records type, source, project/task/execution/release references, candidate revision, producer/tool/provider, timestamp, content hash, storage reference, redaction class and optional signature/attestation.

Examples: command result, build log summary, test report, diff hash, implementation-reference validation, dependency scan, screenshot, preview health response, deployment receipt, provider reconciliation result.

For implementation-reference validation, evidence may record the owning technology, exact project version, authoritative source reference, applicability decision and validation result.

Evidence is append-only. Large payloads live by content hash in object storage; PostgreSQL stores immutable metadata.

When both machine-readable evidence and a human-readable summary exist, the machine-readable evidence is canonical and the summary should be generated or derived from it rather than maintained as a second independent source of truth.
