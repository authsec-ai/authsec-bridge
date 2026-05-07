"""Command-line entry: `session-bridge` (alias `sb`).

Subcommands:
  list                                     show recent sessions across all CLIs
  list --from claude                       show only Claude
  show --from claude --session <id|prefix>  show parsed turns
  transfer --from claude --to codex [--session <id>] [--cwd <path>]
                                           bridge a session into target's history

If --session is omitted, the most recent session in --from is used.
If --cwd is omitted, the current working directory is used.
"""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from . import discover
from .parsers import parse
from .writers import write


SUPPORTED = ("claude", "codex", "gemini")
SUPPORTED_TARGETS = ("claude", "codex", "gemini", "markdown")


def _fmt_age(p: Path) -> str:
    import time
    delta = time.time() - p.stat().st_mtime
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    return f"{int(delta / 86400)}d ago"


def cmd_list(args) -> int:
    targets = [args.from_cli] if args.from_cli else list(SUPPORTED)
    cwd = args.cwd or None
    for cli in targets:
        try:
            files = discover.list_sessions(cli, cwd)
        except Exception as e:
            print(f"[{cli}] error: {e}", file=sys.stderr)
            continue
        print(f"\n== {cli} ({len(files)} sessions) ==")
        for f in files[: args.limit]:
            print(f"  {_fmt_age(f):>10}  {f.name}  ({f.stat().st_size:,} bytes)")
            print(f"             {f}")
    return 0


def cmd_show(args) -> int:
    cwd = args.cwd or None
    path = discover.find_session(args.from_cli, args.session, cwd)
    if path is None:
        print(f"No session found for {args.from_cli}" + (f" matching {args.session!r}" if args.session else ""), file=sys.stderr)
        return 1
    ns = parse(args.from_cli, path)
    print(f"Source: {ns.source_cli}  id={ns.source_session_id}")
    print(f"CWD:    {ns.cwd or '(unknown)'}")
    print(f"Turns:  {len(ns.turns)}")
    print()
    for i, t in enumerate(ns.turns):
        print(f"--- [{i}] {t.role} ---")
        print((t.text or "").splitlines()[0][:160] if t.text else "(no text)")
        if t.tool_summaries:
            print(f"  +{len(t.tool_summaries)} tool calls")
    return 0


def cmd_transfer(args) -> int:
    cwd = args.cwd or os.getcwd()
    src_path = discover.find_session(args.from_cli, args.session, cwd)
    if src_path is None:
        print(f"No source session found for {args.from_cli}" + (f" matching {args.session!r}" if args.session else ""), file=sys.stderr)
        print("Hint: run `session-bridge list --from " + args.from_cli + "` to see what's available.", file=sys.stderr)
        return 1

    print(f"Reading source: {src_path}")
    ns = parse(args.from_cli, src_path)
    print(f"  parsed {len(ns.turns)} turns; cwd in source: {ns.cwd or '(unknown)'}")

    out_path, new_id = write(args.to_cli, ns, cwd)
    print(f"\nBridged into {args.to_cli}:")
    print(f"  {out_path}")
    print(f"  session id: {new_id}")

    hints = {
        "claude":   f"  start Claude in this folder; the session will appear in `/resume`.",
        "codex":    f"  cd into the cwd and run `codex resume {new_id}` (or `codex resume --all` to pick).",
        "gemini":   (
            f"  cd into the cwd and run `gemini --resume {new_id}`.\n"
            "  (If the chat picker shows the entry but resume crashes, fall back to\n"
            "  the markdown target: `sb transfer --to markdown --cwd <project>`.)"
        ),
        "markdown": (
            "  Open the new CLI in this cwd and tell it:\n"
            '    "read HANDOFF.md and continue from where the user last spoke."\n'
            "  Works in any CLI (Claude, Codex, Gemini, Cursor, Copilot, etc.)."
        ),
    }
    print(hints.get(args.to_cli, ""))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="session-bridge", description="Bridge sessions between Claude / Codex / Gemini CLIs.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list recent sessions")
    pl.add_argument("--from", dest="from_cli", choices=SUPPORTED, help="show only this CLI")
    pl.add_argument("--cwd", help="filter to this working directory (Claude+Gemini only)")
    pl.add_argument("--limit", type=int, default=10)
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("show", help="show parsed turns of a session")
    ps.add_argument("--from", dest="from_cli", choices=SUPPORTED, required=True)
    ps.add_argument("--session", help="session id or filename substring (default: most recent)")
    ps.add_argument("--cwd", help="restrict search to this cwd")
    ps.set_defaults(func=cmd_show)

    pt = sub.add_parser("transfer", help="bridge a session from one CLI into another")
    pt.add_argument("--from", dest="from_cli", choices=SUPPORTED, required=True)
    pt.add_argument("--to", dest="to_cli", choices=SUPPORTED_TARGETS, required=True)
    pt.add_argument("--session", help="source session id or substring (default: latest)")
    pt.add_argument("--cwd", help="target cwd to register the new session under (default: current)")
    pt.set_defaults(func=cmd_transfer)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
