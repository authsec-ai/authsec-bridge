"""Parse a Claude Code session JSONL file into a NeutralSession.

Claude record types we care about:
  - {"type":"user", "message": {"role":"user", "content":[...]}}
  - {"type":"assistant", "message": {"role":"assistant", "content":[...]}}

Inside `content`, each item has its own `type`:
  - {"type":"text", "text":"..."}                            -> message text
  - {"type":"tool_use", "name":"Bash", "input":{...}}        -> tool call
  - {"type":"tool_result", "content":[{"type":"text",...}]}  -> tool result

We collapse adjacent same-role records into single turns since Claude
sometimes splits one assistant turn into multiple records (text, then a
tool_use, then more text after the tool returns).
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from ..model import NeutralSession, NeutralTurn


def _stringify_content(items: list[dict]) -> tuple[str, list[str]]:
    """Returns (text, tool_summaries) extracted from a Claude `content` array."""
    text_parts: list[str] = []
    summaries: list[str] = []
    for item in items:
        t = item.get("type")
        if t == "text":
            txt = (item.get("text") or "").strip()
            if txt:
                text_parts.append(txt)
        elif t == "tool_use":
            name = item.get("name", "Tool")
            inp = item.get("input", {})
            summaries.append(_summarize_tool_call(name, inp))
        elif t == "tool_result":
            # The result content is mostly noise for the bridged session — we
            # already summarized the call. Skip the body unless it's an error.
            inner = item.get("content")
            if isinstance(inner, list):
                for sub in inner:
                    if sub.get("type") == "text":
                        body = (sub.get("text") or "").strip()
                        if "error" in body.lower()[:80]:
                            summaries.append(f"  ↳ tool error: {body[:120]}")
        # Anything else we ignore for v1.
    return ("\n\n".join(text_parts), summaries)


def _summarize_tool_call(name: str, inp: dict[str, Any]) -> str:
    """One-line description of a tool call, for inclusion in the bridged session."""
    name_lower = name.lower()
    if name_lower == "bash":
        cmd = (inp.get("command") or "").strip()
        return f"ran `{cmd[:160]}`"
    if name_lower in ("edit", "write"):
        path = inp.get("file_path") or inp.get("path") or "?"
        return f"{name_lower} {path}"
    if name_lower == "read":
        path = inp.get("file_path") or "?"
        return f"read {path}"
    if name_lower == "grep":
        pat = inp.get("pattern", "")
        return f"grep `{pat[:80]}`"
    if name_lower == "glob":
        pat = inp.get("pattern", "")
        return f"glob `{pat[:80]}`"
    if name_lower in ("webfetch", "websearch"):
        return f"{name_lower} {inp.get('url') or inp.get('query', '?')}"
    # Fallback
    args_preview = json.dumps(inp, ensure_ascii=False)[:120]
    return f"{name} {args_preview}"


def parse_claude(path: str | Path) -> NeutralSession:
    p = Path(path)
    turns: list[NeutralTurn] = []
    session_id: str | None = None
    cwd: str | None = None
    started_at: str | None = None

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if session_id is None and rec.get("sessionId"):
                session_id = rec["sessionId"]
            if cwd is None and rec.get("cwd"):
                cwd = rec["cwd"]
            if started_at is None and rec.get("timestamp"):
                started_at = rec["timestamp"]

            rtype = rec.get("type")
            if rtype not in ("user", "assistant"):
                continue
            msg = rec.get("message") or {}
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                text, summaries = content, []
            elif isinstance(content, list):
                text, summaries = _stringify_content(content)
            else:
                continue

            # Skip tool_result-only user messages (they pollute the transcript)
            if role == "user" and not text and isinstance(content, list):
                if all(item.get("type") == "tool_result" for item in content):
                    continue

            if not text and not summaries:
                continue

            # Coalesce consecutive same-role turns
            if turns and turns[-1].role == role:
                if text:
                    turns[-1].text = (turns[-1].text + "\n\n" + text).strip()
                turns[-1].tool_summaries.extend(summaries)
            else:
                turns.append(NeutralTurn(
                    role=role,
                    text=text,
                    tool_summaries=summaries,
                    timestamp=rec.get("timestamp"),
                ))

    return NeutralSession(
        source_cli="claude",
        source_session_id=session_id or p.stem,
        cwd=cwd,
        started_at=started_at,
        turns=turns,
    )
