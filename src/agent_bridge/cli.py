#!/usr/bin/env python3
"""
agent-bridge — shared session handoff store for Grok Build + Claude Code.

Full raw transcripts are not portable across harnesses. This tool stores
structured handoffs both agents can save/load so work continues across tools.

Home: ~/.agent-bridge/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("AGENT_BRIDGE_HOME", Path.home() / ".agent-bridge"))
SESSIONS = HOME / "sessions"
INDEX = HOME / "index.jsonl"
CURRENT = HOME / "CURRENT.md"
CURRENT_META = HOME / "CURRENT.json"
NATIVE_CATALOG_JSON = HOME / "native-catalog.json"
NATIVE_CATALOG_MD = HOME / "NATIVE_SESSIONS.md"
NATIVE_MIRROR = HOME / "native-mirror"  # readable exports of peer sessions

GROK_HOME = Path(os.environ.get("GROK_HOME", Path.home() / ".grok"))
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
GROK_SESSIONS = GROK_HOME / "sessions"
CLAUDE_PROJECTS = CLAUDE_HOME / "projects"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(text: str, max_len: int = 48) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")[:max_len].strip("-")
    return s or "untitled"


def ensure_dirs() -> None:
    SESSIONS.mkdir(parents=True, exist_ok=True)
    HOME.mkdir(parents=True, exist_ok=True)


def detect_agent() -> str:
    # Best-effort environment hints
    if os.environ.get("GROK_HOME") or os.environ.get("XAI_API_KEY"):
        # Prefer explicit CLI flag; this is only a fallback.
        pass
    if os.environ.get("CLAUDE_CODE") or os.environ.get("CLAUDECODE"):
        return "claude"
    return "unknown"


def git_info(cwd: str | None) -> dict[str, str]:
    info = {"branch": "", "status_short": "", "repo_root": ""}
    if not cwd:
        return info
    try:
        import subprocess

        def run(args: list[str]) -> str:
            r = subprocess.run(
                args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return (r.stdout or "").strip()

        root = run(["git", "rev-parse", "--show-toplevel"])
        if not root:
            return info
        info["repo_root"] = root
        info["branch"] = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        info["status_short"] = run(["git", "status", "--short"])
    except Exception:
        pass
    return info


def append_index(entry: dict[str, Any]) -> None:
    with INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_index() -> list[dict[str, Any]]:
    if not INDEX.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def list_session_dirs() -> list[Path]:
    if not SESSIONS.exists():
        return []
    dirs = [p for p in SESSIONS.iterdir() if p.is_dir() and (p / "handoff.md").exists()]
    # Prefer name sort (timestamp prefix) then mtime
    dirs.sort(key=lambda p: p.name, reverse=True)
    return dirs


def resolve_id(id_or_latest: str) -> Path | None:
    if id_or_latest in ("latest", "current", ""):
        if CURRENT_META.exists():
            meta = json.loads(CURRENT_META.read_text(encoding="utf-8"))
            sid = meta.get("id")
            if sid:
                p = SESSIONS / sid
                if (p / "handoff.md").exists():
                    return p
        dirs = list_session_dirs()
        return dirs[0] if dirs else None

    # exact dir name
    p = SESSIONS / id_or_latest
    if (p / "handoff.md").exists():
        return p

    # prefix / fragment match
    matches = [d for d in list_session_dirs() if id_or_latest in d.name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # prefer exact prefix
        pref = [d for d in matches if d.name.startswith(id_or_latest)]
        return pref[0] if pref else matches[0]
    return None


def write_current(session_dir: Path, meta: dict[str, Any], handoff: str) -> None:
    title = meta.get("title") or session_dir.name
    source = meta.get("source_agent") or "unknown"
    ts = meta.get("created_at") or now_iso()
    cwd = meta.get("cwd") or ""
    branch = (meta.get("git") or {}).get("branch") or ""
    preview = "\n".join(handoff.strip().splitlines()[:40])
    CURRENT.write_text(
        f"""# Agent Bridge — CURRENT handoff

