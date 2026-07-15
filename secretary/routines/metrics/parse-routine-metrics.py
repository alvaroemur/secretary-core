#!/usr/bin/env python3
"""Parsea JSONL de una corrida de rutina → meta.json + append metrics.jsonl."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _load_pricing(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    yml = path.with_suffix(".yml")
    if yaml is not None and yml.is_file():
        return yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    return {"defaults": {"auto_proxy": "moonshot-v1-128k"}, "models": {}}


def _pricing_key(model_requested: str, model_resolved: str, pricing: dict[str, Any]) -> str:
    req = (model_requested or "").strip()
    res = (model_resolved or "").strip()
    models = pricing.get("models") or {}
    for candidate in (req, res):
        key = candidate.lower()
        if key in models:
            row = models[key]
            if isinstance(row, dict) and row.get("proxy"):
                return str(row["proxy"])
            return key
        if candidate in models:
            row = models[candidate]
            if isinstance(row, dict) and row.get("proxy"):
                return str(row["proxy"])
            return candidate
    if res.lower() == "auto" or req.lower() == "auto":
        return (pricing.get("defaults") or {}).get("auto_proxy", "moonshot-v1-128k")
    slug = res.replace(" ", "-").lower()
    return slug if slug in models else (pricing.get("defaults") or {}).get("auto_proxy", "moonshot-v1-128k")


def _detect_billing(init: dict[str, Any]) -> tuple[str, str]:
    """Infer billing_mode and api_key_source from JSONL init event."""
    api_src = str(init.get("apiKeySource") or "unknown")
    runtime = str(init.get("runtime") or "").lower()

    if api_src == "apiKey":
        return "api_key", api_src
    # api-cron streams: runtime=api bills via API key even if legacy init omitted apiKeySource
    if runtime == "api":
        return "api_key", api_src if api_src != "unknown" else "apiKey"
    if api_src == "login" or runtime == "cursor":
        return "cursor_plan", api_src
    if runtime == "claude":
        return "claude_sub", api_src
    return "cursor_plan", api_src


def _pr_fields_from_env() -> dict[str, Any]:
    """Optional PR linkage from resolve-routine-pr.sh / agent env."""
    fields: dict[str, Any] = {}
    num_raw = os.environ.get("ROUTINE_PR_NUMBER") or os.environ.get("PR_NUMBER")
    if num_raw:
        try:
            fields["pr_number"] = int(str(num_raw).strip())
        except ValueError:
            pass
    url = (os.environ.get("ROUTINE_PR_URL") or os.environ.get("PR_URL") or "").strip()
    if url:
        fields["pr_url"] = url
    branch = (
        os.environ.get("ROUTINE_HEAD_BRANCH")
        or os.environ.get("HEAD_BRANCH")
        or os.environ.get("SECRETARY_BRANCH")
        or ""
    ).strip()
    if branch and branch != "main":
        fields["head_branch"] = branch
    repo = (os.environ.get("ROUTINE_PR_REPO") or "").strip()
    if repo:
        fields["pr_repo"] = repo
    return fields


def _attach_pr_fields(record: dict[str, Any]) -> dict[str, Any]:
    pr = _pr_fields_from_env()
    if pr:
        record.update(pr)
    return record


def _wall_duration_ms(started_at: str, ended_at: str) -> int | None:
    """Compute wall-clock duration from ISO timestamps when JSONL omits duration_ms."""
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        return max(0, int((end - start).total_seconds() * 1000))
    except (ValueError, TypeError):
        return None


def _estimate_cost_usd(usage: dict[str, int], price_row: dict[str, Any]) -> float:
    def tier(key: str, tokens: int) -> float:
        rate = float(price_row.get(key, 0) or 0)
        return (tokens / 1_000_000) * rate

    return (
        tier("input_per_1m", int(usage.get("input", 0)))
        + tier("output_per_1m", int(usage.get("output", 0)))
        + tier("cache_read_per_1m", int(usage.get("cache_read", 0)))
        + tier("cache_write_per_1m", int(usage.get("cache_write", 0)))
    )


def _tool_name(evt: dict[str, Any]) -> str:
    tc = evt.get("tool_call") or {}
    for key in tc:
        if key.endswith("ToolCall"):
            return key.replace("ToolCall", "")
    return "unknown"


def parse_jsonl(path: Path) -> dict[str, Any]:
    init: dict[str, Any] = {}
    usage_evt: dict[str, Any] = {}
    tool_counts: dict[str, int] = {}
    tool_total = 0
    errors: list[str] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = evt.get("type")
        if etype == "system" and evt.get("subtype") == "init":
            init = evt
        elif etype == "tool_call" and evt.get("subtype") == "started":
            name = _tool_name(evt)
            tool_counts[name] = tool_counts.get(name, 0) + 1
            tool_total += 1
        elif etype == "result":
            usage_evt = evt
            if evt.get("is_error") or evt.get("subtype") != "success":
                err = evt.get("error") or evt.get("result") or evt.get("subtype")
                errors.append(str(err))

    usage_raw = usage_evt.get("usage") or {}
    usage = {
        "input": int(usage_raw.get("inputTokens") or 0),
        "output": int(usage_raw.get("outputTokens") or 0),
        "cache_read": int(usage_raw.get("cacheReadTokens") or 0),
        "cache_write": int(usage_raw.get("cacheWriteTokens") or 0),
    }
    usage["total"] = sum(usage.values())

    provider_cost: float | None = None
    raw_pc = usage_raw.get("providerCostUsd")
    if raw_pc is not None:
        try:
            provider_cost = float(raw_pc)
        except (TypeError, ValueError):
            provider_cost = None

    billing_mode, api_src = _detect_billing(init)

    return {
        "init": init,
        "usage_evt": usage_evt,
        "usage": usage,
        "provider_cost_usd": provider_cost,
        "tool_counts": tool_counts,
        "tool_total": tool_total,
        "errors": errors,
        "api_key_source": api_src,
        "billing_mode": billing_mode,
        "model_resolved": init.get("model"),
        "session_id": init.get("session_id") or usage_evt.get("session_id"),
        "request_id": usage_evt.get("request_id"),
        "duration_ms": usage_evt.get("duration_ms"),
        "duration_api_ms": usage_evt.get("duration_api_ms"),
        "status": "success" if usage_evt.get("subtype") == "success" and not usage_evt.get("is_error") else "error",
    }


def build_record(
    *,
    routine_id: str,
    run_id: str,
    started_at: str,
    ended_at: str,
    exit_code: int,
    model_requested: str,
    trigger: str,
    jsonl_path: Path,
    log_path: Path,
    meta_path: Path,
    parsed: dict[str, Any],
    pricing: dict[str, Any],
    wall_ms: int | None = None,
) -> dict[str, Any]:
    price_key = _pricing_key(model_requested, str(parsed.get("model_resolved") or ""), pricing)
    price_row = (pricing.get("models") or {}).get(price_key) or {}
    local_est = _estimate_cost_usd(parsed["usage"], price_row)
    provider_cost = parsed.get("provider_cost_usd")
    # Prefer NanoGPT billed USD when the harness captured x_nanogpt_pricing.
    if provider_cost is not None:
        cost = float(provider_cost)
        cost_note_suffix = " · providerCostUsd (NanoGPT billed)"
    else:
        cost = local_est
        cost_note_suffix = ""

    executor = os.environ.get("ROUTINES_EXECUTOR") or os.environ.get("SECRETARY_ROUTINES_EXECUTOR")
    runtime = os.environ.get("SECRETARY_RUNTIME")

    duration_ms = parsed.get("duration_ms")
    if duration_ms is None and wall_ms is not None:
        duration_ms = wall_ms
    if duration_ms is None:
        duration_ms = _wall_duration_ms(started_at, ended_at)

    cost_block: dict[str, Any] = {
        "estimated_usd": round(cost, 6),
        "pricing_proxy": price_key,
        "pricing_label": price_row.get("label"),
        "note": (
            (
                "API billing (api_key)"
                if parsed.get("billing_mode") == "api_key"
                else "Subscription proxy — API-equivalent estimate (not real spend)"
            )
            + cost_note_suffix
        ),
    }
    if provider_cost is not None:
        cost_block["provider_cost_usd"] = round(float(provider_cost), 6)
        cost_block["local_estimated_usd"] = round(local_est, 6)

    record = {
        "run_id": run_id,
        "routine_id": routine_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "executor": executor,
        "runtime": runtime,
        "duration_ms": duration_ms,
        "duration_api_ms": parsed.get("duration_api_ms"),
        "exit_code": exit_code,
        "status": parsed.get("status") if exit_code == 0 else "error",
        "model_requested": model_requested,
        "model_resolved": parsed.get("model_resolved"),
        "api_key_source": parsed.get("api_key_source"),
        "billing_mode": parsed.get("billing_mode"),
        "session_id": parsed.get("session_id"),
        "request_id": parsed.get("request_id"),
        "tokens": parsed["usage"],
        "tools": {"by_type": parsed["tool_counts"], "total": parsed["tool_total"]},
        "cost": cost_block,
        "errors": parsed.get("errors") or [],
        "trigger": trigger,
        "paths": {
            "jsonl": str(jsonl_path),
            "log": str(log_path),
            "meta": str(meta_path),
        },
    }
    return _attach_pr_fields(record)


def build_mechanical_record(
    *,
    routine_id: str,
    run_id: str,
    started_at: str,
    ended_at: str,
    exit_code: int,
    outcome: str,
    trigger: str,
    reason: str,
    jsonl_path: Path,
    log_path: Path,
    meta_path: Path,
    wall_ms: int | None = None,
) -> dict[str, Any]:
    """Ledger row for poll/scheduler runs (no LLM stream)."""
    executor = os.environ.get("ROUTINES_EXECUTOR") or os.environ.get("SECRETARY_ROUTINES_EXECUTOR")
    runtime = os.environ.get("SECRETARY_RUNTIME") or "mechanical"
    duration_ms = wall_ms if wall_ms is not None else _wall_duration_ms(started_at, ended_at)
    zero_usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0}
    status = "success" if exit_code == 0 else "error"
    record: dict[str, Any] = {
        "run_id": run_id,
        "routine_id": routine_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "executor": executor,
        "runtime": runtime,
        "duration_ms": duration_ms,
        "duration_api_ms": None,
        "exit_code": exit_code,
        "status": status,
        "outcome": outcome,
        "model_requested": "none",
        "model_resolved": None,
        "api_key_source": None,
        "billing_mode": "none",
        "session_id": None,
        "request_id": None,
        "tokens": zero_usage,
        "tools": {"by_type": {}, "total": 0},
        "cost": {
            "estimated_usd": 0.0,
            "pricing_proxy": None,
            "pricing_label": None,
            "note": "Mechanical poll — no LLM",
        },
        "errors": [reason] if reason and status == "error" else [],
        "trigger": trigger,
        "paths": {
            "jsonl": str(jsonl_path),
            "log": str(log_path),
            "meta": str(meta_path),
        },
    }
    if reason and status == "success":
        record["note"] = reason
    return _attach_pr_fields(record)


def format_summary(record: dict[str, Any]) -> str:
    t = record["tokens"]
    c = record["cost"]
    tools = record["tools"]
    return (
        f"[metrics] routine={record['routine_id']} status={record['status']} "
        f"exit={record['exit_code']} duration_ms={record.get('duration_ms')} "
        f"model={record.get('model_resolved')} ({record.get('model_requested')}) "
        f"billing={record.get('billing_mode')} "
        f"tokens in={t['input']} out={t['output']} cache_read={t['cache_read']} total={t['total']} "
        f"tools={tools['total']} est_usd=${c['estimated_usd']:.4f} "
        f"proxy={c.get('pricing_proxy')}"
    )


def main_mechanical(argv: list[str]) -> int:
    if len(argv) < 12:
        print(
            "usage: parse-routine-metrics.py --mechanical "
            "<routine_id> <run_id> <started_at> <ended_at> <exit_code> "
            "<outcome> <trigger> <reason> <jsonl> <log> <meta> [metrics_ledger] [wall_ms]",
            file=sys.stderr,
        )
        return 2

    (
        routine_id,
        run_id,
        started_at,
        ended_at,
        exit_code_raw,
        outcome,
        trigger,
        reason,
    ) = argv[0:8]
    jsonl_path = Path(argv[8])
    log_path = Path(argv[9])
    meta_path = Path(argv[10])
    ledger_path = Path(argv[11]) if len(argv) > 11 else jsonl_path.parent.parent / "metrics.jsonl"
    wall_ms = int(argv[12]) if len(argv) > 12 else None

    record = build_mechanical_record(
        routine_id=routine_id,
        run_id=run_id,
        started_at=started_at,
        ended_at=ended_at,
        exit_code=int(exit_code_raw),
        outcome=outcome,
        trigger=trigger,
        reason=reason,
        jsonl_path=jsonl_path,
        log_path=log_path,
        meta_path=meta_path,
        wall_ms=wall_ms,
    )

    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = (
        f"[metrics] routine={record['routine_id']} status={record['status']} "
        f"outcome={record.get('outcome')} exit={record['exit_code']} "
        f"duration_ms={record.get('duration_ms')} billing={record.get('billing_mode')} "
        f"trigger={record.get('trigger')}"
    )
    print(summary, flush=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n" + summary + "\n")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--mechanical":
        return main_mechanical(sys.argv[2:])

    if len(sys.argv) < 10:
        print(
            "usage: parse-routine-metrics.py <routine_id> <run_id> <started_at> "
            "<ended_at> <exit_code> <model_requested> <trigger> <jsonl> <log> <meta> "
            "[metrics_ledger] [wall_ms]",
            file=sys.stderr,
        )
        return 2

    routine_id, run_id, started_at, ended_at = sys.argv[1:5]
    exit_code = int(sys.argv[5])
    model_requested, trigger = sys.argv[6:8]
    jsonl_path = Path(sys.argv[8])
    log_path = Path(sys.argv[9])
    meta_path = Path(sys.argv[10])
    ledger_path = Path(sys.argv[11]) if len(sys.argv) > 11 else jsonl_path.parent.parent / "metrics.jsonl"
    wall_ms = int(sys.argv[12]) if len(sys.argv) > 12 else None

    script_dir = Path(__file__).resolve().parent
    pricing = _load_pricing(script_dir / "model-pricing.json")

    parsed = parse_jsonl(jsonl_path) if jsonl_path.is_file() else {
        "usage": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
        "tool_counts": {},
        "tool_total": 0,
        "errors": ["missing jsonl"],
        "status": "error",
        "billing_mode": "unknown",
        "api_key_source": "unknown",
    }

    record = build_record(
        routine_id=routine_id,
        run_id=run_id,
        started_at=started_at,
        ended_at=ended_at,
        exit_code=exit_code,
        model_requested=model_requested,
        trigger=trigger,
        jsonl_path=jsonl_path,
        log_path=log_path,
        meta_path=meta_path,
        parsed=parsed,
        pricing=pricing,
        wall_ms=wall_ms,
    )

    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = format_summary(record)
    print(summary, flush=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n" + summary + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
