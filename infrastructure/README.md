# infrastructure

Infrastructure-as-code/configuration introduced only by approved missions.

- `dev/dev-environment-policy.json` — M-007 immutable provenance/security
  policy lock for the repository development environment (base image
  coordinate + digest + architectures, registered features, toolchain,
  bootstrap and security posture). It is a provenance/policy lock, not a
  second environment-description protocol; `.devcontainer/devcontainer.json`
  remains the single portable Dev Containers description.

Do not implement functionality here until the active mission authorizes it.
