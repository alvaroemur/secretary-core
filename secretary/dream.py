"""Wrapper for the instance's sec-dream deterministic collector (spec 020 FR-19).

`scripts/dream/collect.py` lives in the instance (data/config side), not in this
package — it reads instance-specific paths via `.secretary.yml`. This module just
resolves that script and shells out to it, the same pattern used for
`routines setup`'s `install-routine-schedule.sh`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from secretary.config import instance_root


def run_collect(write_collect: bool = False) -> int:
    """Invoke the instance's scripts/dream/collect.py, forwarding stdout/stderr."""
    script = instance_root() / "scripts" / "dream" / "collect.py"
    if not script.is_file():
        print(f"dream collect: no existe {script}", file=sys.stderr)
        return 2

    cmd = [sys.executable, str(script)]
    if write_collect:
        cmd.append("--write-collect")

    result = subprocess.run(cmd)
    return result.returncode


def run_emit_metrics(since: str | None = None, dry_run: bool = False) -> int:
    """Append this sec-dream run to the routines ledger (issue #24 / spec 019).

    sec-dream runs natively as a Claude Code scheduled task — it has no
    invoke-*.sh subprocess/JSONL stream for `parse-routine-metrics.py` to
    parse, so it can't emit forward the way api-cron/cursor-cron do. Instead
    of reimplementing session-transcript parsing here, shell out to the
    instance's `backfill-metrics-claude-sessions.py`, scoped to routine
    `sec-dream` and today — it already knows how to read Claude session
    transcripts (marker `<scheduled-task name="sec-dream">`) and is
    idempotent on `session_id`/`run_id`.
    """
    script = instance_root() / "scripts" / "routines" / "backfill-metrics-claude-sessions.py"
    if not script.is_file():
        print(f"dream emit-metrics: no existe {script}", file=sys.stderr)
        return 2

    if since is None:
        since = datetime.now(ZoneInfo("America/Lima")).date().isoformat()

    cmd = [sys.executable, str(script), "--since", since, "--routine", "sec-dream"]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd)
    return result.returncode


# Reportes de la propia corrida: no son trabajo que una sesión pueda pisar.
REPORT_PREFIX = 'subsystem/dream/'
ENTREGA_MARK = re.compile(r'<!--\s*dream:entrega\s+(\{.*?\})\s*-->', re.S)


def entrega_meta(body: str) -> dict:
    """Metadato `<!-- dream:entrega {...} -->` del body: tipo, compromiso, verificación."""
    match = ENTREGA_MARK.search(body or '')
    if not match:
        return {}
    try:
        meta = json.loads(match.group(1))
    except ValueError:
        return {}
    return meta if isinstance(meta, dict) else {}


def open_dream_prs(repos: list[dict], run=subprocess.run) -> list[dict]:
    """PRs abiertos con rama `dream/*` en los repos de `dispatch.executor.repos`."""
    fields = 'number,title,url,headRefName,files,createdAt,reviews,reviewDecision,body'
    prs = []
    for entry in repos:
        result = run(['gh', 'pr', 'list', '--repo', entry['repo'], '--state', 'open',
                      '--limit', '100', '--json', fields], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"dream open-prs: {entry['repo']}: {result.stderr.strip()}", file=sys.stderr)
            continue
        for pr in json.loads(result.stdout or '[]'):
            if not pr.get('headRefName', '').startswith('dream/'):
                continue
            prs.append({
                'repo': entry['repo'], 'path': entry.get('path'), 'number': pr['number'],
                'title': pr.get('title', ''), 'url': pr.get('url', ''), 'branch': pr['headRefName'],
                'created_at': pr.get('createdAt'),
                'reviewed': bool(pr.get('reviews') or pr.get('reviewDecision')),
                'files': [f['path'] for f in pr.get('files') or []
                          if not f['path'].startswith(REPORT_PREFIX)],
                'entrega': entrega_meta(pr.get('body', '')),
            })
    return prs


def run_open_prs(write: bool = False) -> int:
    """Lista los PRs abiertos de dream; con `write`, refresca la caché que lee el hook U9."""
    from secretary.config import dispatch_executor_repos
    from secretary.dream_hook import cache_path

    prs = open_dream_prs(dispatch_executor_repos())
    data = {'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'unreviewed': sum(not pr['reviewed'] for pr in prs), 'prs': prs}
    if write:
        path = cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        tmp.replace(path)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0