> Auto-generated pointer. Both **Grok Build** and **Claude Code** should read this
> at session start when resuming shared work.

- **id:** `{session_dir.name}`
- **title:** {title}
- **source:** {source}
- **created:** {ts}
- **cwd:** `{cwd}`
- **branch:** `{branch}`
- **path:** `{session_dir / "handoff.md"}`

## Handoff preview

{preview}

---
Load full handoff: `python ~/.agent-bridge/bin/agent_bridge.py load latest`
""",
        encoding="utf-8",
    )
    CURRENT_META.write_text(json.dumps({**meta, "id": session_dir.name}, indent=2), encoding="utf-8")


DEFAULT_HANDOFF_TEMPLATE = """# Handoff: {title}

## Goal
{goal}

## Done so far
{done}

## Decisions
{decisions}

## Remaining work
{remaining}

## Notes / gotchas
{notes}

## Open questions
{questions}
"""


def cmd_init(_: argparse.Namespace) -> int:
    ensure_dirs()
    readme = HOME / "README.md"
    if not readme.exists():
        readme.write_text(
            """# Agent Bridge

Shared session handoffs between **Grok Build** and **Claude Code**.

## Why not raw transcripts?

Claude stores sessions under `~/.claude/projects/*.jsonl`.
Grok stores sessions under `~/.grok/sessions/`.
Formats differ and full logs are huge. This bridge stores **structured handoffs**
both agents can write and resume from.

## Layout

```
~/.agent-bridge/
  CURRENT.md          # latest pointer (read at session start)
  CURRENT.json
  index.jsonl         # append-only catalog
  sessions/<id>/
    handoff.md        # the payload both agents read
    meta.json
  bin/agent_bridge.py
  skills/agent-bridge/SKILL.md
```

## CLI

```bash
python ~/.agent-bridge/bin/agent_bridge.py save --agent grok --title "auth refactor" --body-file handoff.md
python ~/.agent-bridge/bin/agent_bridge.py load latest
python ~/.agent-bridge/bin/agent_bridge.py list
python ~/.agent-bridge/bin/agent_bridge.py search "auth"
python ~/.agent-bridge/bin/agent_bridge.py current
```

## Agent usage

