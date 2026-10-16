"""Read-only eligibility checks for deferred repository reorganization."""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import os
import uuid
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from secretary.config import dispatch_executor_repos, load_config


def command(args: list[str]) -> str:
    p = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise RuntimeError(f"{args[0]}: {p.stderr.strip() or 'consulta fallida'}")
    return p.stdout


def git(root: Path, *args: str) -> str:
    return command(['git', '-C', str(root), *args])


def relative(value: str) -> str:
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError('Ruta vacía o con caracteres de control')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '.git' in p.parts or '\\' in value:
        raise ValueError('Ruta fuera del alcance: ' + value)
    if str(p) == '.':
        raise ValueError('Declarar rutas concretas, no todo el repo')
    return str(p)


def overlaps(a: str, b: str) -> bool:
    return a == b or a.startswith(b + '/') or b.startswith(a + '/')


def validate(request: dict, root: Path) -> dict:
    if request.get('version') != 1 or request.get('action') not in ['reorganize', 'archive', 'delete']:
        raise ValueError('Versión o acción no admitida')
    targets = request.get('targets')
    if not isinstance(targets, list) or not targets:
        raise ValueError('Faltan targets')
    result = dict(request)
    result['targets'] = []
    for target in targets:
        src = relative(target['from']); dst = relative(target['to'])
        if overlaps(src, dst):
            raise ValueError('Origen y destino solapados')
        for path in [src, dst]:
            if not (root / path).resolve().is_relative_to(root.resolve()):
                raise ValueError('Ruta resuelta fuera del repo')
        result['targets'].append({'from': src, 'to': dst})
    paths = [path for target in result['targets'] for path in target.values()]
    if any(overlaps(a, b) for i, a in enumerate(paths) for b in paths[i + 1:]):
        raise ValueError('Targets cruzados o destinos duplicados; dividir la propuesta')
    result['dependencies'] = [relative(x) for x in request.get('dependencies', [])]
    conditions = request.get('conditions', [])
    if not isinstance(conditions, list):
        raise ValueError('conditions debe ser una lista')
    for condition in conditions:
        if condition.get('type') == 'issue-completed':
            if not re.fullmatch(r'[\w.-]+/[\w.-]+', condition.get('repo', '')) or not isinstance(condition.get('number'), int) or condition['number'] < 1:
                raise ValueError('Referencia de condición inválida')
        elif condition.get('type') == 'not-before':
            parse_time(condition['at'])
        else:
            raise ValueError('Condición no admitida')
    return result


def parse_time(value: str) -> datetime:
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('La fecha requiere zona horaria')
    return date


def status_paths(raw: str) -> list[str]:
    records = raw.split('\0'); paths = []
    index = 0
    while index < len(records):
        record = records[index]; index += 1
        if not record:
            continue
        paths.append(relative(record[3:].rstrip('/')))
        if 'R' in record[:2] or 'C' in record[:2]:
            if index >= len(records) or not records[index]:
                raise ValueError('Rename incompleto')
            paths.append(relative(records[index].rstrip('/'))); index += 1
    return paths


def observe(root: Path, repo: str) -> dict:
    """Read all worktrees, local pending commits, shared stashes and open PRs."""
    observed = {'captured_at': datetime.now(timezone.utc).isoformat(), 'worktrees': [], 'pending': [], 'prs': [], 'errors': []}
    try:
        lines = git(root, 'worktree', 'list', '--porcelain').splitlines()
        worktrees = [Path(line[9:]) for line in lines if line.startswith('worktree ')]
        if not worktrees:
            observed['errors'].append('Inventario de worktrees vacío')
        base = git(root, 'rev-parse', 'origin/main').strip()
        observed['base'] = base
        remote_base = command(['gh', 'api', f'repos/{repo}/commits/main', '--jq', '.sha']).strip()
        if remote_base != base:
            observed['errors'].append('origin/main desactualizado: actualizar antes de evaluar')
        for wt in worktrees:
            dirty = status_paths(git(wt, 'status', '--porcelain=v1', '-z', '--untracked-files=all'))
            pending = [relative(p) for p in git(wt, 'diff', '--name-only', '-z', base + '...HEAD').split('\0') if p]
            row = {'path': str(wt), 'head': git(wt, 'rev-parse', 'HEAD').strip(), 'dirty': dirty, 'unmerged': pending}
            observed['worktrees'].append(row)
            for kind, paths in [('dirty', dirty), ('unmerged-commit', pending)]:
                if paths:
                    observed['pending'].append({'kind': kind, 'source': str(wt), 'paths': paths})
        # A stash belongs to the repo, not each checkout. Include its untracked parent.
        for ref in git(root, 'stash', 'list', '--format=%gd').splitlines():
            paths = [relative(p) for p in git(root, 'diff', '--name-only', '-z', ref + '^1', ref).split('\0') if p]
            parents = git(root, 'rev-list', '--parents', '-n', '1', ref).split()
            if len(parents) > 3:
                paths += [relative(p) for p in git(root, 'ls-tree', '-r', '--name-only', '-z', ref + '^3').split('\0') if p]
            observed['pending'].append({'kind': 'stash', 'source': ref, 'paths': sorted(set(paths))})
    except (RuntimeError, ValueError) as exc:
        observed['errors'].append(str(exc))
    try:
        prs = json.loads(command(['gh', 'pr', 'list', '--repo', repo, '--state', 'open', '--limit', '1000', '--json', 'number,url']))
        if len(prs) >= 1000:
            raise ValueError('Cobertura de PR incompleta')
        observed['prs'] = prs
        for pr in prs:
            detail = json.loads(command(['gh', 'pr', 'view', str(pr['number']), '--repo', repo, '--json', 'headRefOid']))
            pages = json.loads(command(['gh', 'api', f"repos/{repo}/pulls/{pr['number']}/files", '--paginate', '--slurp']))
            files = [file for page in pages for file in page]
            paths = sorted({relative(file[key]) for file in files for key in ['filename', 'previous_filename'] if file.get(key)})
            if not paths or len(files) >= 3000:
                observed['errors'].append(f"PR #{pr['number']}: alcance vacío o posiblemente truncado")
            observed['pending'].append({'kind': 'pr', 'source': pr['url'], 'paths': paths, 'head': detail['headRefOid']})
    except (RuntimeError, ValueError, KeyError) as exc:
        observed['errors'].append(str(exc))
    return observed


