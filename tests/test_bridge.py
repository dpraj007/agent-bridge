"""Tests for agent-bridge (stdlib + pytest)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_bridge import cli


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def bridge_home(tmp_path, monkeypatch):
    home = tmp_path / "bridge"
    claude = tmp_path / "claude"
    grok = tmp_path / "grok"
    codex = tmp_path / "codex"
    home.mkdir()
    (claude / "projects" / "demo-proj").mkdir(parents=True)
    (grok / "sessions" / "cwd" / "sess").mkdir(parents=True)
    (codex / "sessions" / "2026" / "05" / "23").mkdir(parents=True)

    # Claude fixture
    src_c = (FIXTURES / "claude_project" / "demo.jsonl").read_text(encoding="utf-8")
    (claude / "projects" / "demo-proj" / "demo-claude-001.jsonl").write_text(src_c, encoding="utf-8")

    # Grok fixture
    sess = grok / "sessions" / "cwd" / "sess"
    for name in ("summary.json", "chat_history.jsonl"):
        data = (FIXTURES / "grok_session" / name).read_bytes()
        (sess / name).write_bytes(data)

    # Codex fixture
    codex_name = (
        "rollout-2026-05-23T12-00-00-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jsonl"
    )
    codex_src = (FIXTURES / "codex_session" / codex_name).read_text(encoding="utf-8")
    (codex / "sessions" / "2026" / "05" / "23" / codex_name).write_text(
        codex_src, encoding="utf-8"
    )
    (codex / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "thread_name": "Demo Codex session",
                "updated_at": "2026-05-23T13:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_BRIDGE_HOME", str(home))
    monkeypatch.setenv("CLAUDE_HOME", str(claude))
    monkeypatch.setenv("GROK_HOME", str(grok))
    monkeypatch.setenv("CODEX_HOME", str(codex))

    # Reload path constants on module
    cli.HOME = home
    cli.SESSIONS = home / "sessions"
    cli.INDEX = home / "index.jsonl"
    cli.CURRENT = home / "CURRENT.md"
    cli.CURRENT_META = home / "CURRENT.json"
    cli.NATIVE_CATALOG_JSON = home / "native-catalog.json"
    cli.NATIVE_CATALOG_MD = home / "NATIVE_SESSIONS.md"
    cli.NATIVE_MIRROR = home / "native-mirror"
    cli.CLAUDE_HOME = claude
    cli.GROK_HOME = grok
    cli.CODEX_HOME = codex
    cli.GROK_SESSIONS = grok / "sessions"
    cli.CLAUDE_PROJECTS = claude / "projects"
    cli.CODEX_SESSIONS = codex / "sessions"
    cli.CODEX_SESSION_INDEX = codex / "session_index.jsonl"

    return home


def test_slugify():
    assert cli.slugify("Hello World!") == "hello-world"
    assert cli.slugify("") == "untitled"


def test_init_and_save_load(bridge_home, tmp_path):
    assert cli.main(["init"]) == 0
    body = tmp_path / "h.md"
    body.write_text("# Handoff\n\n## Goal\nShip it\n", encoding="utf-8")
    assert (
        cli.main(
            [
                "save",
                "--agent",
                "grok",
                "--title",
                "Ship it",
                "--body-file",
                str(body),
                "--cwd",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert cli.main(["list"]) == 0
    assert cli.main(["current"]) == 0
    assert cli.main(["load", "latest"]) == 0
    assert (bridge_home / "CURRENT.md").exists()


def test_scan_native_sessions(bridge_home):
    rows = cli.scan_native("all")
    agents = {r["agent"] for r in rows}
    assert "grok" in agents
    assert "claude" in agents
    assert "codex" in agents
    titles = {r["title"] for r in rows}
    assert any("Grok" in t or "Demo" in t for t in titles)
    assert any("Claude" in t or "Demo" in t for t in titles)
    assert any("Codex" in t or "Demo" in t or "git" in t.lower() for t in titles)


def test_sessions_list_and_show(bridge_home, capsys):
    assert cli.main(["sessions", "list", "--limit", "10"]) == 0
    out = capsys.readouterr().out
    assert "grok" in out or "claude" in out
    assert "codex" in out
    assert cli.main(["sessions", "show", "demo-claude-001", "--meta-only"]) == 0
    assert (
        cli.main(
            [
                "sessions",
                "show",
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "--meta-only",
            ]
        )
        == 0
    )
    assert cli.main(["sessions", "sync"]) == 0
    assert (bridge_home / "NATIVE_SESSIONS.md").exists()


def test_extract_transcripts(bridge_home):
    grok_dir = cli.GROK_SESSIONS / "cwd" / "sess"
    text = cli.extract_grok_transcript(grok_dir, max_chars=2000)
    assert "user" in text.lower() or "Hello" in text
    claude_path = cli.CLAUDE_PROJECTS / "demo-proj" / "demo-claude-001.jsonl"
    text2 = cli.extract_claude_transcript(claude_path, max_chars=2000)
    assert "demo" in text2.lower() or "help" in text2.lower()
    codex_path = next(cli.CODEX_SESSIONS.rglob("rollout-*.jsonl"))
    text3 = cli.extract_codex_transcript(codex_path, max_chars=2000)
    assert "git" in text3.lower() or "clean" in text3.lower()


def test_install_skills(bridge_home):
    # skill bundled in package data or repo skills/
    rc = cli.main(["install-skills"])
    assert rc == 0
    assert (cli.CLAUDE_HOME / "skills" / "agent-bridge" / "SKILL.md").exists()
    assert (cli.GROK_HOME / "skills" / "agent-bridge" / "SKILL.md").exists()
    assert (cli.CODEX_HOME / "skills" / "agent-bridge" / "SKILL.md").exists()
