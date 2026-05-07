"""Writers — turn a NeutralSession into a CLI-specific session file on disk.

Each writer:
  - generates a fresh session UUID
  - writes the new file under the target CLI's session folder
  - returns the path written and the new session UUID
"""

from .claude_writer import write_claude
from .codex_writer import write_codex
from .gemini_writer import write_gemini
from .markdown_writer import write_markdown


def write(target_cli: str, session, cwd):
    if target_cli == "claude":
        return write_claude(session, cwd)
    if target_cli == "codex":
        return write_codex(session, cwd)
    if target_cli == "gemini":
        return write_gemini(session, cwd)
    if target_cli == "markdown":
        return write_markdown(session, cwd)
    raise ValueError(f"unknown target CLI: {target_cli!r}")
