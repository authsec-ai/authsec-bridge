"""Find existing sessions on disk for a given CLI, optionally scoped to a cwd."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from . import paths


def list_sessions(cli: str, cwd: Optional[str] = None) -> list[Path]:
    if cli == "claude":
        if cwd:
            return paths.claude_sessions_for_cwd(cwd)
        # All Claude sessions across all projects
        root = paths.claude_projects_root()
        if not root.exists():
            return []
        files = list(root.glob("*/*.jsonl"))
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    if cli == "codex":
        # Codex doesn't index by cwd, but we can post-filter by parsing meta.
        return paths.codex_all_sessions()
    if cli == "gemini":
        if cwd:
            res = paths.gemini_sessions_for_cwd(cwd)
            if res:
                return res
        return paths.gemini_all_sessions()
    raise ValueError(f"unknown CLI: {cli!r}")


def find_session(cli: str, session_id_or_prefix: Optional[str], cwd: Optional[str]) -> Optional[Path]:
    """Pick the right session file to bridge.

    - If a session id/substring is given, search ALL sessions for this CLI
      (not just those matching cwd) — user is explicitly identifying one.
    - Otherwise (no id given), restrict to the cwd to avoid grabbing an
      unrelated recent session.
    """
    if session_id_or_prefix:
        candidates = list_sessions(cli, cwd=None)
        for p in candidates:
            if session_id_or_prefix.lower() in p.name.lower():
                return p
        return None
    # No id supplied: prefer the most recent session in this cwd
    candidates = list_sessions(cli, cwd)
    if candidates:
        return candidates[0]
    # Fall back to most recent session anywhere
    candidates = list_sessions(cli, cwd=None)
    return candidates[0] if candidates else None
