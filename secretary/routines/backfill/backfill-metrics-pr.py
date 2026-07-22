#!/usr/bin/env python3
"""Backfill pr_number/pr_url/head_branch/pr_repo on historical metrics rows (spec 019).

Espejo de backfill-metrics-billing.py. Resuelve el PR ligado a cada corrida histórica
de rutina y parcha subsystem/routines/metrics.jsonl + los *.meta.json por corrida.

Orden de resolución por fila (reusa la lógica de resolve-routine-pr.sh):
  1. BRANCH= en paths.log → match exacto de headRefName en el cache de PRs.
  2. URL pull en paths.log (última) → lookup por número/repo en el cache.
  3. Inferencia temporal: prefijo de rama desde branchHints de ROUTINE_ENRICHMENT +
     fecha de started_at; join contra PRs merged/all en [started-6h, ended+48h],
     filtrado por is_auto_pr + _pr_matches_routine.

Opcional (--with-issues): para secretary-briefing empareja el Issue diario
(label tipo:informe-diario) por createdAt ≈ started_at del día → issue_number/issue_url.

Rutinas sin PR por diseño → skip: sec-heartbeat, billing_mode == 'none' (polls
mecánicos), reuniones-scheduler. secretary-briefing entrega Issue, no PR.

Uso:
  export SECRETARY_INSTANCE=~/.secretary
  python3 $SECRETARY_CORE/secretary/routines/backfill/backfill-metrics-pr.py --dry-run --since 2026-07-01
  python3 $SECRETARY_CORE/secretary/routines/backfill/backfill-metrics-pr.py --since 2026-07-01 [--routine reuniones-update] [--with-issues]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROUTINES_ROOT = SCRIPT_DIR.parent
INSTANCE_ROOT = Path(os.path.expanduser(os.environ.get("SECRETARY_INSTANCE", "~/.secretary"))).resolve()
PORTAL_DIR = INSTANCE_ROOT / "scripts" / "portal"

# Rutinas que no abren PR — skip (mainOnly, polls mecánicos, entrega vía Issue).
SKIP_ROUTINES = {"sec-heartbeat", "reuniones-scheduler"}
ISSUE_ONLY_ROUTINES = {"secretary-briefing"}

DEFAULT_REPO = "yourusername/cowork-secretary"


def _load_aggregate_module():
    """Carga scripts/portal/aggregate.py para reusar helpers (DRY con el portal)."""
    spec = importlib.util.spec_from_file_location(
        "portal_aggregate", PORTAL_DIR / "aggregate.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load portal/aggregate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_agg = _load_aggregate_module()
is_auto_pr = _agg.is_auto_pr
_pr_matches_routine = _agg._pr_matches_routine
parse_iso_lima = _agg.parse_iso_lima


def instance_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("SECRETARY_INSTANCE", "~/.secretary"))).resolve()


def default_repo_full(inst: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(inst), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        remote = proc.stdout.strip()
    except OSError:
        remote = ""
    slug = re.sub(r"^git@github\.com:|^https://github\.com/", "", remote)
    slug = re.sub(r"\.git$", "", slug)
    return slug or DEFAULT_REPO


# ── PR cache (una llamada gh por repo, reusada por todas las filas) ────────────

_PR_CACHE: dict[str, list[dict[str, Any]]] = {}


def pr_cache(repo_full: str) -> list[dict[str, Any]]:
    if repo_full in _PR_CACHE:
        return _PR_CACHE[repo_full]
    items: list[dict[str, Any]] = []
    proc = subprocess.run(
        [
            "gh", "pr", "list", "--repo", repo_full, "--state", "all",
            "--json", "number,headRefName,createdAt,url,state,mergedAt,closedAt",
            "--limit", "1000",
        ],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode == 0:
        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, list):
                items = parsed
        except json.JSONDecodeError:
            items = []
    else:
        print(f"  [warn] gh pr list {repo_full}: {proc.stderr.strip()[:120]}", file=sys.stderr)
    _PR_CACHE[repo_full] = items
    return items


def _pr_fields(pr: dict[str, Any], repo_full: str) -> dict[str, Any]:
    slug = repo_full.split("/")[-1] if "/" in repo_full else repo_full
    return {
        "pr_number": int(pr["number"]),
        "pr_url": str(pr.get("url") or f"https://github.com/{repo_full}/pull/{pr['number']}"),
        "head_branch": str(pr.get("headRefName") or ""),
        "pr_repo": slug,
    }


# ── extracción del log ────────────────────────────────────────────────────────

_BRANCH_RE = re.compile(r"BRANCH=(\S+)")
_PULL_RE = re.compile(r"https://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)")


def extract_from_log(log_path: Path) -> tuple[str | None, tuple[str, str, int] | None]:
    """Devuelve (branch limpio, (owner, repo, number) de la última URL pull)."""
    if not log_path.is_file():
        return None, None
    text = log_path.read_text(encoding="utf-8", errors="replace")

    branch: str | None = None
    b_matches = _BRANCH_RE.findall(text)
    if b_matches:
        raw = b_matches[-1].strip().strip("\"'`")
        raw = raw.rstrip("`\"').,;")
        branch = raw or None

    pull: tuple[str, str, int] | None = None
    p_matches = _PULL_RE.findall(text)
    if p_matches:
        owner, repo, num = p_matches[-1]
        pull = (owner, repo, int(num))

    return branch, pull


# ── resolución del PR por fila ────────────────────────────────────────────────

def resolve_pr(rec: dict[str, Any], default_repo: str) -> dict[str, Any] | None:
    routine_id = str(rec.get("routine_id") or "")
    paths = rec.get("paths") or {}
    log_path = Path(str(paths.get("log") or ""))
    branch, pull = extract_from_log(log_path)

    # 1. BRANCH → match exacto en el cache del repo por defecto.
    if branch and branch != "main":
        for pr in pr_cache(default_repo):
            if str(pr.get("headRefName") or "") == branch:
                return _pr_fields(pr, default_repo)

    # 2. URL pull → lookup por número (verifica auto + match de rutina para
    #    descartar referencias a PRs hermanos que babysit deja en el log).
    if pull:
        owner, repo, num = pull
        repo_full = f"{owner}/{repo}"
        found = next((p for p in pr_cache(repo_full) if int(p.get("number", -1)) == num), None)
        if found is not None:
            head = str(found.get("headRefName") or "")
            same_repo = repo_full == default_repo
            if not same_repo or (is_auto_pr(head) and _pr_matches_routine(head, routine_id)):
                return _pr_fields(found, repo_full)
        else:
            # No está en el cache (típico cross-repo de dispatch): confiar en la URL directa.
            return {
                "pr_number": num,
                "pr_url": f"https://github.com/{repo_full}/pull/{num}",
                "head_branch": "",
                "pr_repo": repo,
            }

    # 3. Inferencia temporal: cada corrida auto abre su PROPIO PR, creado durante o
    #    poco después de su ejecución. Ventana estrecha alrededor de [started, ended]
    #    para no colapsar varias corridas horarias sobre un mismo PR. Se elige el auto
    #    PR (que matchee la rutina) cuyo createdAt esté más cerca del started_at.
    started = parse_iso_lima(str(rec.get("started_at") or ""))
    if not started:
        return None
    ended = parse_iso_lima(str(rec.get("ended_at") or "")) or started
    window_start = started - timedelta(minutes=10)
    window_end = ended + timedelta(minutes=45)

    best: dict[str, Any] | None = None
    best_dist: timedelta | None = None
    for pr in pr_cache(default_repo):
        head = str(pr.get("headRefName") or "")
        if not is_auto_pr(head) or not _pr_matches_routine(head, routine_id):
            continue
        created = parse_iso_lima(str(pr.get("createdAt") or ""))
        if not created or created < window_start or created > window_end:
            continue
        dist = abs(created - started)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = _pr_fields(pr, default_repo)
    return best


# ── issues (opcional, deliverable #3) ─────────────────────────────────────────

_ISSUE_CACHE: dict[str, list[dict[str, Any]]] = {}


def brief_issue_cache(repo_full: str, label: str) -> list[dict[str, Any]]:
    key = f"{repo_full}|{label}"
    if key in _ISSUE_CACHE:
        return _ISSUE_CACHE[key]
    items: list[dict[str, Any]] = []
    proc = subprocess.run(
        [
            "gh", "issue", "list", "--repo", repo_full, "--label", label,
            "--state", "all", "--json", "number,url,createdAt", "--limit", "200",
        ],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode == 0:
        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, list):
                items = parsed
        except json.JSONDecodeError:
            items = []
    _ISSUE_CACHE[key] = items
    return items


def resolve_issue(rec: dict[str, Any], repo_full: str, label: str) -> dict[str, Any] | None:
    started = parse_iso_lima(str(rec.get("started_at") or ""))
    if not started:
        return None
    day = started.date()
    best: dict[str, Any] | None = None
    for issue in brief_issue_cache(repo_full, label):
        created = parse_iso_lima(str(issue.get("createdAt") or ""))
        if not created or created.date() != day:
            continue
        best = {"issue_number": int(issue["number"]), "issue_url": str(issue.get("url") or "")}
        break
    return best


# ── main ──────────────────────────────────────────────────────────────────────

def _parse_started(s: str) -> datetime | None:
    return parse_iso_lima(s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2026-07-01", help="Solo filas en/después de esta fecha (started_at)")
    parser.add_argument("--routine", default=None, help="Limitar a un routine_id")
    parser.add_argument("--with-issues", action="store_true", help="También emparejar Issue diario para secretary-briefing")
    parser.add_argument("--dry-run", action="store_true", help="Reportar sin escribir")
    args = parser.parse_args()

    since = datetime.fromisoformat(args.since).date()
    inst = instance_root()
    ledger = inst / "subsystem/routines/metrics.jsonl"
    if not ledger.is_file():
        print(f"missing ledger: {ledger}", file=sys.stderr)
        return 1

    default_repo = default_repo_full(inst)

    lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
    by_id: dict[str, dict[str, Any]] = {}
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

    changed = 0
    resolved = 0
    unresolved = 0
    for rid in order:
        rec = by_id[rid]
        started = _parse_started(str(rec.get("started_at") or ""))
        if not started or started.date() < since:
            continue
        routine_id = str(rec.get("routine_id") or "")
        if args.routine and routine_id != args.routine:
            continue

        # Skips por diseño.
        if routine_id in SKIP_ROUTINES:
            continue
        if (rec.get("billing_mode") or "").lower() == "none":
            continue

        patch: dict[str, Any] = {}

        if routine_id in ISSUE_ONLY_ROUTINES:
            if args.with_issues and not rec.get("issue_number"):
                issue = resolve_issue(rec, default_repo, "tipo:informe-diario")
                if issue:
                    patch.update(issue)
        elif not rec.get("pr_number"):
            fields = resolve_pr(rec, default_repo)
            if fields:
                patch.update(fields)
                resolved += 1
            else:
                unresolved += 1

        if not patch:
            continue

        rec.update(patch)
        changed += 1
        label = patch.get("pr_number") or patch.get("issue_number")
        kind = "issue" if "issue_number" in patch else "pr"
        print(f"[patch] {rid} {routine_id} → {kind} #{label} ({patch.get('head_branch') or patch.get('issue_url', '')})")

        meta_path = Path(str((rec.get("paths") or {}).get("meta") or ""))
        if meta_path.is_file() and not args.dry_run:
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta.update(patch)
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [warn] meta patch failed {meta_path.name}: {exc}", file=sys.stderr)

    print(f"\nresolved={resolved} unresolved={unresolved} patched={changed}")

    if changed == 0:
        print("no rows needed patching")
        return 0

    if args.dry_run:
        print(f"dry-run: would patch {changed} row(s)")
        return 0

    backup = ledger.with_suffix(f".jsonl.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(ledger, backup)
    with ledger.open("w", encoding="utf-8") as f:
        for rid in order:
            f.write(json.dumps(by_id[rid], ensure_ascii=False) + "\n")
    print(f"wrote {changed} patch(es) to {ledger} (backup {backup.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
