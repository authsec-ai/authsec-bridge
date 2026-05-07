"""Write a NeutralSession as a Claude Code session JSONL.

Format (matching what Claude reads):
  - Records have type 'user' or 'assistant'
  - Each record has a `uuid`, `parentUuid`, `sessionId`, `timestamp`, `cwd`
  - Message follows {"role": ..., "content": [{"type":"text", "text": "..."}]}
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import paths
from ..model import NeutralSession
from ._render import render_turn_text, BRIDGE_BANNER


def write_claude(session: NeutralSession, cwd: str) -> tuple[Path, str]:
    new_session_id = str(uuid.uuid4())
    project_dir = paths.claude_project_dir(cwd)
    project_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_dir / f"{new_session_id}.jsonl"

    now_iso = datetime.now(timezone.utc).isoformat()

    records = []
    parent: str | None = None

    def _push(role: str, text: str) -> None:
        nonlocal parent
        rec_uuid = str(uuid.uuid4())
        rec = {
            "parentUuid": parent,
            "isSidechain": False,
            "type": role,
            "timestamp": now_iso,
            "sessionId": new_session_id,
            "cwd": str(cwd),
            "version": "session-bridge/0.0.1",
            "uuid": rec_uuid,
            "message": {
                "role": role,
                "content": [{"type": "text", "text": text}],
            },
        }
        records.append(rec)
        parent = rec_uuid

    # Banner (system-style note delivered as a user turn so models read it)
    _push("user", BRIDGE_BANNER)

    for t in session.turns:
        body = render_turn_text(t)
        if not body:
            continue
        _push(t.role if t.role in ("user", "assistant") else "user", body)

    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return out_path, new_session_id
