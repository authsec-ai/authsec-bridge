"""Write a NeutralSession as a HANDOFF.md file in the target cwd.

This is the universal fallback: every coding CLI reads project markdown by
default (CLAUDE.md, GEMINI.md, AGENTS.md, README.md). After bridging, you
just say "read HANDOFF.md and continue from there" in the new CLI.

Use this when the target CLI's session-resume mechanism is too tightly
coupled to its internal storage format (e.g. Gemini's git-tag-based
saved-chat system) to fake reliably from outside.
"""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from ..model import NeutralSession
from ._render import render_turn_text


def write_markdown(session: NeutralSession, cwd: str) -> tuple[Path, str]:
    out_path = Path(cwd) / "HANDOFF.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()

    lines: list[str] = []
    lines.append("# Session handoff")
    lines.append("")
    lines.append(
        f"_Bridged from **{session.source_cli}** session "
        f"`{session.source_session_id}` at {now_iso}._"
    )
    lines.append("")
    lines.append(
        "> Read this file end-to-end. The user was working with another CLI "
        "and switched mid-task. Tool calls from the previous CLI are described "
        "in prose; do not try to replay them. Continue from where the user "
        "last spoke."
    )
    lines.append("")
    if session.cwd:
        lines.append(f"Original cwd: `{session.cwd}`")
        lines.append("")
    lines.append(f"Total turns: **{len(session.turns)}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, t in enumerate(session.turns):
        body = render_turn_text(t)
        if not body:
            continue
        role_label = "User" if t.role == "user" else "Assistant"
        lines.append(f"## [{i}] {role_label}")
        lines.append("")
        lines.append(body)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path, str(out_path)
