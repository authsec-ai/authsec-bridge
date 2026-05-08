# authsec-bridge

Bridge a session between **Claude Code**, **Codex CLI**, and **Gemini CLI** — pick up your conversation in a different tool without re-explaining context.

## Install

```bash
git clone https://github.com/authsec-ai/authsec-bridge.git
cd authsec-bridge
python -m pip install -e .
```

Registers two commands: `session-bridge` and the shorter alias `sb`.  
If neither is recognized, use `python -m session_bridge.cli` directly.

Verify:

```bash
python -m session_bridge.cli --help
```

## Usage

### Transfer latest session

Run this command from the **authsec-bridge directory**. Use `--cwd` to point to the project where your session was started:

```bash
# Claude → Gemini
python -m session_bridge.cli transfer --from claude --to gemini --cwd "C:/Users/YourName/path/to/your-project"

# Claude → Codex
python -m session_bridge.cli transfer --from claude --to codex --cwd "C:/Users/YourName/path/to/your-project"

# Codex → Claude
python -m session_bridge.cli transfer --from codex --to claude --cwd "C:/Users/YourName/path/to/your-project"
```

Example:

```bash
python -m session_bridge.cli transfer --from claude --to gemini --cwd "C:/Users/rk/authsec-sales-agent"
```

Output prints the new session ID and the exact resume command to run.

### Resume in the target CLI

```bash
codex resume <session-id>
gemini --resume <session-id>
# Claude: use /resume inside Claude Code
```

### List recent sessions

```bash
python -m session_bridge.cli list --from claude --limit 5
python -m session_bridge.cli list --from codex
python -m session_bridge.cli list          # all CLIs
```

Example output:

```
== claude (33 sessions) ==
      1h ago  1775242a-ce89-451b-a153-88eb592918fd.jsonl  (78,936 bytes)
             C:\Users\bishn\.claude\projects\d--authnull-git-authsec-bridge\1775242a-ce89-451b-a153-88eb592918fd.jsonl
     18h ago  cd977abd-b48f-46d9-8b53-171b998cbf0f.jsonl  (189,030 bytes)
             C:\Users\bishn\.claude\projects\d--authnull-git-authsec-bridge\cd977abd-b48f-46d9-8b53-171b998cbf0f.jsonl
     18h ago  556813a3-08a6-4596-85f9-a5b9fbc138dd.jsonl  (8,443 bytes)
             C:\Users\bishn\.claude\projects\d--authnull-git-authsec-bridge\556813a3-08a6-4596-85f9-a5b9fbc138dd.jsonl
```

### Transfer a specific session (not the latest)

Copy the session ID from the list output — the filename without `.jsonl`:

```bash
python -m session_bridge.cli transfer --from claude --to gemini --session <SESSION-ID>
```

### Universal fallback: Markdown handoff

Use this when native resume is unreliable, or the target CLI isn't supported:

```bash
python -m session_bridge.cli transfer --from claude --to markdown
```

Writes `HANDOFF.md` in the current directory. Open any CLI and run:

```
read HANDOFF.md and continue from where the user last spoke
```

Works with Claude, Codex, Gemini, Cursor, Copilot, or any LLM-based tool.

## What's preserved

| Item                            | Status                                             |
| ------------------------------- | -------------------------------------------------- |
| User and assistant text turns   | ✅                                                 |
| Conversation order              | ✅                                                 |
| Working directory               | ✅                                                 |
| Tool call summaries (as prose)  | ✅                                                 |
| Structured tool calls / results | ❌ stripped — re-injecting them breaks target CLIs |
| Original session UUID           | ❌ fresh UUID generated for target                 |

## Compatibility

Tested on Windows 11:

| Direction             | Works? | Notes                               |
| --------------------- | ------ | ----------------------------------- |
| Claude → Claude       | ✅     | `/resume` in Claude Code            |
| Claude → Codex ≤0.122 | ✅     | `codex resume <id>`                 |
| Claude → Codex ≥0.128 | ⚠️     | Resume by UUID directly (see below) |
| Claude → Gemini       | ✅     | `gemini --resume <id>`              |
| Codex → Claude        | ✅     | `/resume` in Claude Code            |
| Codex → Gemini        | ✅     | `gemini --resume <id>`              |
| Gemini → Claude       | ✅     | `/resume` in Claude Code            |
| Gemini → Codex        | ⚠️     | Same Codex 0.128 issue              |
| any → Markdown        | ✅     | Universal                           |

**Codex ≥0.128:** The session picker moved to SQLite and may not show the bridged session. Resume directly by UUID — it always works:

```bash
codex resume <session-id-printed-by-sb>
```

Or use `--to markdown` as the fallback.

## Project structure

```
src/session_bridge/
├── model.py             # NeutralSession / NeutralTurn dataclasses
├── paths.py             # session storage paths per CLI
├── discover.py          # list / find sessions on disk
├── parsers/             # per-CLI → NeutralSession
│   ├── claude_parser.py
│   ├── codex_parser.py
│   └── gemini_parser.py
├── writers/             # NeutralSession → per-CLI
│   ├── claude_writer.py
│   ├── codex_writer.py
│   ├── gemini_writer.py
│   └── markdown_writer.py
└── cli.py
```

To add a new CLI: write a parser, a writer, and add its paths to `paths.py`.

## License

MIT
