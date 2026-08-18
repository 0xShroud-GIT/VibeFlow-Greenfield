# tests/security

Security fixtures and later product security suites.

`fixtures/semgrep/positive` deterministically triggers every repository-owned
M-006 high-confidence execution/injection rule. `fixtures/semgrep/negative`
contains structurally similar safe operations and must produce zero findings.
`scripts/security/test-semgrep-rules.sh` asserts the exact six rule IDs and the
zero-finding negative result with Semgrep CE 1.172.0.

No product authorization, isolation, secret-handling, or abuse functionality is
implemented by M-006; those later suites remain mission-gated.
