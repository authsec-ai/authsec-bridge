"""Parse a Codex CLI rollout JSONL into a NeutralSession.

Record shapes we care about (from inspecting real rollouts):
  - First record: {"type":"session_meta","payload":{"id":..., "cwd":..., ...}}
  - {"type":"response_item","payload":{"type":"message","role":"user|assistant",
       "content":[{"type":"input_text"|"output_text", "text":"..."}]}}
  - {"type":"event_msg","payload":{"type":"function_call","name":..., "arguments":...}}
  - {"type":"event_msg","payload":{"type":"task_started"|...}}  -> ignore
"""

from __future__ import annotations
import json
from pathlib import Path

from ..model import NeutralSession, NeutralTurn


def _summarize_function_call(payload: dict) -> str:
    name = payload.get("name", "tool")
    args_raw = payload.get("arguments", "")
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw)
        except Exception:
            args = {"_raw": args_raw[:120]}
    else:
        args = args_raw or {}
    if name == "shell":
        cmd_list = args.get("command") or []
        cmd = " ".join(str(x) for x in cmd_list) if isinstance(cmd_list, list) else str(cmd_list)
        return f"ran `{cmd[:160]}`"
    if name == "apply_patch":
        return "applied patch"
    return f"{name} {json.dumps(args, ensure_ascii=False)[:120]}"


def parse_codex(path: str | Path) -> NeutralSession:
    p = Path(path)
    turns: list[NeutralTurn] = []
    session_id: str | None = None
    cwd: str | None = None
    started_at: str | None = None

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = rec.get("type")
            payload = rec.get("payload") or {}

            if rtype == "session_meta":
                session_id = payload.get("id") or session_id
                cwd = payload.get("cwd") or cwd
                started_at = payload.get("timestamp") or rec.get("timestamp")
                continue

            if rtype == "response_item":
                ptype = payload.get("type")
                if ptype != "message":
                    continue
                role = payload.get("role")
                if role not in ("user", "assistant"):
                    # Codex also has "developer" role messages — skip them
                    continue
                content = payload.get("content") or []
                text_parts: list[str] = []
                for item in content:
                    if item.get("type") in ("input_text", "output_text", "text"):
                        txt = (item.get("text") or "").strip()
                        if txt:
                            text_parts.append(txt)
                text = "\n\n".join(text_parts).strip()
                if not text:
                    continue
                if turns and turns[-1].role == role:
                    turns[-1].text = (turns[-1].text + "\n\n" + text).strip()
                else:
                    turns.append(NeutralTurn(
                        role=role, text=text,
                        timestamp=rec.get("timestamp"),
                    ))
                continue

            if rtype == "event_msg":
                ptype = payload.get("type")
                if ptype == "function_call":
                    summary = _summarize_function_call(payload)
                    if turns and turns[-1].role == "assistant":
                        turns[-1].tool_summaries.append(summary)
                    else:
                        # rare: tool call before any assistant text
                        turns.append(NeutralTurn(
                            role="assistant", text="",
                            tool_summaries=[summary],
                        ))
                # other event types (task_started, agent_message_delta, etc.) ignored

    return NeutralSession(
        source_cli="codex",
        source_session_id=session_id or p.stem,
        cwd=cwd,
        started_at=started_at,
        turns=turns,
    )
