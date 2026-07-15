#!/usr/bin/env python3
"""OpenAI-compatible chat completions client for api-cron routines."""

from __future__ import annotations

import json
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


def _default_model(model: str) -> str:
    if not model or model == "auto":
        return "minimax/minimax-m2.7"
    return model


def _write_jsonl(path: str, event: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def stream_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    jsonl_path: str,
) -> tuple[int, dict[str, int | float]]:
    resolved = _default_model(model)
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": resolved,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Secretary, an autonomous operations agent. "
                    "Follow the user prompt exactly and report progress clearly."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    _write_jsonl(
        jsonl_path,
        {
            "type": "system",
            "subtype": "init",
            "model": resolved,
            "apiKeySource": "apiKey",
            "runtime": "api",
        },
    )

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    usage: dict[str, int | float] = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
    }
    exit_code = 0
    errors: list[str] = []

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if chunk.get("usage"):
                    # Final usage chunk replaces prior (stream emits once).
                    usage = {
                        "input": 0,
                        "output": 0,
                        "cache_read": 0,
                        "cache_write": 0,
                    }
                    accumulate_usage(
                        usage,
                        chunk["usage"],
                        provider_cost=provider_cost_usd(chunk),
                    )

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    _write_jsonl(
                        jsonl_path,
                        {"type": "assistant", "subtype": "delta", "text": content},
                    )
    except urllib.error.HTTPError as exc:
        exit_code = 1
        body = exc.read().decode("utf-8", errors="replace")
        errors.append(f"HTTP {exc.code}: {body[:500]}")
        sys.stderr.write(errors[-1] + "\n")
    except Exception as exc:  # noqa: BLE001
        exit_code = 1
        errors.append(str(exc))
        sys.stderr.write(errors[-1] + "\n")

    _write_jsonl(
        jsonl_path,
        {
            "type": "result",
            "subtype": "success" if exit_code == 0 else "error",
            "is_error": exit_code != 0,
            "usage": result_usage_payload(usage),
            "errors": errors,
        },
    )
    return exit_code, usage


def main() -> int:
    if len(sys.argv) != 6:
        print(
            "usage: invoke-api-client.py <base_url> <api_key> <model> <prompt_file> <jsonl_path>",
            file=sys.stderr,
        )
        return 2

    base_url, api_key, model, prompt_file, jsonl_path = sys.argv[1:6]
    prompt = open(prompt_file, encoding="utf-8").read()
    code, _usage = stream_chat(
        base_url=base_url,
        api_key=api_key,
        model=model,
        prompt=prompt,
        jsonl_path=jsonl_path,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
