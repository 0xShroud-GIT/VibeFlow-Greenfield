# Evidence Model

An Evidence item records type, source, project/task/execution/release references, candidate revision, producer/tool/provider, timestamp, content hash, storage reference, redaction class and optional signature/attestation.

Examples: command result, build log summary, test report, diff hash, dependency scan, screenshot, preview health response, deployment receipt, provider reconciliation result.

Evidence is append-only. Large payloads live by content hash in object storage; PostgreSQL stores immutable metadata.
