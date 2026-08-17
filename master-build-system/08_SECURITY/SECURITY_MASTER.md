# Security Master

Security is defined around authorities and grants rather than around trusting the agent/workspace.

Required control families:
- authentication/session security,
- tenant/project/resource authorization,
- provider account linking,
- SecretRef/KMS envelope and token brokerage,
- ConnectionGrant least privilege and revocation,
- agent/tool/workspace permissions,
- approval for privileged/irreversible actions,
- workspace sandbox/network egress/resource quotas,
- native-web bridge origin/session/project binding,
- supply-chain/dependency/container scanning,
- audit and evidence integrity,
- redaction in logs/telemetry/support,
- abuse/rate/budget controls.

Security tests are negative by default: prove one tenant/agent/project cannot cross boundaries.
