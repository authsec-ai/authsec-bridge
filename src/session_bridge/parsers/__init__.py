"""Parsers — read a CLI-specific session file, return a NeutralSession.

Each parser strips structural tool calls but keeps a one-line prose summary
of every tool invocation, so the bridged session preserves *what was done*
without trying to replay tool calls under a different CLI's tool registry.
"""

from .claude_parser import parse_claude
from .codex_parser import parse_codex
from .gemini_parser import parse_gemini


def parse(source_cli: str, path):
    if source_cli == "claude":
        return parse_claude(path)
    if source_cli == "codex":
        return parse_codex(path)
    if source_cli == "gemini":
        return parse_gemini(path)
    raise ValueError(f"unknown source CLI: {source_cli!r}")
