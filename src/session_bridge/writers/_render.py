"""Shared rendering: turn a NeutralTurn into a single text string.

Tool summaries are appended as a small italicized block so the new model
can see what was done without trying to replay tool calls structurally.
"""

from __future__ import annotations
from ..model import NeutralTurn


BRIDGE_BANNER = (
    "[session-bridge] This conversation was bridged from another CLI. "
    "Tool calls from the previous CLI are described in prose below. "
    "Continue from where the user last spoke; do not try to re-run those tool calls."
)


def render_turn_text(t: NeutralTurn) -> str:
    body = t.text or ""
    if t.tool_summaries:
        bullet = "\n".join(f"  - {s}" for s in t.tool_summaries)
        body = (body + "\n\n_(actions taken in the previous session:)_\n" + bullet).strip()
    return body