def scope(request: dict, root: Path) -> tuple[list[str], list[str]]:
    """Expand scope with tracked references to old/new paths; ambiguous basenames block."""
    affected = {p for target in request['targets'] for p in target.values()} | set(request['dependencies'])
    errors = []
    sources = [t['from'] for t in request['targets']]
    for name in git(root, 'ls-files', '-z').split('\0'):
        if not name:
            continue
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if b'\0' in data:
            continue
        text = data.decode('utf-8', errors='replace')
        for old in sources:
            if old in text:
                affected.add(relative(name))
            elif PurePosixPath(old).name in text and name not in request['dependencies'] and not any(overlaps(name, p) for p in affected):
                errors.append(f'Referencia por nombre sin ruta delimitada: {name} → {PurePosixPath(old).name}')
    return sorted(affected), sorted(set(errors))


def conditions(request: dict, now: datetime) -> list[dict]:
    result = []
    for condition in request.get('conditions', []):
        try:
            if condition['type'] == 'not-before':
                result.append({'condition': condition, 'value': now >= parse_time(condition['at']), 'evidence': now.isoformat()})
            else:
                issue = json.loads(command(['gh', 'issue', 'view', str(condition['number']), '--repo', condition['repo'], '--json', 'state,stateReason,url']))
                result.append({'condition': condition, 'value': issue['state'] == 'CLOSED' and issue.get('stateReason') == 'COMPLETED', 'evidence': issue})
        except (RuntimeError, ValueError, KeyError) as exc:
            result.append({'condition': condition, 'value': None, 'error': str(exc)})
    return result


