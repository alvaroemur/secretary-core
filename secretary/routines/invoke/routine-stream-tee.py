#!/usr/bin/env python3
"""Lee stream-json del agent CLI; guarda JSONL crudo y emite log legible en vivo."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _tool_name(evt: dict[str, Any]) -> str:
    tc = evt.get("tool_call") or {}
    for key in tc:
        if key.endswith("ToolCall"):
            return key.replace("ToolCall", "")
    return "unknown"


def _tool_summary(evt: dict[str, Any]) -> str:
    subtype = evt.get("subtype", "")
    name = _tool_name(evt)
    tc = evt.get("tool_call") or {}
    inner = next((tc[k] for k in tc if k.endswith("ToolCall")), {})
    if name == "shell":
        cmd = (inner.get("args") or {}).get("command", "")
        if subtype == "started":
            return f"[tool] shell → {cmd[:120]}"
        exit_code = ((inner.get("result") or {}).get("success") or {}).get("exitCode")
        return f"[tool] shell ✓ exit={exit_code}"
    if subtype == "started":
        desc = inner.get("description") or evt.get("description") or ""
        return f"[tool] {name} {desc[:80]}".strip()
    return f"[tool] {name} ✓"


def _assistant_text(evt: dict[str, Any]) -> str:
    msg = evt.get("message") or {}
    parts: list[str] = []
    for block in msg.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = (block.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: routine-stream-tee.py <output.jsonl>", file=sys.stderr)
        return 2

    out_path = Path(sys.argv[1])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as raw:
        for line in sys.stdin:
            raw.write(line)
            raw.flush()
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                print(line, flush=True)
                continue

            etype = evt.get("type")
            if etype == "assistant":
                text = _assistant_text(evt)
                if text:
                    print(text, flush=True)
            elif etype == "tool_call":
                print(_tool_summary(evt), flush=True)
            elif etype == "result":
                usage = evt.get("usage") or {}
                dur = evt.get("duration_ms")
                print(
                    f"[result] {evt.get('subtype')} duration_ms={dur} "
                    f"in={usage.get('inputTokens')} out={usage.get('outputTokens')} "
                    f"cache_read={usage.get('cacheReadTokens')}",
                    flush=True,
                )
            elif etype == "system" and evt.get("subtype") == "init":
                print(
                    f"[init] model={evt.get('model')} api={evt.get('apiKeySource')} "
                    f"session={evt.get('session_id')}",
                    flush=True,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
