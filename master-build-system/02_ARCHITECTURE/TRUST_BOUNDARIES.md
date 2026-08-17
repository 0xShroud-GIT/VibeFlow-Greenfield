# Trust Boundaries

1. Mobile/web clients are untrusted requestors.
2. Gateway authenticates sessions and binds commands to Account/Organization/Project.
3. Control Plane is authoritative for VibeFlow resources.
4. Agent providers are untrusted executors: their claims are observations.
5. Workspaces are semi-trusted execution environments: mutable state must be reconciled and hashed.
6. External tools/connections are separately authorized via grants.
7. Deployment/data providers own their external resources but not VibeFlow product truth.
8. Verification must obtain independent evidence where feasible; it must not merely echo agent assertions.
