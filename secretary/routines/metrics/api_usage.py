#!/usr/bin/env python3
"""Normalize OpenAI-compatible / NanoGPT usage + billed cost for api-cron harnesses."""

from __future__ import annotations

from typing import Any


def extract_cache_tokens(usage: dict[str, Any]) -> tuple[int, int]:
    """Return (cache_read, cache_write) from NanoGPT / OpenAI-compat usage."""
    details = usage.get("prompt_tokens_details") or {}
    cache_read = int(
        usage.get("cache_read_input_tokens")
        or details.get("cached_tokens")
        or usage.get("cacheReadTokens")
        or 0
    )
    cache_write = int(
        usage.get("cache_creation_input_tokens")
        or usage.get("cacheWriteTokens")
        or 0
    )
    return cache_read, cache_write


def normalize_token_usage(usage: dict[str, Any]) -> dict[str, int]:
    """Map provider usage → agent JSONL convention (input = non-cached prompt).

    `prompt_tokens` includes cached tokens; CostEstimate bills input/cache separately.
    """
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    cache_read, cache_write = extract_cache_tokens(usage)
    # Anthropic-style: cached portions are not also billed at full input rate.
    input_tokens = max(0, prompt - cache_read - cache_write)
    return {
        "input": input_tokens,
        "output": output,
        "cache_read": cache_read,
        "cache_write": cache_write,
    }


def provider_cost_usd(payload: dict[str, Any]) -> float | None:
    """Billed USD from NanoGPT `x_nanogpt_pricing` when present."""
    xp = payload.get("x_nanogpt_pricing")
    if not isinstance(xp, dict):
        return None
    for key in ("costUsd", "usdCost", "cost", "amount"):
        raw = xp.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def accumulate_usage(
    totals: dict[str, int | float],
    usage: dict[str, Any],
    *,
    provider_cost: float | None = None,
) -> None:
    """Add one response's tokens (and optional billed USD) into running totals."""
    part = normalize_token_usage(usage)
    for key in ("input", "output", "cache_read", "cache_write"):
        totals[key] = int(totals.get(key) or 0) + part[key]
    if provider_cost is not None:
        totals["provider_cost_usd"] = float(totals.get("provider_cost_usd") or 0.0) + float(
            provider_cost
        )


def result_usage_payload(totals: dict[str, int | float]) -> dict[str, Any]:
    """Shape written on JSONL `type=result` for parse-routine-metrics."""
    out: dict[str, Any] = {
        "inputTokens": int(totals.get("input") or 0),
        "outputTokens": int(totals.get("output") or 0),
        "cacheReadTokens": int(totals.get("cache_read") or 0),
        "cacheWriteTokens": int(totals.get("cache_write") or 0),
    }
    if totals.get("provider_cost_usd") is not None:
        out["providerCostUsd"] = round(float(totals["provider_cost_usd"]), 8)
    return out
