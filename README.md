# relay

Bridge a coding-CLI session between **Claude Code**, **Codex CLI**, and **Gemini CLI** so you can pick up where you left off in a different tool — when you hit a rate limit, want to compare models, or just got tired of one CLI's UX.

> Status: alpha. Useful today for Claude ↔ Codex (older), Claude → Gemini, and any → Markdown. Some target-CLI integrations still being hardened (see [Compatibility](#compatibility)).

## What it does

You have a long conversation in Claude Code. Claude rate-limits you. Today you have to either wait or re-explain everything to a fresh Codex/Gemini session.

`relay` reads the on-disk session file from one CLI, transforms it into the target CLI's session format, and drops it into the target's session folder so you can `--resume` it natively.

```
~/.claude/.../session.jsonl  ─┐
~/.codex/.../rollout-...jsonl ─┼──► relay ──► fresh session in target CLI
~/.gemini/.../session-*.json  ─┘
```

## Install

```bash
git clone https://github.com/<you>/relay
cd relay
pip install -e .
```

That gives you two commands: `relay` and the shorter `r` (alias).

## Usage

### Most-common case: bridge the latest session in this folder

```bash
# In the project you're working in:
relay transfer --from claude --to codex
```

You'll see:

```
Reading source: ~/.claude/projects/.../<uuid>.jsonl
  parsed 47 turns; cwd in source: /path/to/project

Bridged into codex:
  ~/.codex/sessions/2026/05/07/rollout-<ts>-<new-uuid>.jsonl
  session id: <new-uuid>
  cd into the cwd and run `codex resume <new-uuid>` (or `codex resume --all` to pick).
```

Then in your terminal:

```bash
codex resume <new-uuid>
```

Codex opens with the conversation visible to the model. Ask it `"summarize what we discussed"` to verify.

### List recent sessions before bridging

```bash
relay list --from claude --limit 5
relay list --from codex
relay list                        # all CLIs
```

### Pick a specific session (not the latest)

```bash
relay transfer --from claude --to gemini --session bf89ae42
```

### Universal fallback: write a Markdown handoff file

When the target CLI's resume flow is too brittle to fake reliably, dump a `HANDOFF.md` and tell any CLI to read it:

```bash
relay transfer --from claude --to markdown
# Then in the new CLI:
#   "read HANDOFF.md and continue from where the user last spoke"
```

Works in **every** coding CLI (Claude, Codex, Gemini, Cursor, Copilot, future ones).

## What's preserved

| | Status |
|---|---|
| User + assistant text turns | ✅ |
| Order of conversation | ✅ |
| Working directory (so target CLI scopes correctly) | ✅ |
| One-line summaries of tool calls (`ran pytest`, `edited foo.py`) | ✅ as prose |
| **Structured tool calls / tool results** | ❌ stripped on purpose |
| **Original session UUIDs** | ❌ fresh UUID generated for the target |

Tool calls are stripped because each CLI has its own tool registry — re-injecting Claude's `Edit` call into Codex's parser breaks Codex. The new model still sees what was done in narrative form.

## Compatibility

Real testing on a Windows 11 machine running:
- Claude Code (current)
- Codex CLI 0.98.0 → 0.128.0
- Gemini CLI 0.40.0

| Direction | File written | Visible in target? | Verified context retained? |
|---|---|---|---|
| Claude → Claude | ✅ | ✅ in `/resume` | ✅ |
| Claude → Codex (≤0.122) | ✅ | ✅ in `codex resume <id>` | ✅ |
| Claude → Codex (≥0.128) | ✅ | ⚠️ picker filter mismatch (workaround below) | ✅ via direct resume |
| Claude → Gemini | ✅ | ✅ via `gemini --resume <id>` | ✅ |
| Codex → Claude | ✅ | ✅ in `/resume` | needs your test |
| Codex → Gemini | ✅ | ✅ via `gemini --resume <id>` | needs your test |
| Gemini → Claude | ✅ | ✅ in `/resume` | needs your test |
| Gemini → Codex | ✅ | ⚠️ same Codex 0.128 picker issue | ✅ via direct resume |
| any → Markdown | ✅ | ✅ universal | ✅ |

### Codex ≥0.128 picker workaround

Codex 0.128+ moved its session picker from the JSONL session-index to a SQLite database (`~/.codex/state_5.sqlite -> threads` table). `relay` writes both, but the new picker filters by criteria we haven't fully reverse-engineered yet. Two reliable workarounds today:

1. **Resume by UUID directly** (always works):
   ```bash
   codex resume <session-id-relay-printed>
   ```
2. **Use the markdown bridge instead**:
   ```bash
   relay transfer --from claude --to markdown
   # Then in Codex: read HANDOFF.md and continue
   ```

### Gemini saved-chat system

Gemini's `/chat resume <name>` reads from a git-tagged saved-chat mechanism. `relay` doesn't manipulate Gemini's git internals; instead it writes the session as an autosave file that Gemini's `--resume <id>` flag picks up directly. Use `gemini --resume <id>` (not `/chat resume <name>`).

## How it works

```
relay/
└── src/session_bridge/
    ├── model.py             # NeutralSession / NeutralTurn dataclasses
    ├── paths.py             # where each CLI stores sessions
    ├── discover.py          # list / find sessions on disk
    ├── parsers/             # per-CLI -> NeutralSession
    │   ├── claude_parser.py
    │   ├── codex_parser.py
    │   └── gemini_parser.py
    ├── writers/             # NeutralSession -> per-CLI
    │   ├── claude_writer.py
    │   ├── codex_writer.py
    │   ├── gemini_writer.py
    │   └── markdown_writer.py
    └── cli.py               # argparse entry
```

Add a new CLI by writing one parser + one writer + adding paths to `paths.py`. The neutral model is the only contract.

## What it doesn't do

- **No automatic detection of rate-limit events.** You decide when to bridge.
- **No live sync.** Snapshot at the moment of `transfer`. Subsequent activity in either CLI doesn't sync back.
- **No summarization.** A 200-turn session bridges as 200 turns. Future models will hit context limits.
- **No tool-call replay.** Bridged tool calls become prose summaries.
- **No sync server, no auth, no SaaS.** Local-only. Sessions never leave your machine.

## Privacy

`relay` reads session files from your local CLI folders, transforms them, and writes new files back to those same folders. Nothing is sent over the network. The new session contains the full text of the original conversation — keep that in mind if your CLI installations have different access policies.

## Known issues

- Codex 0.128+ picker visibility (workaround above)
- Gemini's `/chat resume <tag>` not supported (use `gemini --resume <id>`)
- 200+ turn sessions bridge fully but may overflow the target model's context window — summarization is on the roadmap

## Roadmap (not promises)

- **v0.1**: full Codex 0.128+ picker support; Gemini git-tag integration
- **v0.2**: optional LLM summarization for very long sessions before bridging
- **v0.3**: bidirectional Cursor / Copilot session formats

## Contributing

This is a small project. Bugs and "it doesn't work on my CLI version X.Y" reports are the most useful contributions. PRs welcome — the parser/writer pattern makes adding a new CLI mechanical.

## License

MIT.

## Credits

Built by [Ritam Kumar Kundu](https://github.com/<you>) while procrastinating on a different project.
