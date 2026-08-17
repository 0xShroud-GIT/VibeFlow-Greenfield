# Frontend Master

The frontend is a projection/controller over canonical resources. It never invents backend truth.

## Native mobile owns the experience for
Home/Create, Projects, Task/Agent summary, action/approval center, provider/connection setup, notifications, recovery status, account/org/settings, concise Git/verification/deployment summaries.

## Workspace web owns the experience for
Files/Monaco editor, terminal/xterm, preview, Git/diff/history, detailed activity/logs, build/test/security details, deployment details, data/storage tools, Canvas/design and advanced artifact surfaces.

## Shared UX rules
- Always distinguish running/candidate-complete/verifying/verified.
- Display provider degradation without converting it to VibeFlow resource loss unless reconciliation proves loss.
- Permission/approval state is explicit; no surprise privileged actions.
- Offline/reconnect state is visible and non-destructive.
- Provider names may appear as detail, but primary workflow vocabulary is provider-neutral.

All commands/events/resources for each surface are bound in `09_CONTRACTS/FRONTEND_BACKEND_MATRIX.yaml`.
