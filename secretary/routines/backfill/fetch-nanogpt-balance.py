#!/usr/bin/env python3
"""Fetch NanoGPT account balance and sync subsystem/routines/billing-wallet.json.

API: POST https://nano-gpt.com/api/check-balance (x-api-key header).
Config: .secretary.yml → dispatch.routines.api.base_url, api_key_env.

Writes only balanceUsd + updatedAt. Preserves rechargedUsd, rechargedAt, provider.
rechargedAt is set manually by the owner (ISO date/datetime) for drift (019-corridas-metrics).

Usage:
  SECRETARY_INSTANCE=~/.secretary python3 $SECRETARY_CORE/secretary/routines/backfill/fetch-nanogpt-balance.py
  SECRETARY_INSTANCE=~/.secretary python3 $SECRETARY_CORE/secretary/routines/backfill/fetch-nanogpt-balance.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

WALLET_REL = "subsystem/routines/billing-wallet.json"
DEFAULT_API_BASE = "https://nano-gpt.com/api/v1"
DEFAULT_KEY_ENV = "SECRETARY_ROUTINES_API_KEY"
DEFAULT_PROVIDER = "NanoGPT"


def instance_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("SECRETARY_INSTANCE", "~/.secretary"))).resolve()


def lima_today() -> str:
    try:
        import zoneinfo

        return datetime.now(zoneinfo.ZoneInfo("America/Lima")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_secretary_config(inst: Path) -> dict[str, Any]:
    path = inst / ".secretary.yml"
    if not path.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def routines_api_config(cfg: dict[str, Any]) -> tuple[str, str]:
    api = ((cfg.get("dispatch") or {}).get("routines") or {}).get("api") or {}
    base_url = str(api.get("base_url") or DEFAULT_API_BASE)
    key_env = str(api.get("api_key_env") or DEFAULT_KEY_ENV)
    return base_url, key_env


def nanogpt_check_balance_url(api_base_url: str) -> str:
    """Map OpenAI-compatible base (…/api/v1) to balance endpoint (…/api/check-balance)."""
    base = api_base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3] + "/check-balance"
    if base.endswith("/api"):
        return base + "/check-balance"
    return "https://nano-gpt.com/api/check-balance"


def resolve_api_key(key_env: str) -> str | None:
    key = os.environ.get(key_env, "").strip()
    return key or None


def fetch_nanogpt_balance_usd(
    api_key: str,
    api_base_url: str = DEFAULT_API_BASE,
    timeout: float = 15.0,
) -> float:
    """POST /check-balance → usd_balance (raises on HTTP/parse errors)."""
    url = nanogpt_check_balance_url(api_base_url)
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    raw = body.get("usd_balance")
    if raw is None:
        raise ValueError("response missing usd_balance")
    return round(float(raw), 4)


def read_wallet_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def wallet_spent_from_snapshot(raw: dict[str, Any]) -> tuple[float | None, str | None]:
    provider = str(raw.get("provider") or DEFAULT_PROVIDER)
    for key in ("spentUsd7d", "spentUsd"):
        if raw.get(key) is not None:
            return round(float(raw[key]), 4), provider
    balance = raw.get("balanceUsd")
    recharged = raw.get("rechargedUsd")
    if balance is not None and recharged is not None:
        return round(float(recharged) - float(balance), 4), provider
    return None, None


def write_wallet_balance(path: Path, raw: dict[str, Any], balance_usd: float, updated_at: str) -> None:
    """Update balanceUsd/updatedAt only — preserves rechargedUsd, rechargedAt, provider, etc."""
    out = dict(raw)
    out["balanceUsd"] = round(balance_usd, 4)
    out["updatedAt"] = updated_at
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_billing_wallet(
    inst: Path,
    cfg: dict[str, Any] | None = None,
    *,
    write: bool = True,
    warn: Any = None,
) -> tuple[float | None, str | None]:
    """Fetch live balance, merge into billing-wallet.json, return (spentUsd, provider).

    Preserves rechargedUsd, rechargedAt, and provider. On fetch failure, falls back to file snapshot.
    """
    if warn is None:
        warn = lambda msg: print(f"wallet: {msg}", file=sys.stderr)

    path = inst / WALLET_REL
    raw = read_wallet_file(path)
    if raw is None:
        return None, None

    base_url, key_env = routines_api_config(cfg or load_secretary_config(inst))
    api_key = resolve_api_key(key_env)
    if not api_key:
        warn(f"sin {key_env} — usando snapshot en {WALLET_REL}")
        return wallet_spent_from_snapshot(raw)

    try:
        balance = fetch_nanogpt_balance_usd(api_key, base_url)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        warn(f"fetch balance HTTP {exc.code} — fallback snapshot ({detail})")
        return wallet_spent_from_snapshot(raw)
    except (urllib.error.URLError, ValueError, json.JSONDecodeError, TypeError) as exc:
        warn(f"fetch balance falló — fallback snapshot ({exc})")
        return wallet_spent_from_snapshot(raw)

    if write:
        write_wallet_balance(path, raw, balance, lima_today())
        merged = dict(raw)
        merged["balanceUsd"] = round(balance, 4)
        return wallet_spent_from_snapshot(merged)

    merged = dict(raw)
    merged["balanceUsd"] = round(balance, 4)
    return wallet_spent_from_snapshot(merged)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch NanoGPT balance into billing-wallet.json")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only; do not write file")
    parser.add_argument("--instance", help="Override SECRETARY_INSTANCE")
    args = parser.parse_args()

    inst = Path(args.instance).expanduser().resolve() if args.instance else instance_root()
    cfg = load_secretary_config(inst)
    base_url, key_env = routines_api_config(cfg)
    path = inst / WALLET_REL

    raw = read_wallet_file(path)
    if raw is None:
        print(f"wallet: no existe {path}", file=sys.stderr)
        return 1

    api_key = resolve_api_key(key_env)
    if not api_key:
        print(f"wallet: falta env {key_env}", file=sys.stderr)
        return 2

    try:
        balance = fetch_nanogpt_balance_usd(api_key, base_url)
    except Exception as exc:  # noqa: BLE001
        print(f"wallet: fetch falló — {exc}", file=sys.stderr)
        return 3

    spent, provider = wallet_spent_from_snapshot({**raw, "balanceUsd": balance})
    print(f"balanceUsd={balance:.4f} provider={provider} spentSinceRecharge={spent}")
    print(f"endpoint={nanogpt_check_balance_url(base_url)}")

    if not args.dry_run:
        write_wallet_balance(path, raw, balance, lima_today())
        print(f"wallet: wrote {path}")
    else:
        print("wallet: dry-run — no write")

    return 0


if __name__ == "__main__":
    sys.exit(main())
