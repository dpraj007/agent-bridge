---
name: agent-bridge
description: >
  Shared sessions between coding agents (Claude Code, Grok Build, …): structured
  handoffs PLUS a unified catalog of native sessions. Use for handoff, list
  sessions, show peer sessions, resume shared work, switch agents, or
  agent-bridge commands.
---

# Agent Bridge — cross-agent sessions

CLI (after `pip install agent-bridge` or `pip install -e .`):

```bash
agent-bridge <command>
# or
python -m agent_bridge <command>
```

## Two layers

| Layer | What | Command |
|-------|------|---------|
| **Native catalog** | Sessions on disk from each agent | `sessions list/show/export/sync` |
| **Handoffs** | Portable summaries for continuing work | `save` / `load` / `current` |

Living catalogs (refreshed on `sessions list` / `sessions sync`):

- `~/.agent-bridge/NATIVE_SESSIONS.md`
- `~/.grok/NATIVE_SESSIONS.md` (when Grok is installed)
- `~/.claude/NATIVE_SESSIONS.md` (when Claude Code is installed)

Peer chats do **not** appear in the other product’s native `/resume` UI — use this catalog.

## Session start

```bash
agent-bridge sessions sync
agent-bridge current
agent-bridge sessions list
agent-bridge sessions show <id>
```

## Save before switching agents

Draft a handoff markdown (goal, done, decisions, remaining), then:

```bash
agent-bridge save --agent claude --title "TITLE" --cwd "$PWD" --body-file handoff.md
# or --agent grok
```

## Rules

- Prefer `sessions list/show` over dumping multi‑MB raw JSONL.
- Transcripts from `show` are **excerpts** (capped).
- Local only — no network required.
