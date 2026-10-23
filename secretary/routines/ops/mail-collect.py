#!/usr/bin/env python3
"""Recolector de hilos nuevos para revision-correo (D15, pieza 9).

Para cada cuenta de ``account_usage.revision_correo`` trae los hilos con actividad
desde la última corrida y escribe un TSV compacto para el triage. Solo lee:
llama a ``gog`` con ``--readonly --gmail-no-send``; no archiva, no etiqueta y no
crea borradores.

Desde: ``freshness.last_success_at`` de ``extractors/mail/contract.yaml`` en
``--instance``; si falta, ``Última actualización`` de ``state.md``; si falta, 24 h.
Nunca cubre menos de ``--min-lookback-hours`` ni más de ``--max-lookback-days``.

Salida (TSV, una sección por cuenta):

    # account=<clave> since=<iso> status=ok threads=<n> truncated=no
    THREAD  DATE  FROM  SUBJECT  LABELS  MSGS  OWNER  SNIPPET

OWNER: ``last`` (el último mensaje es del propietario), ``replied`` (escribió en
el hilo, pero el último no es suyo) o ``no``.

Uso:
    mail-collect.py [--instance DIR] [--out FILE] [--since ISO] [--account CLAVE]...
                    [--max-threads N] [--snippet-chars N] [--dry-run]

``--dry-run`` imprime el plan (cuentas, desde, consulta) sin llamar a Gmail.
Código de salida: 0 si al menos una cuenta respondió, 1 si todas fallaron, 2 por
error de uso o configuración.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

GOG_GUARD = ['--readonly', '--gmail-no-send', '--no-input']
COLUMNS = ['THREAD', 'DATE', 'FROM', 'SUBJECT', 'LABELS', 'MSGS', 'OWNER', 'SNIPPET']
# Etiquetas de sistema que no ayudan al triage.
NOISE_LABELS = {'UNREAD', 'IMPORTANT', 'CATEGORY_PERSONAL'}


def config_get(key: str) -> str:
    out = subprocess.run(['secretary', 'config', 'get', key], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f'mail-collect: no pude leer {key} de la config: {out.stderr.strip()}')
    return out.stdout.strip()


def resolve_accounts(keys: list[str]) -> list[tuple[str, str]]:
    if not keys:
        raw = config_get('account_usage.revision_correo')
        keys = json.loads(raw) if raw.startswith('[') else [raw]
    accounts = []
    for key in keys:
        addr = config_get(f'accounts.{key}')
        if addr:
            accounts.append((key, addr))
    if not accounts:
        raise SystemExit('mail-collect: ninguna cuenta configurada para revision-correo')
    return accounts


def last_run(instance: Path) -> datetime | None:
    contract = instance / 'extractors/mail/contract.yaml'
    if contract.is_file():
        m = re.search(r'last_success_at:\s*"?([0-9T:+\-.Z]+)"?', contract.read_text(encoding='utf-8'))
        if m:
            try:
                return datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
            except ValueError:
                pass
    state = instance / 'extractors/mail/state.md'
    if state.is_file():
        m = re.search(r'Última actualización:\s*(\d{4}-\d{2}-\d{2})', state.read_text(encoding='utf-8'))
        if m:
            return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
    return None


def resolve_since(args: argparse.Namespace, now: datetime) -> datetime:
    since = datetime.fromisoformat(args.since) if args.since else last_run(Path(args.instance))
    if since is None:
        since = now - timedelta(hours=24)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    since = min(since, now - timedelta(hours=args.min_lookback_hours))
    return max(since, now - timedelta(days=args.max_lookback_days))


def gog(account: str, *args: str) -> dict:
    cmd = ['gog', 'gmail', *args, '--json', f'--account={account}', *GOG_GUARD]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        msg = (out.stderr.strip() or out.stdout.strip()).splitlines()
        raise RuntimeError(msg[-1][:160] if msg else f'gog salió con {out.returncode}')
    return json.loads(out.stdout or '{}')


def clean(text: str, limit: int = 0) -> str:
    text = re.sub(r'\s+', ' ', html.unescape(text or '')).strip()
    return text[: limit - 1] + '…' if limit and len(text) > limit else text


def header(msg: dict, name: str) -> str:
    for h in msg.get('payload', {}).get('headers', []) or []:
        if h.get('name', '').lower() == name:
            return h.get('value', '')
    return ''


def thread_row(account: str, summary: dict, snippet_chars: int) -> list[str]:
    tid = summary['id']
    row = {'THREAD': tid, 'DATE': summary.get('date', ''), 'FROM': summary.get('from', ''),
           'SUBJECT': summary.get('subject', ''), 'LABELS': summary.get('labels') or [],
           'MSGS': str(summary.get('messageCount', '')), 'OWNER': '?', 'SNIPPET': ''}
    try:
        msgs = gog(account, 'thread', 'get', tid).get('thread', {}).get('messages', []) or []
    except (RuntimeError, ValueError, subprocess.TimeoutExpired):
        msgs = []
    if msgs:
        last = msgs[-1]
        sent = ['SENT' in (m.get('labelIds') or []) for m in msgs]
        row['OWNER'] = 'last' if sent[-1] else ('replied' if any(sent) else 'no')
        row['FROM'] = header(last, 'from') or row['FROM']
        row['MSGS'] = str(len(msgs))
        row['SNIPPET'] = clean(last.get('snippet', ''), snippet_chars)
    labels = [lb for lb in row['LABELS'] if lb not in NOISE_LABELS]
    row['LABELS'] = ','.join(labels)
    return [clean(str(row[c])) for c in COLUMNS]


def collect(key: str, account: str, query: str, args: argparse.Namespace) -> list[str]:
    head = f'# account={key} since={args.since_iso}'
    try:
        found = gog(account, 'search', query, f'--max={args.max_threads}')
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return [f'{head} status=error error={clean(str(exc))}']
    threads = found.get('threads') or []
    truncated = 'yes' if found.get('nextPageToken') else 'no'
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda t: thread_row(account, t, args.snippet_chars), threads))
    lines = [f'{head} status=ok threads={len(rows)} truncated={truncated}', '\t'.join(COLUMNS)]
    lines += ['\t'.join(r) for r in rows]
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--instance', default=os.environ.get('SECRETARY_INSTANCE', str(Path.home() / '.secretary')))
    p.add_argument('--out', help='archivo de salida (por defecto, stdout)')
    p.add_argument('--since', help='ISO 8601; reemplaza el estado de la última corrida')
    p.add_argument('--account', action='append', default=[], help='clave de accounts.<clave>; repetible')
    p.add_argument('--max-threads', type=int, default=150)
    p.add_argument('--snippet-chars', type=int, default=160)
    p.add_argument('--min-lookback-hours', type=float, default=24)
    p.add_argument('--max-lookback-days', type=float, default=7)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args(argv)

    now = datetime.now(timezone.utc)
    since = resolve_since(args, now)
    args.since_iso = since.isoformat(timespec='seconds')
    query = f'after:{int(since.timestamp())} -in:chats'
    accounts = resolve_accounts(args.account)

    if args.dry_run:
        for key, _ in accounts:
            print(f'[dry-run] account={key} since={args.since_iso} '
                  f'gog gmail search {query!r} --max={args.max_threads} --json {" ".join(GOG_GUARD)}')
        return 0

    lines: list[str] = []
    ok = 0
    for key, addr in accounts:
        section = collect(key, addr, query, args)
        ok += 'status=ok' in section[0]
        lines += section + ['']
    text = '\n'.join(lines)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