def evaluate(request: dict, observation: dict, affected: list[str], scope_errors: list[str], condition_results: list[dict], activity: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    reasons = list(scope_errors) + list(observation.get('errors', []))
    try:
        age = (now - parse_time(observation['captured_at'])).total_seconds()
        if not 0 <= age <= 300:
            reasons.append('Evidencia Git/PR vencida o futura')
    except (KeyError, ValueError):
        reasons.append('Falta fecha verificable de observación')
    known = False
    if activity is not None:
        try:
            age = (now - parse_time(activity['captured_at'])).total_seconds()
            known = activity['coverage'] == 'known' and bool(activity['source']) and 0 <= age <= 300
            if not known:
                reasons.append('Cobertura del harness desconocida o vencida')
            for record in activity.get('active', []):
                paths = [relative(p) for p in record['paths']]
                if not paths:
                    reasons.append('Sesión activa sin rutas delimitadas')
                elif any(overlaps(a, b) for a in affected for b in paths):
                    reasons.append('Trabajo activo: ' + str(record.get('ref', activity['source'])))
        except (KeyError, ValueError):
            reasons.append('Evidencia de actividad inválida')
    blockers = []
    for pending in observation.get('pending', []):
        if not pending['paths'] or any(overlaps(a, b) for a in affected for b in pending['paths']):
            blockers.append(pending)
    if blockers:
        reasons.append('Trabajo pendiente en rutas afectadas')
    if not known:
        if any(w['dirty'] for w in observation.get('worktrees', [])) or observation.get('prs'):
            reasons.append('Sin cobertura del harness: exige Git limpio en todos los worktrees y ningún PR abierto')
    if any(c['value'] is None for c in condition_results):
        reasons.append('Condición con evidencia desconocida')
    state = 'blocked' if reasons else 'waiting' if any(c['value'] is False for c in condition_results) else 'eligible-for-pr'
    if request['action'] != 'reorganize':
        state = 'proposal-only'; reasons.append('Archivo/borrado requiere plan de preservación y aprobación específica')
    return {'state': state, 'scope': affected, 'reasons': reasons, 'blockers': blockers, 'conditions': condition_results,
            'harness_coverage': 'known' if known else 'unknown', 'effects': [], 'permission': 'prepare-pr-only; merge humano'}


def inspect(root: Path, repo: str, request: dict, activity: dict | None = None) -> dict:
    request = validate(request, root)
    observed = observe(root, repo)
    affected, errors = scope(request, root)
    for target in request['targets']:
        if not (root / target['from']).exists():
            errors.append('Origen ausente: ' + target['from'])
        if (root / target['to']).exists():
            errors.append('Destino existente: ' + target['to'])
    now = datetime.now(timezone.utc)
    result = evaluate(request, observed, affected, errors, conditions(request, now), activity, now)
    result.update({'repo': repo, 'request': request, 'observation': observed})
    result['fingerprint'] = hashlib.sha256(json.dumps({'repo': repo, 'request': request}, sort_keys=True).encode()).hexdigest()
    result['evidence_hash'] = hashlib.sha256(json.dumps(observed, sort_keys=True).encode()).hexdigest()
    material = {key: result[key] for key in ['fingerprint', 'state', 'scope', 'reasons', 'blockers']}
    result['report_key'] = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
    return result


def claim(directory: Path, repo: str, fingerprint: str, token: str = "") -> dict:
    """Serialize preparation per repo. A crashed claim never expires into execution."""
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(repo.encode()).hexdigest()
    lease = directory / (key + '.json')
    # Keep the guard inode: deleting it would allow two processes to lock different files.
    with (directory / (key + '.guard')).open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        if token:
            if not lease.exists() or json.loads(lease.read_text())['token'] != token:
                raise ValueError('Reclamo ausente o token de otro intento; no liberar')
            lease.unlink()
            return {'state': 'released'}
        if lease.exists():
            raise ValueError('Repo reclamado; comprobar el intento anterior antes de liberar. Sin recuperación automática por tiempo.')
        record = {'repo': repo, 'fingerprint': fingerprint, 'token': uuid.uuid4().hex,
                  'created_at': datetime.now(timezone.utc).isoformat()}
        with lease.open('x') as handle:
            json.dump(record, handle)
        return {'state': 'claimed', **record}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--issue', type=int)
    parser.add_argument('--claim', choices=['acquire', 'release'], help='Reclamo local explícito: no mueve archivos ni autoriza ejecución')
    parser.add_argument('--fingerprint', default='')
    parser.add_argument('--token', default='')
    parser.add_argument('--activity', type=Path, help='Evidencia fresca de un colector de sesiones confiable; no inferir cobertura')
    args = parser.parse_args()
    matches = [e for e in dispatch_executor_repos(load_config()) if e['repo'] == args.repo]
    if len(matches) != 1:
        raise ValueError('Repo ausente o duplicado en allowlist')
    root = Path(matches[0]['path'])
    if args.claim:
        if args.request or args.issue or args.activity:
            raise ValueError('Reclamo y evaluación son operaciones separadas')
        if args.claim == 'acquire' and not re.fullmatch('[a-f0-9]{64}', args.fingerprint):
            raise ValueError('Fingerprint requerido para reclamar')
        if args.claim == 'release' and not args.token:
            raise ValueError('Token requerido para liberar')
        directory = Path(os.environ.get('SECRETARY_TIDY_CLAIMS', str(Path.home()/'.local/state/secretary/tidy/claims')))
        print(json.dumps(claim(directory, args.repo, args.fingerprint, args.token if args.claim == 'release' else '')) )
        return
    if bool(args.request) == bool(args.issue):
        raise ValueError('Indicar --request o --issue, no ambos')
    if args.issue:
        issue = json.loads(command(['gh', 'issue', 'view', str(args.issue), '--repo', args.repo, '--json', 'body,state,labels,url']))
        if issue['state'] != 'OPEN' or 'tag:tidyup' not in [label['name'] for label in issue['labels']]:
            raise ValueError('Solicitud cerrada o sin etiqueta de descubrimiento')
        blocks = re.findall(r'<!-- tidy:request\s+(.*?)\s*-->', issue['body'], re.S)
        if len(blocks) != 1:
            raise ValueError('Exigir exactamente un bloque tidy:request JSON')
        request = json.loads(blocks[0])
    else:
        request = json.loads(args.request.read_text())
    allowed = {entry['repo'] for entry in dispatch_executor_repos(load_config())}
    if any(c.get('type') == 'issue-completed' and c.get('repo') not in allowed for c in request.get('conditions', [])):
        raise ValueError('Condición de un repo fuera de allowlist')
    result = inspect(root, args.repo, request, json.loads(args.activity.read_text()) if args.activity else None)
    if args.issue:
        result['source'] = issue['url']
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
