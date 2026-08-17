# Secret Handling

`SecretRef` is opaque metadata. Raw secrets live only in an approved encrypted broker/KMS boundary. Clients may submit a secret through a dedicated protected enrollment flow, but ordinary project APIs return only refs/metadata.

At execution time, the broker releases the minimum secret to the approved provider/tool channel for the shortest practical lifetime. Never place raw secrets in Agent prompts, event payloads, evidence blobs, logs, analytics or the native-web bridge.