- Save when switching tools or ending a substantial stretch of work.
- Load at session start if `CURRENT.md` is relevant.
- Triggers: "handoff", "save for claude/grok", "resume shared session", "where was I".
""",
            encoding="utf-8",
        )
    if not INDEX.exists():
        INDEX.write_text("", encoding="utf-8")
    print(f"Initialized {HOME}")
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    ensure_dirs()
    title = args.title or "untitled"
    agent = args.agent or detect_agent()
    cwd = args.cwd or os.getcwd()
    stamp = now_stamp()
    sid = f"{stamp}-{slugify(title)}-{uuid.uuid4().hex[:4]}"
    session_dir = SESSIONS / sid
    session_dir.mkdir(parents=True, exist_ok=False)

    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.stdin or (not sys.stdin.isatty() and not args.body):
        body = sys.stdin.read()
    elif args.body:
        body = args.body
    else:
        body = DEFAULT_HANDOFF_TEMPLATE.format(
            title=title,
            goal=args.goal or "(fill in)",
            done=args.done or "(fill in)",
            decisions=args.decisions or "(none yet)",
            remaining=args.remaining or "(fill in)",
            notes=args.notes or "(none)",
            questions=args.questions or "(none)",
        )

    body = body.strip() + "\n"
    (session_dir / "handoff.md").write_text(body, encoding="utf-8")

    g = git_info(cwd)
    meta: dict[str, Any] = {
        "id": sid,
        "title": title,
        "source_agent": agent,
        "created_at": now_iso(),
        "cwd": cwd,
        "git": g,
        "tags": [t for t in (args.tags or "").split(",") if t.strip()],
        "native_session_hint": args.native_session or "",
    }
    (session_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    index_entry = {
        "id": sid,
        "title": title,
        "source_agent": agent,
        "created_at": meta["created_at"],
        "cwd": cwd,
        "branch": g.get("branch", ""),
        "path": str(session_dir / "handoff.md"),
    }
    append_index(index_entry)
    write_current(session_dir, meta, body)

    print("HANDOFF SAVED")
    print(f"  id:     {sid}")
    print(f"  title:  {title}")
    print(f"  agent:  {agent}")
    print(f"  path:   {session_dir / 'handoff.md'}")
    print(f"  current:{CURRENT}")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    ensure_dirs()
    path = resolve_id(args.id or "latest")
    if not path:
        print("No handoffs found. Save one first.", file=sys.stderr)
        return 1
    meta_path = path / "meta.json"
    handoff = (path / "handoff.md").read_text(encoding="utf-8")
    if args.json:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        print(json.dumps({"meta": meta, "handoff": handoff}, indent=2))
    else:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            print(f"# id: {meta.get('id')}")
            print(f"# source: {meta.get('source_agent')}  created: {meta.get('created_at')}")
            print(f"# cwd: {meta.get('cwd')}")
            print()
        print(handoff, end="" if handoff.endswith("\n") else "\n")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    ensure_dirs()
    dirs = list_session_dirs()[: args.limit]
    if not dirs:
        print("No handoffs yet.")
        return 0
    print(f"{'ID':<48} {'AGENT':<8} {'TITLE'}")
    print("-" * 90)
    for d in dirs:
        meta_path = d / "meta.json"
        title, agent = d.name, "?"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            title = meta.get("title") or title
            agent = meta.get("source_agent") or "?"
        print(f"{d.name:<48} {agent:<8} {title}")
    return 0


def cmd_current(_: argparse.Namespace) -> int:
    ensure_dirs()
    if CURRENT.exists():
        print(CURRENT.read_text(encoding="utf-8"), end="")
        return 0
    print("No CURRENT handoff. Save one with: agent_bridge.py save --title ...")
    return 1


def cmd_path(_: argparse.Namespace) -> int:
    print(HOME)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    ensure_dirs()
    q = args.query.lower()
    hits = 0
    for d in list_session_dirs():
        handoff = (d / "handoff.md").read_text(encoding="utf-8", errors="ignore")
        meta_txt = ""
        meta_path = d / "meta.json"
        if meta_path.exists():
            meta_txt = meta_path.read_text(encoding="utf-8", errors="ignore")
        blob = (handoff + "\n" + meta_txt + "\n" + d.name).lower()
        if q in blob:
            title = d.name
            agent = "?"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                title = meta.get("title") or title
                agent = meta.get("source_agent") or "?"
            print(f"{d.name}  [{agent}]  {title}")
            hits += 1
            if hits >= args.limit:
                break
    if hits == 0:
        print("No matches.")
        return 1
    return 0


def cmd_set_current(args: argparse.Namespace) -> int:
    path = resolve_id(args.id)
    if not path:
        print("Handoff not found.", file=sys.stderr)
        return 1
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    handoff = (path / "handoff.md").read_text(encoding="utf-8")
    write_current(path, meta, handoff)
    print(f"CURRENT set to {path.name}")
    return 0


# ---------------------------------------------------------------------------
# Native sessions (Grok + Claude) — unified catalog so each agent can see both
# ---------------------------------------------------------------------------


def _text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif "text" in block:
                    parts.append(str(block["text"]))
                elif "content" in block:
                    parts.append(_text_from_content(block["content"]))
        return "\n".join(parts)
    if isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        if "content" in content:
            return _text_from_content(content["content"])
    return str(content)


def scan_grok_sessions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not GROK_SESSIONS.exists():
        return out
    for summary in GROK_SESSIONS.rglob("summary.json"):
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        info = data.get("info") or {}
        sid = info.get("id") or summary.parent.name
        mtime = summary.stat().st_mtime
        out.append(
            {
                "agent": "grok",
                "id": sid,
                "title": data.get("generated_title")
                or data.get("session_summary")
                or sid,
                "summary": data.get("session_summary") or "",
                "cwd": (info.get("cwd") or ""),
                "created_at": data.get("created_at") or "",
                "updated_at": data.get("updated_at")
                or data.get("last_active_at")
                or "",
                "messages": data.get("num_chat_messages")
                or data.get("num_messages")
                or 0,
                "model": data.get("current_model_id") or "",
                "path": str(summary.parent),
                "summary_path": str(summary),
                "mtime": mtime,
            }
        )
    out.sort(key=lambda r: r.get("mtime") or 0, reverse=True)
    return out


def scan_claude_sessions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not CLAUDE_PROJECTS.exists():
        return out
    for jsonl in CLAUDE_PROJECTS.rglob("*.jsonl"):
        # Skip nested agent sidechains if any; keep top-level project sessions
        if jsonl.parent.name.startswith(".") or "subagents" in jsonl.parts:
            continue
        try:
            st = jsonl.stat()
        except OSError:
            continue
        # Derive cwd from project folder name when possible
        proj = jsonl.parent.name  # e.g. C--Users-ddpat
        cwd_guess = proj.replace("--", ":\\").replace("-", "\\") if proj.startswith("C--") else proj
        title = ""
        first_user = ""
        last_user = ""
        n_user = 0
        n_asst = 0
        try:
            with jsonl.open(encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    t = o.get("type")
                    if t == "ai-title":
                        title = o.get("aiTitle") or o.get("title") or title
                    elif t == "user":
                        n_user += 1
                        msg = o.get("message") or o
                        text = _text_from_content(msg.get("content") if isinstance(msg, dict) else msg)
                        text = text.strip()
                        if text and not first_user:
                            first_user = text[:240]
                        if text:
                            last_user = text[:240]
                    elif t == "assistant":
                        n_asst += 1
        except OSError:
            continue
        if not title:
            title = (first_user or jsonl.stem)[:80]
        out.append(
            {
                "agent": "claude",
                "id": jsonl.stem,
                "title": title,
                "summary": first_user,
                "last_user": last_user,
                "cwd": cwd_guess,
                "created_at": "",
                "updated_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "messages": n_user + n_asst,
                "model": "",
                "path": str(jsonl),
                "summary_path": str(jsonl),
                "mtime": st.st_mtime,
            }
        )
    out.sort(key=lambda r: r.get("mtime") or 0, reverse=True)
    return out


def scan_native(agent: str = "all") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if agent in ("all", "grok"):
        rows.extend(scan_grok_sessions())
    if agent in ("all", "claude"):
        rows.extend(scan_claude_sessions())
    rows.sort(key=lambda r: r.get("mtime") or 0, reverse=True)
    return rows


def find_native(id_or_fragment: str, agent: str = "all") -> dict[str, Any] | None:
    rows = scan_native(agent)
    # exact id
    for r in rows:
        if r["id"] == id_or_fragment:
            return r
    # grok:id / claude:id
    if ":" in id_or_fragment:
        a, _, rest = id_or_fragment.partition(":")
        return find_native(rest, a if a in ("grok", "claude") else agent)
    matches = [r for r in rows if id_or_fragment in r["id"] or id_or_fragment.lower() in (r.get("title") or "").lower()]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # prefer more recently updated
    matches.sort(key=lambda r: r.get("mtime") or 0, reverse=True)
    return matches[0]


def extract_grok_transcript(session_dir: Path, max_chars: int = 12000) -> str:
    chat = session_dir / "chat_history.jsonl"
    lines_out: list[str] = []
    total = 0
    if not chat.exists():
        return "(no chat_history.jsonl)"
    with chat.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = o.get("type") or o.get("role") or "?"
            if role not in ("user", "assistant", "system"):
                continue
            if role == "system":
                continue  # skip huge system prompts
            text = _text_from_content(o.get("content")).strip()
            if not text:
                continue
            # Strip common wrapper tags for readability
            if text.startswith("<user_info>") or text.startswith("<system-reminder>"):
                continue
            chunk = f"### {role}\n{text[:2000]}\n"
            if total + len(chunk) > max_chars:
                lines_out.append("\n…(truncated)…\n")
                break
            lines_out.append(chunk)
            total += len(chunk)
    return "\n".join(lines_out) if lines_out else "(no user/assistant messages extracted)"


def extract_claude_transcript(jsonl_path: Path, max_chars: int = 12000) -> str:
    lines_out: list[str] = []
    total = 0
    with jsonl_path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = o.get("type")
            if t not in ("user", "assistant"):
                continue
            msg = o.get("message") or o
            role = t
            if isinstance(msg, dict) and msg.get("role"):
                role = msg["role"]
            text = _text_from_content(msg.get("content") if isinstance(msg, dict) else msg).strip()
            if not text:
                continue
            if text.startswith("<") and "system-reminder" in text[:80]:
                continue
            chunk = f"### {role}\n{text[:2000]}\n"
            if total + len(chunk) > max_chars:
                lines_out.append("\n…(truncated)…\n")
                break
            lines_out.append(chunk)
            total += len(chunk)
    return "\n".join(lines_out) if lines_out else "(no user/assistant messages extracted)"


def write_native_catalog(rows: list[dict[str, Any]]) -> None:
    ensure_dirs()
    # Strip heavy fields for json
    slim = []
    for r in rows:
        slim.append({k: v for k, v in r.items() if k != "mtime"})
    NATIVE_CATALOG_JSON.write_text(json.dumps(slim, indent=2), encoding="utf-8")

    lines = [
        "# Native sessions - Grok Build + Claude Code",
        "",
        f"_Generated: {now_iso()}_",
        "",
        "Both agents can list/show these via:",
        "`python ~/.agent-bridge/bin/agent_bridge.py sessions list`",
        "",
        "| Agent | Updated | Title | Id | Msgs | Cwd |",
        "|-------|---------|-------|----|------|-----|",
    ]
    for r in rows[:100]:
        title = (r.get("title") or "").replace("|", "\\|").replace("\n", " ")[:60]
        cwd = (r.get("cwd") or "").replace("|", "\\|")[:40]
        lines.append(
            f"| {r.get('agent')} | {(r.get('updated_at') or '')[:19]} | {title} | `{r.get('id')}` | {r.get('messages')} | `{cwd}` |"
        )
    lines.append("")
    lines.append("## Commands")
    lines.append("")
    lines.append("```text")
    lines.append("sessions list [--agent grok|claude|all] [--limit N]")
    lines.append("sessions show <id|fragment>     # metadata + transcript excerpt")
    lines.append("sessions export <id>            # write handoff + mirror md")
    lines.append("sessions search <query>")
    lines.append("sessions sync                   # rebuild this catalog")
    lines.append("```")
    lines.append("")
    NATIVE_CATALOG_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Mirrors next to each harness so agents "see" the peer list nearby
    for dest in (
        GROK_HOME / "NATIVE_SESSIONS.md",
        CLAUDE_HOME / "NATIVE_SESSIONS.md",
        CLAUDE_HOME / "agent-bridge-sessions.md",
        GROK_HOME / "agent-bridge-sessions.md",
    ):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(NATIVE_CATALOG_MD.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass


def cmd_sessions_list(args: argparse.Namespace) -> int:
    # Always rebuild full catalog so filtered lists don't wipe the shared index
    all_rows = scan_native("all")
    write_native_catalog(all_rows)
    rows = all_rows if args.agent == "all" else [r for r in all_rows if r["agent"] == args.agent]
    rows = rows[: args.limit]
    if not rows:
        print("No native sessions found.")
        return 0
    print(f"{'AGENT':<8} {'UPDATED':<20} {'MSGS':>5}  {'TITLE':<40}  ID")
    print("-" * 110)
    for r in rows:
        title = (r.get("title") or "")[:40]
        updated = (r.get("updated_at") or "")[:19]
        print(f"{r['agent']:<8} {updated:<20} {r.get('messages') or 0:>5}  {title:<40}  {r['id']}")
    print()
    print(f"Catalog: {NATIVE_CATALOG_MD}")
    print(f"Also mirrored to ~/.grok/NATIVE_SESSIONS.md and ~/.claude/NATIVE_SESSIONS.md")
    return 0


def cmd_sessions_show(args: argparse.Namespace) -> int:
    row = find_native(args.id, args.agent)
    if not row:
        print(f"Session not found: {args.id}", file=sys.stderr)
        return 1
    print(f"agent:    {row['agent']}")
    print(f"id:       {row['id']}")
    print(f"title:    {row.get('title')}")
    print(f"cwd:      {row.get('cwd')}")
    print(f"updated:  {row.get('updated_at')}")
    print(f"messages: {row.get('messages')}")
    print(f"path:     {row.get('path')}")
    if row.get("summary"):
        print(f"summary:  {row['summary'][:300]}")
    print()
    if args.meta_only:
        return 0
    print("## Transcript excerpt")
    print()
    if row["agent"] == "grok":
        print(extract_grok_transcript(Path(row["path"]), max_chars=args.max_chars))
    else:
        print(extract_claude_transcript(Path(row["path"]), max_chars=args.max_chars))
    return 0


def cmd_sessions_export(args: argparse.Namespace) -> int:
    row = find_native(args.id, args.agent)
    if not row:
        print(f"Session not found: {args.id}", file=sys.stderr)
        return 1
    if row["agent"] == "grok":
        excerpt = extract_grok_transcript(Path(row["path"]), max_chars=args.max_chars)
    else:
        excerpt = extract_claude_transcript(Path(row["path"]), max_chars=args.max_chars)

    title = row.get("title") or row["id"]
    body = f"""# Handoff from native {row['agent']} session

