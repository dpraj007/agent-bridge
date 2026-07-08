# agent-bridge

**Cross-agent session handoffs** for [Claude Code](https://claude.ai/code), [Grok Build](https://x.ai), and friends.

Coding agents store chats in different formats. Switching tools usually means losing context. **agent-bridge** keeps a local, portable layer so you can:

1. **See** sessions from the other agent (`sessions list` / `show`)
2. **Hand off** work mid-task (`save` / `load` / `CURRENT.md`)
3. **Export** a native chat into a structured handoff

Local only. Zero dependencies. No cloud.

```bash
pip install agent-bridge
agent-bridge init
agent-bridge install-skills
agent-bridge sessions list
```

## Install

```bash
pip install agent-bridge
# or from source
pip install git+https://github.com/dpraj007/agent-bridge.git
```

```bash
agent-bridge init
agent-bridge install-skills          # Claude + Grok skill dirs
agent-bridge install-skills --wire-rules   # also append a short section to CLAUDE.md / AGENTS.md
```

## Quick start

### List sessions from every agent on this machine

```bash
agent-bridge sessions list
agent-bridge sessions list --agent grok
agent-bridge sessions list --agent claude
agent-bridge sessions show <id-or-title-fragment>
```

Catalogs are written to:

- `~/.agent-bridge/NATIVE_SESSIONS.md`
- `~/.claude/NATIVE_SESSIONS.md` (if present)
- `~/.grok/NATIVE_SESSIONS.md` (if present)

> Claude’s `/resume` UI will not list Grok sessions natively (and reverse). Use this catalog instead.

### Hand off mid-task

```bash
# After drafting handoff.md (goal, done, decisions, remaining):
agent-bridge save --agent claude --title "auth refactor" --body-file handoff.md

# In the other agent:
agent-bridge load latest
# or read ~/.agent-bridge/CURRENT.md
```

### Export a native session → handoff

```bash
agent-bridge sessions export <id>
```

## CLI reference

| Command | Description |
|---------|-------------|
| `init` | Create `~/.agent-bridge/` |
| `install-skills` | Install skill for Claude Code / Grok |
| `sessions list` | Unified native session index |
| `sessions show <id>` | Metadata + transcript excerpt |
| `sessions export <id>` | Export to handoff + mirror |
| `sessions search <q>` | Search titles/summaries |
| `sessions sync` | Rebuild shared catalog |
| `save` / `load` / `list` / `current` | Structured handoffs |
| `search` | Search handoffs |

Environment:

| Variable | Default |
|----------|---------|
| `AGENT_BRIDGE_HOME` | `~/.agent-bridge` |
| `CLAUDE_HOME` | `~/.claude` |
| `GROK_HOME` | `~/.grok` |

## How it works

```
┌─────────────┐     handoffs + catalog      ┌─────────────┐
│ Claude Code │◄───────────────────────────►│  Grok Build │
│  *.jsonl    │     ~/.agent-bridge/        │  sessions/  │
└─────────────┘                             └─────────────┘
```

Raw transcripts are huge and format-incompatible. The bridge stores **structured handoffs** and a **session index with excerpts** both agents can run via shell.

## Privacy

- **Local only** — no network calls by the CLI
- Reads session stores under `~/.claude` and `~/.grok` on **your** machine
- Does not upload transcripts
- `sessions show` returns **capped excerpts**, not full dumps by default

## Skill for agents

After `install-skills`, both harnesses get an `agent-bridge` skill. Agents should use the CLI when you say “handoff”, “list Grok sessions”, “resume shared”, etc.

## Development

```bash
git clone https://github.com/dpraj007/agent-bridge.git
cd agent-bridge
pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [LICENSE](LICENSE).

## Author

[Dhairyasheel Patil](https://github.com/dpraj007) — built because real work spans more than one agent.
