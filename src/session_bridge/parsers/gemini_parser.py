"""Parse a Gemini CLI session JSON into a NeutralSession.

Format (real example):
  {
    "sessionId": "<uuid>",
    "projectHash": "<sha256>",
    "startTime": "2026-01-08T...",
    "lastUpdated": "2026-01-08T...",
    "messages": [
      {"id":..., "timestamp":..., "type":"user", "content":"..."},
      {"id":..., "timestamp":..., "type":"model", "content":"..."},
      ...
    ]
  }
"""

from __future__ import annotations
import json
from pathlib import Path

from ..model import NeutralSession, NeutralTurn


_ROLE_MAP = {
    "user": "user",
    "gemini": "assistant",   # current Gemini CLI uses "gemini"
    "model": "assistant",    # older versions
    "assistant": "assistant",
}


def parse_gemini(path: str | Path) -> NeutralSession:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    turns: list[NeutralTurn] = []
    for msg in data.get("messages", []):
        mtype = msg.get("type")
        role = _ROLE_MAP.get(mtype)
        if role is None:
            continue
        content = msg.get("content")
        text = content if isinstance(content, str) else (
            json.dumps(content, ensure_ascii=False) if content is not None else ""
        )
        text = text.strip()
        if not text:
            continue
        if turns and turns[-1].role == role:
            turns[-1].text = (turns[-1].text + "\n\n" + text).strip()
        else:
            turns.append(NeutralTurn(
                role=role, text=text,
                timestamp=msg.get("timestamp"),
            ))

    return NeutralSession(
        source_cli="gemini",
        source_session_id=data.get("sessionId") or p.stem,
        cwd=None,  # Gemini doesn't store cwd in the session file
        started_at=data.get("startTime"),
        turns=turns,
    )