## Goal
Resume / inspect work from {row['agent']} session: {title}

## Native session
- agent: {row['agent']}
- id: `{row['id']}`
- path: `{row.get('path')}`
- cwd: `{row.get('cwd')}`
- updated: {row.get('updated_at')}
- messages: {row.get('messages')}

## Summary
{row.get('summary') or '(none)'}

## Transcript excerpt
{excerpt}

## Remaining work
(Infer from transcript; fill when saving a real handoff.)

## Notes / gotchas
Exported automatically by agent-bridge `sessions export`.
"""
    # Mirror markdown for the peer agent
    NATIVE_MIRROR.mkdir(parents=True, exist_ok=True)
    mirror = NATIVE_MIRROR / f"{row['agent']}-{slugify(title)}-{row['id'][:8]}.md"
    mirror.write_text(body, encoding="utf-8")

    # Also save as bridge handoff so CURRENT can point at it
    tmp = HOME / ".export-body.md"
    tmp.write_text(body, encoding="utf-8")
    rc = cmd_save(
        argparse.Namespace(
            title=f"[{row['agent']}] {title}"[:80],
            agent=row["agent"],
            cwd=row.get("cwd") or os.getcwd(),
            body_file=str(tmp),
            body=None,
            stdin=False,
            goal=None,
            done=None,
            decisions=None,
            remaining=None,
            notes=None,
            questions=None,
            tags=f"native,{row['agent']}",
            native_session=row["id"],
        )
    )
    try:
        tmp.unlink(missing_ok=True)  # type: ignore[call-arg]
    except TypeError:
        if tmp.exists():
            tmp.unlink()
    print(f"Mirror:  {mirror}")
    return rc


def cmd_sessions_search(args: argparse.Namespace) -> int:
    q = args.query.lower()
    rows = scan_native(args.agent)
    hits = 0
    for r in rows:
        blob = " ".join(
            str(r.get(k) or "")
            for k in ("id", "title", "summary", "last_user", "cwd", "path")
        ).lower()
        if q in blob:
            print(f"{r['agent']:<8} {r['id']}  {(r.get('title') or '')[:60]}")
            hits += 1
            if hits >= args.limit:
                break
    if hits == 0:
        print("No matches.")
        return 1
    return 0


def cmd_sessions_sync(args: argparse.Namespace) -> int:
    rows = scan_native("all")
    write_native_catalog(rows)
    print(f"Synced {len(rows)} native sessions.")
    print(f"  {NATIVE_CATALOG_MD}")
    print(f"  {NATIVE_CATALOG_JSON}")
    print(f"  ~/.grok/NATIVE_SESSIONS.md")
    print(f"  ~/.claude/NATIVE_SESSIONS.md")
    if args.export_recent:
        # Export N most recent from each agent so both sides have readable mirrors
        by_agent: dict[str, list[dict[str, Any]]] = {"grok": [], "claude": []}
        for r in rows:
            a = r["agent"]
            if a in by_agent and len(by_agent[a]) < args.export_recent:
                by_agent[a].append(r)
        for a, group in by_agent.items():
            for r in group:
                ns = argparse.Namespace(
                    id=r["id"], agent=a, max_chars=8000
                )
                print(f"Exporting {a}:{r['id'][:8]}…")
                cmd_sessions_export(ns)
    return 0


SKILL_SNIPPET = """
## Agent Bridge (shared multi-agent sessions)

