# Security Policy

## What this tool does

`agent-bridge` runs **locally**. It may read:

- `~/.claude/projects/**` (Claude Code session JSONL)
- `~/.grok/sessions/**` (Grok Build session dirs)
- `~/.agent-bridge/**` (handoffs you create)

It does **not** open network connections by default and does **not** phone home.

## Reporting a vulnerability

Please open a private security advisory on GitHub or email the maintainer via GitHub profile contact options. Do not post exploit details in public issues until a fix is available.

## Recommendations

- Do not commit `~/.agent-bridge` session data to public repos
- Treat session transcripts as sensitive (may contain secrets, tokens, personal data)
- Prefer `sessions show` excerpts over pasting full JSONL into chats
