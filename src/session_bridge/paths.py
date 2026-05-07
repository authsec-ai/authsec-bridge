"""Filesystem path conventions for each supported CLI.

Discovered empirically on Windows + Linux; macOS should match Linux.
If a CLI changes its layout, update only this file.
"""

from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path


def home() -> Path:
    return Path(os.path.expanduser("~"))


# ── Claude Code ──────────────────────────────────────────────────────────

def claude_root() -> Path:
    return home() / ".claude"


def claude_projects_root() -> Path:
    return claude_root() / "projects"


def claude_encode_cwd(cwd: str | os.PathLike) -> str:
    """Replicate Claude Code's project-folder naming.

    Empirical rule (Windows): every `:`, `\\`, `/`, ` ` becomes `-`.
    Drive case is preserved as-typed. So:
      C:\\Users\\Ritam Kumarb Kundu\\Desktop\\foo
        -> C--Users-Ritam-Kumarb-Kundu-Desktop-foo
    """
    import re
    raw = str(cwd)
    encoded = re.sub(r"[\\/:\s]", "-", raw)
    return encoded.rstrip("-")


def claude_project_dir(cwd: str | os.PathLike) -> Path:
    """Best-effort: Claude sometimes uppercases the drive letter, sometimes
    not. Return the first matching directory if one exists, otherwise the
    most-likely path."""
    encoded = claude_encode_cwd(cwd)
    root = claude_projects_root()
    if not root.exists():
        return root / encoded
    # Search case-insensitively
    encoded_lower = encoded.lower()
    for child in root.iterdir():
        if child.is_dir() and child.name.lower() == encoded_lower:
            return child
    return root / encoded


def claude_sessions_for_cwd(cwd: str | os.PathLike) -> list[Path]:
    d = claude_project_dir(cwd)
    if not d.exists():
        return []
    return sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


# ── Codex CLI ────────────────────────────────────────────────────────────

def codex_root() -> Path:
    return home() / ".codex"


def codex_sessions_root() -> Path:
    return codex_root() / "sessions"


def codex_session_path_for_now(session_uuid: str) -> Path:
    """Build a fresh path under sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl."""
    now = datetime.now()
    folder = codex_sessions_root() / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
    ts = now.strftime("%Y-%m-%dT%H-%M-%S")
    return folder / f"rollout-{ts}-{session_uuid}.jsonl"


def codex_all_sessions() -> list[Path]:
    root = codex_sessions_root()
    if not root.exists():
        return []
    files = list(root.rglob("rollout-*.jsonl"))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


# ── Gemini CLI ───────────────────────────────────────────────────────────

def gemini_root() -> Path:
    return home() / ".gemini"


def gemini_projects_index_path() -> Path:
    """Map of cwd (lowercased) → friendly project folder name."""
    return gemini_root() / "projects.json"


def gemini_project_folder_name(cwd: str | os.PathLike) -> str:
    """Gemini uses the project's basename (e.g. 'authsec-sales-agent') as the
    folder under tmp/ and history/. The mapping is stored in projects.json.

    If the cwd isn't yet registered, fall back to the basename — that's what
    Gemini itself does on first run."""
    cwd_str = str(cwd).replace("/", "\\").lower() if os.name == "nt" else str(cwd)
    idx = gemini_projects_index_path()
    if idx.exists():
        try:
            import json
            with idx.open("r", encoding="utf-8") as f:
                data = json.load(f)
            mapping = data.get("projects", {})
            # Try exact lowercase match first
            if cwd_str in mapping:
                return mapping[cwd_str]
            # Try case-insensitive match
            for k, v in mapping.items():
                if k.lower() == cwd_str:
                    return v
        except Exception:
            pass
    # Fallback: basename of the cwd
    return Path(cwd).name


def gemini_register_project(cwd: str | os.PathLike, friendly_name: str) -> None:
    """Add (or update) cwd → friendly_name in projects.json so Gemini's CLI
    can locate this project's saved sessions."""
    import json
    idx = gemini_projects_index_path()
    idx.parent.mkdir(parents=True, exist_ok=True)
    if idx.exists():
        try:
            with idx.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"projects": {}}
    else:
        data = {"projects": {}}

    data.setdefault("projects", {})
    # Normalize: strip whitespace, collapse separators to backslash on Windows.
    raw = str(cwd).strip()
    cwd_key = raw.replace("/", "\\").lower() if os.name == "nt" else raw
    data["projects"][cwd_key] = friendly_name
    with idx.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def gemini_chats_dir(cwd: str | os.PathLike) -> Path:
    return gemini_root() / "tmp" / gemini_project_folder_name(cwd) / "chats"


def gemini_history_dir(cwd: str | os.PathLike) -> Path:
    return gemini_root() / "history" / gemini_project_folder_name(cwd)


def gemini_sessions_for_cwd(cwd: str | os.PathLike) -> list[Path]:
    d = gemini_chats_dir(cwd)
    if not d.exists():
        return []
    return sorted(d.glob("session-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


# Legacy alias used elsewhere; keep so we don't break callers, even though we no
# longer use it for path lookup.
def gemini_project_hash(cwd: str | os.PathLike) -> str:
    return gemini_project_folder_name(cwd)


def gemini_all_sessions() -> list[Path]:
    """All chats across all project hashes — used when caller didn't supply a cwd."""
    base = gemini_root() / "tmp"
    if not base.exists():
        return []
    files = list(base.glob("*/chats/session-*.json"))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