Cross-agent handoffs and native session catalog live under `~/.agent-bridge/`.

CLI: `agent-bridge` (or `python -m agent_bridge`)

```text
agent-bridge sessions list
agent-bridge sessions list --agent grok
agent-bridge sessions show <id>
agent-bridge sessions export <id>
agent-bridge save --agent <claude|grok> --title "..." --body-file handoff.md
agent-bridge load latest
agent-bridge current
```

Skill: `agent-bridge`. Local only — no network. Prefer excerpts over raw JSONL dumps.
"""


def _package_skill_md() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "data" / "SKILL.md",
        here.parents[2] / "skills" / "agent-bridge" / "SKILL.md",
        here.parents[1] / "skills" / "agent-bridge" / "SKILL.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def cmd_install_skills(args: argparse.Namespace) -> int:
    ensure_dirs()
    skill_src = _package_skill_md()
    if not skill_src:
        print("Bundled SKILL.md not found in package.", file=sys.stderr)
        return 1
    body = skill_src.read_text(encoding="utf-8")
    only_claude = bool(getattr(args, "claude", False))
    only_grok = bool(getattr(args, "grok", False))
    install_claude = only_claude or not (only_claude or only_grok)
    install_grok = only_grok or not (only_claude or only_grok)
    targets: list[Path] = []
    if install_claude:
        targets.append(CLAUDE_HOME / "skills" / "agent-bridge" / "SKILL.md")
    if install_grok:
        targets.append(GROK_HOME / "skills" / "agent-bridge" / "SKILL.md")
    for dest in targets:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        print(f"Installed skill → {dest}")

    if getattr(args, "wire_rules", False):
        marker_open = "<!-- agent-bridge -->"
        marker_close = "<!-- /agent-bridge -->"
        for rules_path in (CLAUDE_HOME / "CLAUDE.md", GROK_HOME / "AGENTS.md"):
            try:
                rules_path.parent.mkdir(parents=True, exist_ok=True)
                existing = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
                if marker_open in existing:
                    print(f"Rules already wired: {rules_path}")
                    continue
                block = f"\n{marker_open}\n{SKILL_SNIPPET.strip()}\n{marker_close}\n"
                rules_path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
                print(f"Appended bridge section → {rules_path}")
            except OSError as e:
                print(f"Skip rules {rules_path}: {e}", file=sys.stderr)

    home_skill = HOME / "skills" / "agent-bridge" / "SKILL.md"
    home_skill.parent.mkdir(parents=True, exist_ok=True)
    home_skill.write_text(body, encoding="utf-8")
    print(f"Bridge home skill → {home_skill}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-bridge",
        description="Shared Grok ↔ Claude handoffs + native session catalog",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="Create ~/.agent-bridge layout")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("install-skills", help="Install agent-bridge skill for Claude and/or Grok")
    s.add_argument("--claude", action="store_true", help="Only Claude Code skill dir")
    s.add_argument("--grok", action="store_true", help="Only Grok skill dir")
    s.add_argument(
        "--wire-rules",
        action="store_true",
        help="Append a short section to ~/.claude/CLAUDE.md and ~/.grok/AGENTS.md",
    )
    s.set_defaults(func=cmd_install_skills)

    s = sub.add_parser("save", help="Save a structured handoff")
    s.add_argument("--agent", choices=["grok", "claude", "unknown", "other"], default=None)
    s.add_argument("--title", required=True)
    s.add_argument("--cwd", default=None)
    s.add_argument("--body-file", default=None)
    s.add_argument("--body", default=None)
    s.add_argument("--stdin", action="store_true", help="Read handoff body from stdin")
    s.add_argument("--goal", default=None)
    s.add_argument("--done", default=None)
    s.add_argument("--decisions", default=None)
    s.add_argument("--remaining", default=None)
    s.add_argument("--notes", default=None)
    s.add_argument("--questions", default=None)
    s.add_argument("--tags", default="")
    s.add_argument("--native-session", default="", help="Optional native session id/path hint")
    s.set_defaults(func=cmd_save)

    s = sub.add_parser("load", help="Print a handoff (default: latest)")
    s.add_argument("id", nargs="?", default="latest")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_load)

    s = sub.add_parser("list", help="List structured handoffs")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("current", help="Show CURRENT.md pointer")
    s.set_defaults(func=cmd_current)

    s = sub.add_parser("path", help="Print bridge home directory")
    s.set_defaults(func=cmd_path)

    s = sub.add_parser("search", help="Search structured handoffs")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("set-current", help="Point CURRENT at an existing handoff id")
    s.add_argument("id")
    s.set_defaults(func=cmd_set_current)

    # Native sessions (both agents)
    ns = sub.add_parser("sessions", help="List/show/export native Grok + Claude sessions")
    nsub = ns.add_subparsers(dest="sessions_cmd", required=True)

    s = nsub.add_parser("list", help="List native sessions from both agents")
    s.add_argument("--agent", choices=["all", "grok", "claude"], default="all")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_sessions_list)

    s = nsub.add_parser("show", help="Show metadata + transcript excerpt")
    s.add_argument("id", help="Session id, fragment, or grok:<id> / claude:<id>")
    s.add_argument("--agent", choices=["all", "grok", "claude"], default="all")
    s.add_argument("--meta-only", action="store_true")
    s.add_argument("--max-chars", type=int, default=12000)
    s.set_defaults(func=cmd_sessions_show)

    s = nsub.add_parser("export", help="Export native session to handoff + mirror")
    s.add_argument("id")
    s.add_argument("--agent", choices=["all", "grok", "claude"], default="all")
    s.add_argument("--max-chars", type=int, default=12000)
    s.set_defaults(func=cmd_sessions_export)

    s = nsub.add_parser("search", help="Search native session titles/summaries")
    s.add_argument("query")
    s.add_argument("--agent", choices=["all", "grok", "claude"], default="all")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_sessions_search)

    s = nsub.add_parser("sync", help="Rebuild shared native catalog for both agents")
    s.add_argument(
        "--export-recent",
        type=int,
        default=0,
        help="Also export N most recent sessions per agent as handoffs",
    )
    s.set_defaults(func=cmd_sessions_sync)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
