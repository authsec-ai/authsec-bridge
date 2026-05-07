"""Write a NeutralSession as a Codex CLI rollout JSONL.

Codex's session pipeline (verified empirically on 0.128):
  1. Rollout file at ~/.codex/sessions/<Y>/<M>/<D>/rollout-<ts>-<uuid>.jsonl
       - First line: {"type":"session_meta","payload":{"id":..., "cwd":..., "timestamp":...}}
       - Then: {"type":"response_item","payload":{
            "type":"message", "role":"user|assistant",
            "content":[{"type":"input_text"|"output_text", "text":"..."}]}}
  2. Legacy index ~/.codex/session_index.jsonl (older versions read this)
  3. PRIMARY: ~/.codex/state_5.sqlite  -> threads table
       Codex's `resume` picker reads from this. Without a row here whose
       title is non-empty AND has_user_event=1, the session won't appear.
"""

from __future__ import annotations
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import paths
from ..model import NeutralSession
from ._render import render_turn_text, BRIDGE_BANNER


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_codex(session: NeutralSession, cwd: str) -> tuple[Path, str]:
    new_session_id = str(uuid.uuid4())
    out_path = paths.codex_session_path_for_now(new_session_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ts = _now()
    records = []

    # session_meta
    records.append({
        "timestamp": ts,
        "type": "session_meta",
        "payload": {
            "id": new_session_id,
            "timestamp": ts,
            "cwd": str(cwd),
            "originator": "session_bridge",
            "cli_version": "session-bridge/0.0.1",
            "source": "session_bridge",
        },
    })

    def _msg(role: str, text: str, content_type: str) -> dict:
        return {
            "timestamp": _now(),
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": role,
                "content": [{"type": content_type, "text": text}],
            },
        }

    # Banner as a developer-style user message
    records.append(_msg("user", BRIDGE_BANNER, "input_text"))

    for t in session.turns:
        body = render_turn_text(t)
        if not body:
            continue
        if t.role == "assistant":
            records.append(_msg("assistant", body, "output_text"))
        else:
            records.append(_msg("user", body, "input_text"))

    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Compute a thread title from the first plain-prose user turn
    title = _best_title(session)

    # Two registrations so the session shows up across Codex versions:
    #   - Legacy JSONL index (older Codex)
    #   - state_5.sqlite threads table (current Codex picker)
    _append_to_session_index(new_session_id, ts, title)
    _insert_thread_row(
        session_id=new_session_id,
        rollout_path=out_path,
        cwd=cwd,
        title=title,
    )

    return out_path, new_session_id


def _best_title(session: NeutralSession) -> str:
    """Extract a clean title from the first prose-y user turn.
    Strips IDE metadata wrappers (Claude/Codex prepend these) and skips the
    bridge banner itself."""
    import re as _re
    for t in session.turns:
        if t.role != "user" or not t.text:
            continue
        # Skip the bridge banner — it's noise we added, not real user content
        if "[session-bridge]" in t.text or "session-bridge" in t.text[:30]:
            continue
        stripped = _re.sub(r"<ide_selection>.*?</ide_selection>", "", t.text, flags=_re.DOTALL)
        stripped = _re.sub(r"<ide_opened_file>.*?</ide_opened_file>", "", stripped, flags=_re.DOTALL)
        stripped = _re.sub(r"<environment_context>.*?</environment_context>", "", stripped, flags=_re.DOTALL)
        stripped = _re.sub(r"<system-reminder>.*?</system-reminder>", "", stripped, flags=_re.DOTALL)
        for line in stripped.splitlines():
            line = line.strip()
            if line and not line.startswith("<") and "[session-bridge]" not in line:
                return line[:60]
    return f"Bridged from {session.source_cli}"


def _append_to_session_index(session_id: str, timestamp: str, title: str) -> None:
    """Legacy index ~/.codex/session_index.jsonl (older Codex versions read this)."""
    idx_path = paths.codex_root() / "session_index.jsonl"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": session_id,
        "thread_name": title,
        "updated_at": timestamp,
    }
    with idx_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _insert_thread_row(session_id: str, rollout_path: Path, cwd: str, title: str) -> None:
    """Register the bridged session in Codex's primary picker DB.

    Codex 0.128+ reads `~/.codex/state_5.sqlite -> threads` for the resume
    picker. Rows must have `title != ''` and `has_user_event == 1` to be
    visible. If Codex auto-inserted a row for this session_id (because we
    invoked `codex resume <uuid>` once already), we UPDATE that row in place;
    otherwise we INSERT a new one.
    """
    db_path = paths.codex_root() / "state_5.sqlite"
    if not db_path.exists():
        return  # no state DB yet → nothing to register; user hasn't run Codex

    now_s = int(time.time())
    now_ms = int(time.time() * 1000)

    # Codex stores cwd with a Windows extended-length prefix when it normalizes
    # paths internally. Replicate the same shape so picker filtering by cwd
    # works for `codex resume` (which auto-filters by current directory).
    cwd_str = str(cwd).replace("/", "\\")
    if not cwd_str.startswith("\\\\?\\"):
        cwd_norm = "\\\\?\\" + cwd_str
    else:
        cwd_norm = cwd_str

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM threads WHERE id = ?", (session_id,))
            exists = cur.fetchone() is not None
            if exists:
                cur.execute(
                    """
                    UPDATE threads
                    SET title = ?,
                        first_user_message = ?,
                        has_user_event = 1,
                        updated_at = ?,
                        updated_at_ms = ?,
                        rollout_path = ?,
                        cli_version = COALESCE(NULLIF(cli_version, ''), 'session-bridge/0.0.1')
                    WHERE id = ?
                    """,
                    (title, title, now_s, now_ms, str(rollout_path), session_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO threads (
                        id, rollout_path, created_at, updated_at, source,
                        model_provider, cwd, title, sandbox_policy,
                        approval_mode, tokens_used, has_user_event, archived,
                        cli_version, first_user_message, memory_mode,
                        created_at_ms, updated_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 0, ?, ?, 'enabled', ?, ?)
                    """,
                    (
                        session_id, str(rollout_path), now_s, now_s, "session_bridge",
                        "openai", cwd_norm, title,
                        '{"type":"workspace-write","writable_roots":[],"network_access":false,"exclude_tmpdir_env_var":false,"exclude_slash_tmp":false}',
                        "on-request",
                        "session-bridge/0.0.1", title, now_ms, now_ms,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.OperationalError:
        # If Codex is running, the DB may be locked. Best-effort: skip.
        # The session_index.jsonl entry still works as a fallback.
        pass
