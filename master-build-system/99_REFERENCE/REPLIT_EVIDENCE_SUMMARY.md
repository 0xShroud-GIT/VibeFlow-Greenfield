# Replit Research — Safe Architecture Summary

The Replit Android/XAPK deep dive is retained to answer **what capabilities and client-visible patterns a mature integrated agentic IDE needs**, not how to copy Replit internals.

Key proven patterns include a native mobile shell, web workspace/editor surface, a purpose-built native↔workspace bridge, GraphQL/control-plane client, Agent/task/checkpoint/background/notification flows, billing/entitlements, Git/project lifecycle, local parsing/editor utilities and extensive provider/product state vocabulary. Current public Replit docs additionally establish Plan vs Build behavior, checkpoints/version control, MCP integration, publishing/runtime separation and design/visual surfaces.

Maximum static pass included official P1sec hermes-dec 0.1.7 high-level decompilation and full instruction graph, Android DEX/native/config analysis and semantic cross-references. Private backend implementations remain unknowable from the client.

Important correction: the Hermes `FunctionSource` entries in this bundle resolve to empty source strings; embedded `.tsx/.ts` paths are source-like literals, not formal debug source mappings.

Use `REPLIT_TO_VIBEFLOW_390_EVIDENCE_MAP.csv` only for traceability and coverage checks.
