"""Portable close snapshots, conservative routine gates and local usage reports.

Run with ``python -m secretary.efficiency --help``. No model calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from secretary.config import instance_root, load_config, flatten_paths

PILOTS = ('dispatch-executor', 'wiki-update', 'revision-correo')
TOKEN_KEYS = {'input': ('input_tokens', 'inputTokens'), 'output': ('output_tokens', 'outputTokens'),
              'cache_read': ('cache_read_input_tokens', 'cacheReadTokens'),
              'cache_write': ('cache_creation_input_tokens', 'cacheWriteTokens')}


def run(argv: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=90)
    if result.returncode:
        # Do not persist raw provider output (may contain private data or credentials).
        raise RuntimeError(f'{argv[0]}: fallo de consulta (exit {result.returncode})')
    return result.stdout


def query(argv: list[str]) -> Any:
    return json.loads(run(argv))


def rows(value: Any, key: str) -> list[dict]:
    if isinstance(value, list):
        result = [item for page in value for item in page] if value and all(isinstance(page, list) for page in value) else value
    elif isinstance(value, dict) and key in value and (isinstance(value[key], list) or value[key] is None):
        result = value[key] or []
    else:
        raise ValueError(f'Respuesta sin colección {key}')
    if isinstance(value, dict) and value.get('nextPageToken'):
        raise ValueError('Consulta truncada; no se puede confirmar ausencia de trabajo')
    if not all(isinstance(x, dict) for x in result):
        raise ValueError('Colección inválida')
    return result


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_inventory(root: Path, cfg: dict, keys: list[str]) -> dict[str, str]:
    paths = flatten_paths(cfg.get('paths', {}))
    result = {}
    for key in keys:
        raw = paths.get(key)
        if raw is None:
            raise ValueError(f'Falta paths.{key}')
        path = Path(os.path.expanduser(raw))
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            raise FileNotFoundError(f'Fuente ausente: paths.{key}')
        files = sorted(path.rglob('*.md')) if path.is_dir() else [path]
        for item in files:
            result[str(item)] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def routine_inventory(routine: str, root: Path, cfg: dict, now: datetime) -> tuple[Any, bool]:
    """Return an inventory and whether the full routine has mandatory work.

    Pagination exhaustion is required for a negative result. Unknown information
    never becomes a no-op. A completed checkpoint is evidence, not consent.
    """
    if routine == 'dispatch-executor':
        repos = cfg.get('dispatch', {}).get('executor', {}).get('repos', [])
        if not isinstance(repos, list):
            raise ValueError('Allowlist inválida')
        work = []
        for repo in repos:
            if not isinstance(repo, dict) or not repo.get('repo') or not repo.get('path'):
                raise ValueError('Entrada de allowlist inválida')
            found = rows(query(['gh', 'api', '--paginate', '--slurp', f"repos/{repo['repo']}/issues?state=open&labels=dispatch%3Aexecute&per_page=100"]), 'issues')
            for item in found:
                if 'pull_request' in item: continue
                labels = {x.get('name') for x in item.get('labels', [])}
                if not labels.intersection({'dispatch:running', 'dispatch:done', 'dispatch:blocked'}):
                    work.append({'repo': repo['repo'], 'number': item['number'], 'updatedAt': item.get('updated_at', item.get('updatedAt'))})
        return work, bool(work)
    if routine == 'revision-correo':
        accounts = cfg.get('accounts', {})
        names = cfg.get('account_usage', {}).get('revision_correo', [])
        if not names or any(not accounts.get(n) for n in names):
            raise ValueError('Cuentas de correo incompletas')
        inv = {'accounts': {}, 'day': now.date().isoformat()}
        has_work = now.weekday() == 4  # Keep the Friday weekly report.
        for name in names:
            account = accounts[name]
            # Include aging sent follow-ups, Inbox Zero and duplicate drafts.
            threads = rows(query(['gog', 'gmail', 'search',
                'in:inbox OR newer_than:1d OR (in:sent newer_than:7d)', '--account', account,
                '--max', '1000', '--all', '--json', '--no-input']), 'threads')
            drafts = rows(query(['gog', 'gmail', 'drafts', 'list', '--account', account,
                                 '--max', '1000', '--all', '--json', '--no-input']), 'drafts')
            inv['accounts'][name] = {'threads': threads, 'drafts': drafts}
            # Presence is conservative: let existing policy judge follow-ups.
            has_work = has_work or bool(threads or drafts)
        inv['local'] = file_inventory(root, cfg, ['mail.state', 'mail.pending', 'mail.policy', 'mail.settings'])
        return inv, has_work
    if routine == 'wiki-update':
        repo = cfg.get('brief', {}).get('repo')
        if not repo:
            raise ValueError('Falta brief.repo')
        prs = rows(query(['gh', 'api', '--paginate', '--slurp', f'repos/{repo}/pulls?state=all&per_page=100']), 'prs')
        auto = [p for p in prs if re.match(r'^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-', p.get('head', {}).get('ref', p.get('headRefName', '')))]
        keys = [k for k in flatten_paths(cfg.get('paths', {})) if k.endswith('.memory')]
        inv = {'prs': auto, 'files': file_inventory(root, cfg, keys + ['wiki.articles']),
               'day': now.date().isoformat()}
        # Daily maintenance, statistics and closed-PR feedback must still run.
        # Checkpoint only suppresses a second successful run of identical inputs today.
        return inv, any(p.get('state', '').lower() == 'open' for p in auto)
    raise ValueError('Rutina no admitida')


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def gate(routine: str, root: Path, cfg: dict, state: Path, now: datetime) -> dict:
    inventory, mandatory = routine_inventory(routine, root, cfg, now)
    digest = fingerprint(inventory)
    checkpoint = state / f'{routine}.completed.json'
    previous = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    same = previous.get('fingerprint') == digest and previous.get('day') == now.date().isoformat()
    if routine == 'dispatch-executor':
        work = mandatory
    elif routine == 'revision-correo':
        work = mandatory or not same  # Local changes or first scan require review.
    else:
        work = mandatory or not same
    return {'routine_id': routine, 'task_id': f'{routine}:{now.date().isoformat()}:{digest[:12]}',
            'fingerprint': digest, 'day': now.date().isoformat(), 'outcome': 'work' if work else 'noop',
            'reason': 'trabajo pendiente o inventario sin confirmar' if work else 'sin trabajo pendiente; inventario confirmado',
            'checked_at': now.isoformat()}


def append_record(ledger: Path, record: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    # Multiple native routines may finish at the same time.
    import fcntl
    with ledger.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)


def preflight(routine: str, ticket: Path, root: Path, cfg: dict, state: Path, now: datetime) -> int:
    try:
        decision = gate(routine, root, cfg, state, now)
    except Exception as exc:
        decision = {'routine_id': routine, 'outcome': 'error', 'reason': str(exc), 'checked_at': now.isoformat()}
    decision['ticket_path'] = str(ticket.resolve())
    write_json(ticket, decision)
    append_record(state / 'metrics.jsonl', {**decision, 'runtime': 'mechanical', 'model_resolved': None,
        'tokens': {key: 0 for key in TOKEN_KEYS}, 'status': 'error' if decision['outcome'] == 'error' else 'success'})
    print(json.dumps(decision, ensure_ascii=False))
    return {'work': 0, 'noop': 10, 'error': 20}[decision['outcome']]


def complete(ticket: Path, state: Path, outcome: str, reason: str) -> None:
    decision = json.loads(ticket.read_text())
    if decision.get('outcome') != 'work' or decision.get('routine_id') not in PILOTS:
        raise ValueError('Ticket sin trabajo autorizado')
    completion_key = state / 'completions' / (fingerprint({'ticket': str(ticket.resolve()), 'checked_at': decision.get('checked_at')}) + '.json')
    if completion_key.exists():
        if json.loads(completion_key.read_text()).get('outcome') == outcome:
            return
    record = {**decision, 'outcome': outcome, 'reason': reason, 'finished_at': datetime.now(timezone.utc).isoformat()}
    write_json(completion_key, record)
    if outcome == 'completed':
        # Do not re-query here: new arrivals after the preflight remain pending.
        write_json(state / f"{decision['routine_id']}.completed.json", decision)
    append_record(state / 'metrics.jsonl', {**record, 'runtime': 'native', 'status': outcome,
                                         'tokens': {key: None for key in TOKEN_KEYS}})


def close_snapshot(repo: Path, session_id: str, touched: list[str], decisions: list[str], next_steps: list[str]) -> dict:
    repo = repo.resolve()
    files = []
    for raw in dict.fromkeys(touched):
        path = (repo / raw).resolve()
        path.relative_to(repo)  # Reject paths outside this checkout.
        rel = str(path.relative_to(repo))
        if rel == '.' or path.is_dir():
            raise ValueError('Indica archivos de la sesión, no directorios')
        status = run(['git', 'status', '--porcelain', '--', rel], repo).strip()
        files.append({'path': rel, 'status': status})
    return {'schema_version': 1, 'session_id': session_id, 'repo': str(repo),
            'branch': run(['git', 'branch', '--show-current'], repo).strip(),
            'commit': run(['git', 'rev-parse', 'HEAD'], repo).strip(), 'files': files,
            'decisions': decisions, 'next_steps': next_steps,
            'captured_at': datetime.now(timezone.utc).isoformat()}


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(x.get('text', '') for x in content if isinstance(x, dict))
    return ''


def import_usage(paths: list[Path]) -> list[dict]:
    """Deduplicate copied transcripts by harness, session and message.

    Claude streaming fragments update the same message; keep the last usage.
    Codex turn totals are cumulative snapshots: difference them once per turn.
    Unknown formats are skipped; absent token values stay null.
    """
    unique: dict[tuple, dict] = {}
    for path in paths:
        session = path.stem
        task = 'interactive/unknown'
        harness = 'claude'
        previous_totals: dict[str, int] = {}
        for line in path.read_text(errors='replace').splitlines():
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get('type') == 'session_meta':
                session = evt['payload'].get('id', session); harness = 'codex'
            session = evt.get('sessionId', session)
            msg = evt.get('message', {})
            text = ''
            if evt.get('type') == 'user':
                text = content_text(msg.get('content'))
            elif evt.get('type') == 'response_item' and evt.get('payload', {}).get('role') == 'user':
                text = content_text(evt['payload'].get('content'))
            elif evt.get('type') == 'event_msg' and evt.get('payload', {}).get('type') == 'user_message':
                text = evt['payload'].get('message', '')
            if text:
                match = re.search(r'<scheduled-task name="([^\"]+)', text)
                if match: task = 'routine:' + match[1]
                elif text.startswith('Eres un revisor de CLAUDE.md'): task = 'reflect-claudemd'
                elif re.search(r'^/wind-down(?:\s|$)|<command-name>/wind-down</command-name>', text): task = 'close'
                elif task == 'close': task = 'interactive/unknown'
            if evt.get('type') == 'assistant' and msg.get('id') and msg.get('usage') is not None:
                usage = msg['usage']; tokens = {k: next((usage[n] for n in names if n in usage), None) for k, names in TOKEN_KEYS.items()}
                unique[(harness, session, msg['id'])] = {'runtime': harness, 'session_id': session,
                    'message_id': msg['id'], 'task_id': task, 'timestamp': evt.get('timestamp'),
                    'model_resolved': msg.get('model'), 'tokens': tokens}
            if evt.get('type') == 'event_msg' and evt.get('payload', {}).get('type') == 'token_count':
                info = evt['payload'].get('info') or {}; totals = info.get('total_token_usage')
                if not totals: continue
                delta = {k: totals[k] - previous_totals.get(k, 0) for k in totals if isinstance(totals[k], int)}
                previous_totals = totals
                if not any(delta.values()): continue
                cached = delta.get('cached_input_tokens')
                inp = delta.get('input_tokens')
                # Codex input includes cached input. Cache creation is not exposed.
                tokens = {'input': inp - cached if inp is not None and cached is not None else None,
                          'output': delta.get('output_tokens'), 'cache_read': cached, 'cache_write': None}
                key = fingerprint(totals)
                unique[(harness, session, key)] = {'runtime': harness, 'session_id': session,
                    'message_id': key, 'task_id': task, 'timestamp': evt.get('timestamp'),
                    'model_resolved': None, 'tokens': tokens}
    return list(unique.values())


def summarize(records: list[dict], start: str, end: str, zone: str = 'UTC') -> dict:
    groups: dict[str, dict] = {}
    for record in records:
        timestamp = record.get('timestamp') or record.get('checked_at') or record.get('finished_at') or record.get('started_at') or ''
        if not timestamp: continue
        date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
        local_day = date.astimezone(ZoneInfo(zone)).date().isoformat()
        if not start <= local_day < end: continue
        key = record.get('task_id') or record.get('routine_id') or 'unknown'
        # Group routine tickets by routine, not daily fingerprint.
        if record.get('routine_id'): key = 'routine:' + record['routine_id']
        group = groups.setdefault(key, {'records': 0, 'tokens': {k: 0 for k in TOKEN_KEYS},
                                       'unknown': {k: 0 for k in TOKEN_KEYS}, 'outcomes': {}})
        group['records'] += 1
        for k in TOKEN_KEYS:
            value = record.get('tokens', {}).get(k)
            if value is None: group['unknown'][k] += 1
            else: group['tokens'][k] += value
        outcome = record.get('outcome', 'unknown')
        group['outcomes'][outcome] = group['outcomes'].get(outcome, 0) + 1
    return {'start_inclusive': start, 'end_exclusive': end, 'timezone': zone, 'groups': groups,
            'note': 'Registros locales; no equivalen a porcentajes de cuota. Totales parciales si hay valores desconocidos.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for cmd in ['preflight', 'complete']:
        p = sub.add_parser(cmd); p.add_argument('--ticket', type=Path, required=True)
        p.add_argument('--state', type=Path)
        if cmd == 'preflight': p.add_argument('routine', choices=PILOTS)
        else:
            p.add_argument('--outcome', choices=['completed', 'partial', 'error'], required=True)
            p.add_argument('--reason', required=True)
    p = sub.add_parser('close-snapshot'); p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--session-id', required=True); p.add_argument('--path', action='append', default=[])
    p.add_argument('--decision', action='append', default=[]); p.add_argument('--next', action='append', default=[])
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('import-usage'); p.add_argument('--source', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('report'); p.add_argument('--ledger', type=Path, action='append', required=True)
    p.add_argument('--start', required=True); p.add_argument('--end', required=True); p.add_argument('--timezone', default='UTC')
    args = parser.parse_args(argv)
    try:
        if args.command in ['preflight', 'complete']:
            root = instance_root(); cfg = load_config()
            state = args.state or root / 'subsystem/routines/efficiency'
            if args.command == 'preflight':
                now = datetime.now(ZoneInfo(cfg.get('timezone', 'UTC')))
                return preflight(args.routine, args.ticket, root, cfg, state, now)
            complete(args.ticket, state, args.outcome, args.reason)
        elif args.command == 'close-snapshot':
            write_json(args.output, close_snapshot(args.repo, args.session_id, args.path, args.decision, args.next))
        elif args.command == 'import-usage':
            paths = []
            for source in args.source:
                paths.extend(sorted(source.rglob('*.jsonl')) if source.is_dir() else [source])
            records = import_usage(paths)
            # Rebuild atomically: rerunning an import never appends duplicates.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temp = args.output.with_suffix('.tmp')
            temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
            temp.replace(args.output)
            print(json.dumps({'records': len(records)}))
        else:
            records = [json.loads(line) for path in args.ledger for line in path.read_text().splitlines() if line.strip()]
            print(json.dumps(summarize(records, args.start, args.end, args.timezone), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'outcome': 'error', 'reason': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 20


if __name__ == '__main__':
    sys.exit(main())
