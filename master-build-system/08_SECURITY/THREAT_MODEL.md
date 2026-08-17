# Threat Model Summary

Primary adversarial/failure actors: malicious/compromised coding agent, prompt injection through repository/tool data, compromised MCP server, leaked provider token, malicious project dependency, hostile workspace process, cross-tenant ID confusion, replayed commands, stale mobile/web client, malicious embedded web content, provider account compromise, billing abuse.

High-value assets: identity sessions, provider credentials, ConnectionGrants, project source, private repo data, workspace filesystem/process/network, evidence integrity, release/deployment authority, billing/usage records.

Default stance: external providers/agents/workspaces are not trusted to assert VibeFlow authority. Every boundary authenticates, scopes, validates and records evidence.
