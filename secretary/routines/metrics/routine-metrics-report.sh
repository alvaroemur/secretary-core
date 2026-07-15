#!/usr/bin/env bash
# Resumen de métricas de rutinas desde metrics.jsonl
# Uso: routine-metrics-report.sh [días] [routine_id]
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
LEDGER="$("$ROUTINES_ROOT/routines-log-dir.sh")/metrics.jsonl"
DAYS="${1:-7}"
FILTER="${2:-}"

if [[ ! -f "$LEDGER" ]]; then
  echo "Sin corridas registradas: $LEDGER"
  exit 0
fi

python3 - "$LEDGER" "$DAYS" "$FILTER" <<'PY'
import json, sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ledger, days, filt = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
cutoff = datetime.now().astimezone() - timedelta(days=days)

by_routine = defaultdict(lambda: {
    "runs": 0, "ok": 0, "err": 0, "tokens": 0, "tools": 0,
    "duration_ms": 0, "cost_usd": 0.0,
})

for line in ledger.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    if filt and r.get("routine_id") != filt:
        continue
    try:
        started = datetime.fromisoformat(r["started_at"])
    except Exception:
        continue
    if started < cutoff:
        continue
    rid = r.get("routine_id", "?")
    b = by_routine[rid]
    b["runs"] += 1
    if r.get("status") == "success" and r.get("exit_code") == 0:
        b["ok"] += 1
    else:
        b["err"] += 1
    t = r.get("tokens") or {}
    b["tokens"] += int(t.get("total") or 0)
    b["tools"] += int((r.get("tools") or {}).get("total") or 0)
    b["duration_ms"] += int(r.get("duration_ms") or 0)
    b["cost_usd"] += float((r.get("cost") or {}).get("estimated_usd") or 0)

print(f"## Rutinas — últimos {days} días" + (f" · {filt}" if filt else ""))
print()
print("| Rutina | Runs | OK | Err | Tokens | Tools | Duración (min) | Est. USD |")
print("|--------|------|----|-----|--------|-------|----------------|----------|")
tot = {"runs": 0, "ok": 0, "err": 0, "tokens": 0, "tools": 0, "duration_ms": 0, "cost_usd": 0.0}
for rid in sorted(by_routine):
    b = by_routine[rid]
    mins = b["duration_ms"] / 60000
    print(f"| {rid} | {b['runs']} | {b['ok']} | {b['err']} | {b['tokens']:,} | {b['tools']} | {mins:.1f} | ${b['cost_usd']:.3f} |")
    for k in tot:
        tot[k] += b[k]
print(f"| **TOTAL** | {tot['runs']} | {tot['ok']} | {tot['err']} | {tot['tokens']:,} | {tot['tools']} | {tot['duration_ms']/60000:.1f} | ${tot['cost_usd']:.3f} |")
print()
print("_Costo = estimación API equivalente (plan Cursor → proxy Kimi en model-pricing.json)_")
PY
