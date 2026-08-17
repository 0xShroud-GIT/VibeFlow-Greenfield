# Workspace Web Master

Technology: React + Monaco + xterm.js, served as a provider-neutral IDE surface.

Primary panes: file tree/editor, terminal, preview, Git/diff, detailed Agent activity, build/test/security, logs, connection/deployment details.

The workspace surface talks to VibeFlow backend through authenticated APIs/remote stream and to native mobile through the versioned bridge. It does not receive raw BYOK secrets.
