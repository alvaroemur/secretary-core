#!/usr/bin/env python3
"""OpenAI-compatible tool loop for api-cron routines (spec 016 phase 1b)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROUTINES_ROOT = SCRIPT_DIR.parent
METRICS_DIR = ROUTINES_ROOT / "metrics"
for _p in (SCRIPT_DIR, METRICS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from api_usage import accumulate_usage, provider_cost_usd, result_usage_payload  # noqa: E402

MAX_ITERATIONS = int(os.environ.get("ROUTINES_API_TOOL_LOOP_MAX", "50"))
SHELL_TIMEOUT = int(os.environ.get("ROUTINES_API_SHELL_TIMEOUT", "300"))

ALLOWED_PREFIXES = (
    "gh ",
    "gog ",
    "secretary ",
    "git ",
    "python3 ",
    "curl ",
    "jq ",
    "launchctl ",
    "date ",
    "echo ",
    "head ",
    "tail ",
    "cat ",
    "ls ",
    "wc ",
    "grep ",
    "rg ",
    "find ",
    "mkdir ",
    "chmod ",
    "which ",
    "test ",
    "mktemp ",
    "tee ",
    "cp ",
    "mv ",
    "touch ",
    "pwd ",
    "true ",
    "false ",
    "env ",
    "printf ",
)

DANGEROUS_PATTERNS = (
    re.compile(r"\bsudo\b"),
    re.compile(r"\brm\s+-rf\s+[/~]"),
    re.compile(r"\beval\b"),
    re.compile(r">\s*/dev/sd"),
    re.compile(r"(?:curl|wget)\s+[^\n|]*\|\s*(?:ba)?sh"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+if="),
)

SEGMENT_SPLIT = re.compile(r"\s*(?:&&|;|\|)\s*")

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a shell command in the routine workspace. "
                "Prefer git -C <dir> instead of cd. Use cwd for working directory. "
                "Allowed: gh, gog, secretary, git, python3, curl, jq, and read-only utils."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Single-line shell command (chains with && ok).",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (default: workspace).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write text content to a file. Prefer this over shell redirects/heredocs. "
                "Paths must be under the workspace or a /tmp secretary worktree."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or workspace-relative file path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
]


def _default_model(model: str) -> str:
    if not model or model == "auto":
        return "minimax/minimax-m2.7"
    return model


def _write_jsonl(path: str, event: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _dangerous(command: str) -> bool:
    return any(p.search(command) for p in DANGEROUS_PATTERNS)


def _assignment_only(segment: str) -> bool:
    seg = segment.strip()
    if not seg or "=" not in seg:
        return False
    if seg.startswith("export "):
        seg = seg[7:].strip()
    # VAR=value or VAR=$(cmd)
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg))


def _cd_only(segment: str) -> bool:
    seg = segment.strip()
    if not seg.startswith("cd "):
        return False
    target = seg[3:].strip()
    if not target or ";" in target or "|" in target:
        return False
    return True


def _segment_allowed(segment: str) -> bool:
    seg = segment.strip()
    if not seg:
        return True
    if _assignment_only(seg) or _cd_only(seg):
        return True
    if _dangerous(seg):
        return False
    if seg.startswith("python3 "):
        rest = seg[8:].strip()
        if rest.startswith("-c "):
            return "\n" not in seg
        if rest.startswith("/tmp/") or rest.startswith("/private/tmp/"):
            return True
        return True
    return any(seg.startswith(p) for p in ALLOWED_PREFIXES)


def _command_allowed(command: str) -> bool:
    cmd = command.strip()
    if not cmd or "\n" in cmd:
        return False
    if _dangerous(cmd):
        return False
    segments = SEGMENT_SPLIT.split(cmd)
    return all(_segment_allowed(s) for s in segments)


def _resolve_write_path(path: str, workspace: str) -> Path | None:
    raw = Path(path).expanduser()
    ws = Path(workspace).expanduser().resolve()
    resolved = (raw if raw.is_absolute() else ws / raw).resolve()
    return resolved


def _write_allowed(path: Path, workspace: str, routine_id: str) -> bool:
    path_str = str(path)
    ws = Path(workspace).expanduser().resolve()

    if ".git/" in path_str or path.name == ".env":
        return False

    if routine_id == "sec-heartbeat":
        hb = ws / "subsystem" / "heartbeat"
        try:
            path.relative_to(hb)
            return True
        except ValueError:
            return False

    if re.search(r"/(?:private/)?tmp/[^/]*/secretary-", path_str):
        return True

    try:
        path.relative_to(ws)
        return True
    except ValueError:
        return False


def _write_file(path: str, content: str, workspace: str, routine_id: str) -> str:
    resolved = _resolve_write_path(path, workspace)
    if resolved is None:
        return f"ERROR: invalid path {path!r}"
    if not _write_allowed(resolved, workspace, routine_id):
        return f"ERROR: write not allowed for path {resolved}"
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {resolved}"
    except OSError as exc:
        return f"ERROR: {exc}"


def _run_shell(command: str, cwd: str) -> str:
    if not _command_allowed(command):
        return f"ERROR: command not allowed. Got: {command[:120]}"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT,
            env={**os.environ},
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            out = f"exit={proc.returncode}\n{out}"
        return out[:16000] or "(empty output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: timeout after {SHELL_TIMEOUT}s"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def _execute_tool(name: str, args: dict[str, Any], workspace: str, routine_id: str) -> str:
    if name == "run_shell":
        return _run_shell(args.get("command", ""), args.get("cwd") or workspace)
    if name == "write_file":
        return _write_file(
            args.get("path", ""),
            args.get("content", ""),
            workspace,
            routine_id,
        )
    return f"ERROR: unknown tool {name}"


def _post_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_tool_loop(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    workspace: str,
    jsonl_path: str,
    routine_id: str = "",
) -> tuple[int, dict[str, int | float]]:
    resolved = _default_model(model)
    routine_id = routine_id or os.environ.get("SECRETARY_ROUTINE_ID", "")
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are Secretary, an autonomous operations agent running a scheduled routine. "
                "Follow the user prompt. Use run_shell for gh, gog, secretary, and git. "
                "Use write_file for creating or overwriting files (not shell heredocs). "
                "Prefer git -C <dir> <subcommand> instead of cd && git. "
                "Work in the workspace directory. Report progress clearly."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    _write_jsonl(
        jsonl_path,
        {
            "type": "system",
            "subtype": "init",
            "model": resolved,
            "apiKeySource": "apiKey",
            "runtime": "api",
            "tool_loop": True,
        },
    )

    usage: dict[str, int | float] = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
    }
    exit_code = 0

    for iteration in range(MAX_ITERATIONS):
        try:
            data = _post_chat(
                base_url=base_url,
                api_key=api_key,
                model=resolved,
                messages=messages,
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            _write_jsonl(
                jsonl_path,
                {"type": "error", "message": f"HTTP {exc.code}: {body[:500]}"},
            )
            return 1, usage
        except Exception as exc:  # noqa: BLE001
            _write_jsonl(jsonl_path, {"type": "error", "message": str(exc)})
            return 1, usage

        accumulate_usage(
            usage,
            data.get("usage") or {},
            provider_cost=provider_cost_usd(data),
        )

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        if content:
            sys.stdout.write(content)
            sys.stdout.flush()
            _write_jsonl(jsonl_path, {"type": "assistant", "text": content})

        if not tool_calls:
            break

        messages.append(message)

        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _execute_tool(name, args, workspace, routine_id)
            _write_jsonl(
                jsonl_path,
                {"type": "tool", "name": name, "args": args, "result": result[:2000]},
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{iteration}"),
                    "content": result,
                }
            )
    else:
        exit_code = 1
        _write_jsonl(jsonl_path, {"type": "error", "message": "max iterations exceeded"})

    _write_jsonl(
        jsonl_path,
        {
            "type": "result",
            "subtype": "success" if exit_code == 0 else "error",
            "is_error": exit_code != 0,
            "usage": result_usage_payload(usage),
        },
    )
    return exit_code, usage


def main() -> int:
    if len(sys.argv) != 7:
        print(
            "usage: invoke-api-tool-loop.py <base_url> <api_key> <model> "
            "<prompt_file> <jsonl_path> <workspace>",
            file=sys.stderr,
        )
        return 2

    base_url, api_key, model, prompt_file, jsonl_path, workspace = sys.argv[1:7]
    prompt = open(prompt_file, encoding="utf-8").read()
    code, _ = run_tool_loop(
        base_url=base_url,
        api_key=api_key,
        model=model,
        prompt=prompt,
        workspace=workspace,
        jsonl_path=jsonl_path,
        routine_id=os.environ.get("SECRETARY_ROUTINE_ID", ""),
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
