---
name: agent-bridge
description: >
  Shared sessions between coding agents (Claude Code, Grok Build, Codex): structured
  handoffs PLUS a unified catalog of native sessions. Use for handoff, list
  sessions, show peer sessions, resume shared work, switch agents, or
  agent-bridge commands.
---

# Agent Bridge — cross-agent sessions

CLI (after `pip install "git+https://github.com/dpraj007/agent-bridge.git"`):

```bash
agent-bridge <command>
# or
python -m agent_bridge <command>
```

## Supported agents

| Agent | Session store |
|-------|----------------|
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| Grok Build | `~/.grok/sessions/**` |
| OpenAI Codex | `~/.codex/sessions/**/rollout-*.jsonl` |

## Two layers

| Layer | What | Command |
|-------|------|---------|
| **Native catalog** | Sessions on disk from each agent | `sessions list/show/export/sync` |
| **Handoffs** | Portable summaries for continuing work | `save` / `load` / `current` |

Living catalogs (refreshed on `sessions list` / `sessions sync`):

- `~/.agent-bridge/NATIVE_SESSIONS.md`
- `~/.claude/NATIVE_SESSIONS.md`
- `~/.grok/NATIVE_SESSIONS.md`
- `~/.codex/NATIVE_SESSIONS.md`

Peer chats do **not** appear in another product’s native resume UI — use this catalog.

## Session start

```bash
agent-bridge sessions sync
agent-bridge current
agent-bridge sessions list
agent-bridge sessions list --agent codex
agent-bridge sessions show <id>
```

## Save before switching agents

```bash
agent-bridge save --agent codex --title "TITLE" --cwd "$PWD" --body-file handoff.md
# or --agent claude / --agent grok
```

## Rules

- Prefer `sessions list/show` over dumping multi‑MB raw JSONL.
- Transcripts from `show` are **excerpts** (capped).
- Local only — no network required.
