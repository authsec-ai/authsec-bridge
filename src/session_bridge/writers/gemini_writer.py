"""Write a NeutralSession as a Gemini CLI session JSON.

Format (single JSON file, not JSONL):
  {
    "sessionId": "<uuid>",
    "projectHash": "<sha256>",
    "startTime": "<iso>",
    "lastUpdated": "<iso>",
    "messages": [
      {"id":"<uuid>","timestamp":"<iso>","type":"user|model","content":"..."}
    ]
  }
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import paths
from ..model import NeutralSession
from ._render import render_turn_text, BRIDGE_BANNER


def _now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_gemini(session: NeutralSession, cwd: str) -> tuple[Path, str]:
    new_session_id = str(uuid.uuid4())

    # Gemini identifies projects by the basename of the cwd (registered in
    # projects.json). Register this cwd if it isn't already, then write to the
    # tmp/<friendly>/chats/ folder.
    friendly = paths.gemini_project_folder_name(cwd)
    paths.gemini_register_project(cwd, friendly)

    project_dir = paths.gemini_root() / "tmp" / friendly
    chats_dir = project_dir / "chats"
    chats_dir.mkdir(parents=True, exist_ok=True)

    # Drop a .project_root marker (matches Gemini's own files) so the dir is
    # a recognized project.
    root_marker = project_dir / ".project_root"
    try:
        if not root_marker.exists():
            root_marker.write_text(str(cwd), encoding="utf-8")
    except Exception:
        pass

    # Mirror in history/<friendly>/ — Gemini's "/chat list" reads from here.
    history_dir = paths.gemini_history_dir(cwd)
    history_dir.mkdir(parents=True, exist_ok=True)
    hist_marker = history_dir / ".project_root"
    try:
        if not hist_marker.exists():
            hist_marker.write_text(str(cwd), encoding="utf-8")
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    fname = f"session-{now.strftime('%Y-%m-%dT%H-%M')}-{new_session_id[:8]}.json"
    out_path = chats_dir / fname

    now_iso = _now_z()

    messages = [{
        "id": str(uuid.uuid4()),
        "timestamp": now_iso,
        "type": "user",
        "content": BRIDGE_BANNER,
    }]

    for t in session.turns:
        body = render_turn_text(t)
        if not body:
            continue
        # Gemini's loader uses an exhaustive switch on `type`. The accepted
        # values for assistant turns is "gemini" (not "model" / "assistant" —
        # those crash the loader with `checkExhaustive` errors).
        gemini_type = "gemini" if t.role == "assistant" else "user"
        messages.append({
            "id": str(uuid.uuid4()),
            "timestamp": _now_z(),
            "type": gemini_type,
            "content": body,
        })

    data = {
        "sessionId": new_session_id,
        # Some old Gemini versions key on projectHash; we keep the field
        # populated with the friendly name for forward-compat.
        "projectHash": friendly,
        "startTime": now_iso,
        "lastUpdated": now_iso,
        "messages": messages,
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return out_path, new_session_id
