## Codex support (v0.2.0)

agent-bridge now lists and opens **OpenAI Codex** sessions alongside Claude Code and Grok Build.

### New
- `sessions list --agent codex`
- `sessions show codex:<id>`
- `install-skills --codex`
- Catalog mirror at `~/.codex/NATIVE_SESSIONS.md`
- Env: `CODEX_HOME`

### Install
```bash
pip install "git+https://github.com/dpraj007/agent-bridge.git"
agent-bridge install-skills
agent-bridge sessions list --agent codex
```
