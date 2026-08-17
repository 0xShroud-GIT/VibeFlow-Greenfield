# Native ↔ Workspace Web Bridge v1

Purpose: let the native mobile shell and embedded/linked workspace web surface exchange device/workspace UI actions without sharing backend authority.

Every session is bound to: bridge version, app build, authenticated account, project, workspace binding, allowed origin and negotiated capabilities.

Message envelope: version, id, correlation_id, direction, type, project_id, workspace_binding_id, payload. Sensitive commands require explicit permission and backend grant where relevant.

Never send raw BYOK/provider tokens. OAuth callbacks and secrets are mediated through native/control-plane flows and opaque references.

Required families: workspace state request/snapshot, editor action, selection/replace, keyboard/device state, navigation/exit, Git refresh, OAuth/permission request, upsell/account handoff, ACK/error, performance tracing.
