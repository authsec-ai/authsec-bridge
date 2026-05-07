"""Neutral intermediate representation for cross-CLI sessions.

Every parser turns a CLI-specific session file into a NeutralSession.
Every writer turns a NeutralSession into a CLI-specific session file.

Tool calls from the source CLI are NOT preserved structurally — they are
flattened into prose under the assistant turn that issued them, because each
CLI has its own tool registry and re-injecting structured tool calls under
a different model usually causes load errors.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


Role = Literal["user", "assistant", "system"]


@dataclass
class NeutralTurn:
    """One conversational turn in the neutral format.

    `tool_summaries` is a list of human-readable lines describing what tools
    the assistant ran during this turn (e.g. "edited foo.py:42-48",
    "ran `pytest`"). They get rendered as prose when writing into a target
    CLI that doesn't share the source CLI's tool definitions.
    """
    role: Role
    text: str
    tool_summaries: list[str] = field(default_factory=list)
    timestamp: Optional[str] = None  # ISO 8601 if known


@dataclass
class NeutralSession:
    source_cli: str                    # 'claude' | 'codex' | 'gemini'
    source_session_id: str
    cwd: Optional[str] = None
    started_at: Optional[str] = None
    turns: list[NeutralTurn] = field(default_factory=list)

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
