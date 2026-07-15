#!/usr/bin/env python3
"""Re-parse JSONL init/result events to fix billing_mode / pricing on historical metrics.

Usage:
  SECRETARY_INSTANCE=~/.secretary python3 backfill-metrics-billing.py \\
    [--since YYYY-MM-DD] [--dry-run] [--calibrate-cache] [--assume-cache-frac 0.93]

Touches subsystem/routines/metrics.jsonl and per-run *.meta.json when billing or cost changes.

Cost rewrite policy (fase 6+):
  1. Prefer providerCostUsd from JSONL (NanoGPT billed) when present.
  2. Else prefer real cache_read/cache_write from JSONL + NanoGPT rate card.
  3. Else, only if --calibrate-cache / --assume-cache-frac: treat pre-fase-6
     inputTokens as full prompt and split with an evidence-based cache fraction.
     Calibration = mean cache_read/(input+cache_read) over api_key rows since
     --since that already have cache_read>0 (post-fase-6 harness). Without that
     signal, historical rows keep their CostEstimate (blind reprice worsens drift).

Re-run after pulling pricing/harness fixes:
  SECRETARY_INSTANCE=~/.secretary python3 $SECRETARY_CORE/secretary/routines/backfill/backfill-metrics-billing.py \\
    --since 2026-07-02 --calibrate-cache
  SECRETARY_INSTANCE=~/.secretary python3 scripts/portal/aggregate.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROUTINES_ROOT = SCRIPT_DIR.parent
METRICS_DIR = ROUTINES_ROOT / "metrics"

# Minimum post-fase-6 samples required before auto-calibration is trusted.
MIN_CALIBRATION_SAMPLES = 3


def _load_parser_module():
    spec = importlib.util.spec_from_file_location(
        "parse_routine_metrics", METRICS_DIR / "parse-routine-metrics.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load parse-routine-metrics.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_prm = _load_parser_module()
parse_jsonl = _prm.parse_jsonl
_load_pricing = _prm._load_pricing
_pricing_key = _prm._pricing_key
_estimate_cost_usd = _prm._estimate_cost_usd


def _parse_started(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cache_frac(tokens: dict[str, Any]) -> float | None:
    inp = int(tokens.get("input") or 0)
    cr = int(tokens.get("cache_read") or 0)
    prompt = inp + cr
    if cr <= 0 or prompt <= 0:
        return None
    return cr / prompt


def _calibrate_cache_frac(
    by_id: dict[str, dict],
    order: list[str],
    since_date,
) -> tuple[float | None, int]:
    """Mean cache hit rate from api_key rows that already recorded cache_read."""
    fracs: list[float] = []
    for rid in order:
        rec = by_id[rid]
        started = str(rec.get("started_at") or "")
        dt = _parse_started(started)
        if not dt or dt.date() < since_date:
            continue
        if rec.get("billing_mode") != "api_key":
            continue
        frac = _cache_frac(rec.get("tokens") or {})
        if frac is not None:
            fracs.append(frac)
    if len(fracs) < MIN_CALIBRATION_SAMPLES:
        return None, len(fracs)
    return sum(fracs) / len(fracs), len(fracs)


def _apply_assumed_cache(usage: dict[str, int], frac: float) -> dict[str, int]:
    """Split pre-fase-6 full-prompt inputTokens into input + cache_read."""
    prompt = int(usage.get("input") or 0) + int(usage.get("cache_read") or 0)
    out = int(usage.get("output") or 0)
    cw = int(usage.get("cache_write") or 0)
    frac = min(max(float(frac), 0.0), 0.99)
    cr = int(round(prompt * frac))
    inp = max(0, prompt - cr)
    total = inp + out + cr + cw
    return {
        "input": inp,
        "output": out,
        "cache_read": cr,
        "cache_write": cw,
        "total": total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2026-07-03", help="Only rows on/after this date (started_at)")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    parser.add_argument(
        "--calibrate-cache",
        action="store_true",
        help=(
            "For api_key rows whose JSONL lacks cache/providerCost, assume cache_read "
            f"fraction = mean of ≥{MIN_CALIBRATION_SAMPLES} post-fase-6 rows with real cache"
        ),
    )
    parser.add_argument(
        "--assume-cache-frac",
        type=float,
        default=None,
        help="Explicit cache_read/(input+cache_read) for historical api_key rows (0–0.99)",
    )
    args = parser.parse_args()

    since = datetime.fromisoformat(args.since).date()
    inst = Path(__import__("os").environ.get("SECRETARY_INSTANCE", Path.home() / ".secretary")).expanduser()
    ledger = inst / "subsystem/routines/metrics.jsonl"
    if not ledger.is_file():
        print(f"missing ledger: {ledger}", file=sys.stderr)
        return 1

    if args.assume_cache_frac is not None and not (0.0 <= args.assume_cache_frac <= 0.99):
        print("--assume-cache-frac must be in [0, 0.99]", file=sys.stderr)
        return 2

    pricing = _load_pricing(METRICS_DIR / "model-pricing.json")
    lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()

    by_id: dict[str, dict] = {}
    order: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = str(rec.get("run_id") or "")
        if not rid:
            continue
        if rid not in by_id:
            order.append(rid)
        by_id[rid] = rec

    assumed_frac: float | None = args.assume_cache_frac
    calib_n = 0
    if assumed_frac is None and args.calibrate_cache:
        assumed_frac, calib_n = _calibrate_cache_frac(by_id, order, since)
        if assumed_frac is None:
            print(
                f"calibrate-cache: only {calib_n} sample(s) with cache_read>0 "
                f"(need ≥{MIN_CALIBRATION_SAMPLES}) — historical no-cache rows will NOT be rewritten",
                file=sys.stderr,
            )
        else:
            print(
                f"calibrate-cache: frac={assumed_frac:.4f} from {calib_n} api_key row(s) "
                f"with real cache since {since.isoformat()}"
            )
    elif assumed_frac is not None:
        print(f"assume-cache-frac: {assumed_frac:.4f}")

    changed = 0
    assumed_n = 0
    for rid in order:
        rec = by_id[rid]
        started = str(rec.get("started_at") or "")
        dt = _parse_started(started)
        if not dt or dt.date() < since:
            continue

        paths = rec.get("paths") or {}
        jsonl_raw = str(paths.get("jsonl") or "")
        if not jsonl_raw:
            continue
        jsonl_path = Path(jsonl_raw)
        if not jsonl_path.is_file():
            continue

        parsed = parse_jsonl(jsonl_path)
        billing = parsed.get("billing_mode")
        api_src = parsed.get("api_key_source")
        model_req = str(rec.get("model_requested") or "")
        price_key = _pricing_key(model_req, str(parsed.get("model_resolved") or ""), pricing)
        price_row = (pricing.get("models") or {}).get(price_key) or {}
        new_tokens = dict(parsed["usage"])
        provider_cost = parsed.get("provider_cost_usd")
        old_tokens = rec.get("tokens") or {}
        old_billing = rec.get("billing_mode")
        old_cost = (rec.get("cost") or {}).get("estimated_usd")

        has_provider = provider_cost is not None
        has_cache = int(new_tokens.get("cache_read") or 0) > 0 or int(
            new_tokens.get("cache_write") or 0
        ) > 0

        # Historical JSONL: result.usage was only inputTokens+outputTokens (full prompt).
        # Prefer ledger tokens if JSONL still has zero cache (same shape).
        if (
            not has_provider
            and not has_cache
            and assumed_frac is not None
            and billing == "api_key"
            and int(old_tokens.get("cache_read") or 0) == 0
            and int(old_tokens.get("input") or 0) > 0
        ):
            base_usage = {
                "input": int(old_tokens.get("input") or new_tokens.get("input") or 0),
                "output": int(old_tokens.get("output") or new_tokens.get("output") or 0),
                "cache_read": 0,
                "cache_write": int(old_tokens.get("cache_write") or 0),
            }
            new_tokens = _apply_assumed_cache(base_usage, assumed_frac)
            has_cache = True
            assumed_n += 1
            assumed = True
        else:
            assumed = False

        local_est = round(_estimate_cost_usd(new_tokens, price_row), 6)
        rewrite_cost = has_provider or has_cache

        if has_provider:
            cost = round(float(provider_cost), 6)
            cost_note = (
                "API billing (api_key) · providerCostUsd (NanoGPT billed)"
                if billing == "api_key"
                else "Subscription proxy — providerCostUsd when present"
            )
        elif assumed:
            cost = local_est
            cost_note = (
                f"API billing (api_key) · assumed cache_read frac={assumed_frac:.4f} "
                f"(JSONL lacked cache; calibrated from post-fase-6 runs)"
            )
        elif has_cache:
            cost = local_est
            cost_note = (
                "API billing (api_key)"
                if billing == "api_key"
                else "Subscription proxy — API-equivalent estimate (not real spend)"
            )
        else:
            cost = old_cost if old_cost is not None else local_est
            cost_note = (rec.get("cost") or {}).get("note") or (
                "API billing (api_key)"
                if billing == "api_key"
                else "Subscription proxy — API-equivalent estimate (not real spend)"
            )

        cost_block = {
            **(rec.get("cost") or {}),
            "estimated_usd": cost,
            "pricing_proxy": price_key,
            "pricing_label": price_row.get("label"),
            "note": cost_note,
        }
        if has_provider:
            cost_block["provider_cost_usd"] = cost
            cost_block["local_estimated_usd"] = local_est
        if assumed and assumed_frac is not None:
            cost_block["assumed_cache_frac"] = round(float(assumed_frac), 4)
            cost_block.pop("provider_cost_usd", None)

        tokens_changed = old_tokens != new_tokens and (has_cache or assumed)
        billing_changed = old_billing != billing
        cost_changed = rewrite_cost and old_cost != cost
        if not billing_changed and not cost_changed and not tokens_changed:
            continue

        patch: dict = {
            "billing_mode": billing,
            "api_key_source": api_src,
            "model_resolved": parsed.get("model_resolved"),
        }
        if tokens_changed:
            patch["tokens"] = new_tokens
        if cost_changed or (rewrite_cost and (rec.get("cost") or {}).get("pricing_proxy") != price_key):
            patch["cost"] = cost_block
        elif billing_changed:
            patch["cost"] = {
                **(rec.get("cost") or {}),
                "pricing_proxy": price_key,
                "pricing_label": price_row.get("label"),
            }

        if not patch.get("cost") and not patch.get("tokens") and not billing_changed:
            continue

        rec.update(patch)
        changed += 1
        print(
            f"[patch] {rid} billing {old_billing!r} -> {billing!r} "
            f"cost ${old_cost} -> ${rec.get('cost', {}).get('estimated_usd')} "
            f"proxy={price_key} cache_read={new_tokens.get('cache_read', 0)} "
            f"rewrite_cost={rewrite_cost} assumed={assumed}"
        )

        meta_path = Path(str(paths.get("meta") or ""))
        if meta_path.is_file() and not args.dry_run:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta.update(patch)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if changed == 0:
        print("no rows needed patching")
        return 0

    if args.dry_run:
        print(
            f"dry-run: would patch {changed} row(s)"
            + (f" ({assumed_n} with assumed cache)" if assumed_n else "")
        )
        return 0

    backup = ledger.with_suffix(f".jsonl.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(ledger, backup)
    with ledger.open("w", encoding="utf-8") as f:
        for rid in order:
            f.write(json.dumps(by_id[rid], ensure_ascii=False) + "\n")
    print(
        f"wrote {changed} patch(es) to {ledger} (backup {backup.name})"
        + (f"; assumed_cache on {assumed_n}" if assumed_n else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
