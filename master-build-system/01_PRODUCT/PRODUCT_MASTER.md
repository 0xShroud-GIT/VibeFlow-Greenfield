# Product Master — Finished VibeFlow

## Product promise

VibeFlow should feel vertically integrated while remaining horizontally provider-neutral.

A finished V1 supports a coherent Build → Test → Security → Diff → Policy → Preview → Release → Deployment → Evidence loop across independently owned agent/model/workspace/repository/tool/deployment providers.

## Primary product areas

### Home / Create
Projects, create-from-prompt, recent tasks, action-needed approvals, notifications, provider/connection health.

### Project
Agent/task, workspace, Git/diff/checkpoints, build/test/security, preview, connections, data/storage, deployments/releases, evidence/verification, settings.

### Mobile control
Create/open project, launch/cancel/retry task, inspect Agent plan/progress, approve actions, receive notifications, inspect diff/verification/deployment summaries, recover/reconnect.

### Workspace web
Files/editor, terminal, preview, Git/diff/history, detailed activity, build/test/security logs, connection/deployment details, artifact/design surfaces.

## User-visible statuses

UI must use canonical state projections from backend state machines. Provider-specific terms are translated at adapter boundaries and may be shown only as secondary diagnostic detail.

## Finish definition

V1 is not complete because a demo works. `11_VERIFICATION/V1_ACCEPTANCE.md` defines the finish line.
