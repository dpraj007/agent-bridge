# Changelog

## 0.2.0 — 2026-07-08

- **OpenAI Codex support**: scan `~/.codex/sessions/**/rollout-*.jsonl`
- Use `session_index.jsonl` thread names when available
- `sessions list|show|export --agent codex`
- `install-skills --codex` and wire `~/.codex/AGENTS.md`
- Catalog mirror → `~/.codex/NATIVE_SESSIONS.md`
- Env: `CODEX_HOME` (default `~/.codex`)

## 0.1.0 — 2026-07-08

- Initial public release
- Structured handoffs (`save` / `load` / `current`)
- Native session catalog for Claude Code + Grok Build
- `sessions list|show|export|search|sync`
- `install-skills` for both harnesses
- Zero third-party dependencies
