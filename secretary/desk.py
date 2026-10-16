"""Read-only work overview, scoped authority and owner-only brief delivery."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from secretary.config import load_config, instance_root


def command(args: list[str]) -> str:
    p = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or f"Error: {args[0]}")
    return p.stdout.strip()


def scope_hash(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


def proposal(body: str) -> dict:
    match = re.search(r'<!-- desk:proposal\s+(\{.*?\})\s*-->', body, re.S)
    try:
        value = json.loads(match[1]) if match else {}
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def authority(issue: dict, owner: str, policy: dict) -> dict:
    """Labels are routing only. Session receipts require independent source verification."""
    digest = scope_hash(issue.get('body') or '')
    if issue.get('state', '').upper() != 'OPEN':
        return {'state': 'blocked', 'reason': 'Issue cerrado', 'scope_sha256': digest}
    for comment in reversed(issue.get('comments', [])):
        if comment.get('author', {}).get('login') != owner:
            continue
        body = comment.get('body') or ''
        if not re.search(r'agent-generated|claude-generated|Codex-generated', body):
            if re.search(rf'^desk:authorize {digest}\s*$', body, re.M):
                return {'state': 'owner-authorized', 'source': comment.get('url'), 'scope_sha256': digest}
            if re.search(rf'^desk:reject {digest}\s*$', body, re.M):
                return {'state': 'blocked', 'reason': 'Rechazo del propietario', 'scope_sha256': digest}
        match = re.search(r'<!-- desk:authorization\s+(\{.*?\})\s*-->', body, re.S)
        if match:
            try:
                receipt = json.loads(match[1])
            except ValueError:
                continue
            if receipt.get('scope_sha256') == digest and receipt.get('source') and receipt.get('owner_quote'):
                return {'state': 'verify-owner-source', 'receipt': receipt, 'scope_sha256': digest}
    p = proposal(issue.get('body') or '')
    effects = p.get('effects')
    if (policy.get('enabled') is True and policy.get('id') == 'prepare-pr-v1'
            and p.get('policy') == policy['id'] and p.get('kind') == 'prepare-pr'
            and isinstance(effects, list) and effects
            and set(effects) <= {'read', 'local-edit', 'branch', 'open-pr'}
            and p.get('requires_decision') is False):
        return {'state': 'policy-authorized', 'policy': policy['id'],
                'requires_preflight': True, 'scope_sha256': digest}
    return {'state': 'needs-decision', 'reason': 'Sin autorización vigente para este alcance', 'scope_sha256': digest}


def protected_changes(paths: list[str]) -> list[str]:
    patterns = (r'(^|/)(AGENTS|CLAUDE)\.md$', r'(^|/)\.secretary\.ya?ml$',
                r'(^|/)(\.github|canon|rules|playbooks|playbooks\.example|skills|skills\.example|portable)/',
                r'(^|/)(\.env(?:\..*)?|.*(?:credential|secret|private.key).*)$',
                r'(^|/)(?:deploy|release|install)[^/]*\.(?:sh|py|js|mjs)$')
    return [p for p in paths if any(re.search(pattern, p, re.I) for pattern in patterns)]


def select_repos(cwd: Path, repos: list[dict]) -> list[dict]:
    cwd = cwd.expanduser().resolve()
    parents = [r for r in repos if cwd == Path(r['path']).expanduser().resolve()
               or Path(r['path']).expanduser().resolve() in cwd.parents]
    if parents:
        return [max(parents, key=lambda r: len(Path(r['path']).parts))]
    # Managed worktrees can live outside the configured project root.
    try:
        common = Path(command(['git', '-C', str(cwd), 'rev-parse', '--path-format=absolute', '--git-common-dir'])).resolve()
        for repo in repos:
            other = Path(command(['git', '-C', str(Path(repo['path']).expanduser()), 'rev-parse',
                                  '--path-format=absolute', '--git-common-dir'])).resolve()
            if common == other:
                return [repo]
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    return [r for r in repos if cwd in Path(r['path']).expanduser().resolve().parents]


def git_snapshot(repo: dict) -> dict:
    root = Path(repo['path']).expanduser()
    result = {'repo': repo['repo'], 'path': str(root), 'worktrees': []}
    try:
        blocks = command(['git', '-C', str(root), 'worktree', 'list', '--porcelain']).split('\n\n')
        for block in blocks:
            entry = dict(line.split(' ', 1) if ' ' in line else (line, True)
                         for line in block.splitlines())
            if 'worktree' not in entry:
                continue
            wt = entry['worktree'];item = {'path': wt, 'branch': entry.get('branch', 'detached')}
            try:
                item['status'] = command(['git', '-C', wt, 'status', '--short', '--branch'])
                item['stashes'] = command(['git', '-C', wt, 'stash', 'list', '--format=%gd %s']).splitlines()
                item['remote_counts_are_cached'] = True
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                item['error'] = str(exc)
            result['worktrees'].append(item)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        result['error'] = str(exc)
    try:
        result['open_prs'] = json.loads(command(['gh', 'pr', 'list', '--repo', repo['repo'], '--state', 'open',
            '--limit', '100', '--json', 'number,title,url,headRefName,isDraft,updatedAt']))
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
        result['pr_error'] = str(exc)
    return result


def decisions(repos: list[dict], owner: str, policy: dict) -> dict:
    found = {};errors = []
    jobs = [(r['repo'], label) for r in repos for label in
            ['desk:decision', 'para-alvaro', 'secretary:proponer', 'dispatch:execute', 'dispatch:blocked']]
    def fetch(job):
        repo,label=job
        try:
            rows=json.loads(command(['gh','issue','list','--repo',repo,'--state','open','--label',label,
                                     '--limit','100','--json','number,title,url,body,labels,updatedAt']))
            return repo,label,rows,None
        except (RuntimeError,subprocess.TimeoutExpired,ValueError) as exc:return repo,label,[],str(exc)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for repo,label,rows,error in pool.map(fetch,jobs):
            if error:errors.append({'repo':repo,'label':label,'error':error})
            for row in rows:
                row['repo']=repo;row['proposal']=proposal(row.get('body') or '');found[row['url']]=row
    return {'items': list(found.values()), 'errors': errors}


def report_sources(instance: Path) -> list[dict]:
    """Evidence candidates, never conclusions from keyword matches alone."""
    fixed = ['subsystem/heartbeat/latest.md', 'loops/job-search/sources-web/state.md',
             'loops/job-search/sources-web/recurrence.yaml', 'loops/job-search/state.md',
             'loops/sales/learnings.md', 'loops/sales/state.md']
    paths = [instance/p for p in fixed]
    reports = instance/'loops/sales/reports'
    if reports.is_dir():
        paths += sorted(reports.glob('*.md'), key=lambda p:p.stat().st_mtime, reverse=True)[:2]
    rows = []
    for path in paths:
        if path.is_file():
            text = path.read_text(errors='replace')
            hits = [{'line': i, 'text': line[:600]} for i, line in enumerate(text.splitlines(), 1)
                    if re.search(r'fuente|estrateg|agotad|decisi[oó]n|bloque|dry.streak|sin respuestas|cola enviable', line, re.I)]
            rows.append({'path': str(path), 'modified_at': datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
                         'candidate_signals': hits[-30:], 'requires_reconciliation': True})
    return rows


def notify(cfg: dict, repo: str, number: int, body_file: Path) -> dict:
    setting = cfg.get('desk', {}).get('notifications', {})
    account = cfg.get('accounts', {}).get('personal')
    if setting.get('brief_email') is not True or not account:
        raise ValueError('Notificación al propietario no habilitada o cuenta ausente')
    # Remitente opcional: cuenta que envía y dirección "Enviar como". El destinatario sigue siendo solo `account`.
    sender_account = setting.get('send_account') or account
    sender_from = setting.get('from')
    known = set(cfg.get('accounts', {}).values())
    if sender_account not in known:
        raise ValueError('send_account debe ser una cuenta registrada en accounts')
    if repo != cfg.get('brief', {}).get('repo'):
        raise ValueError('Solo se notifica el repositorio del brief')
    issue = json.loads(command(['gh', 'issue', 'view', str(number), '--repo', repo, '--json', 'title,url,createdAt,labels']))
    today = datetime.now(ZoneInfo(cfg.get('timezone') or 'UTC')).date().isoformat()
    created = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00')).astimezone(ZoneInfo(cfg.get('timezone') or 'UTC')).date().isoformat()
    if created != today or cfg.get('brief', {}).get('label') not in [l['name'] for l in issue['labels']]:
        raise ValueError('El issue no es un brief creado hoy')
    subject = f'Brief {today} · decisiones y avances'
    root = instance_root()/'subsystem/desk/notifications';root.mkdir(parents=True, exist_ok=True)
    ledger = root/(today+'.json')
    with (root/(today+'.lock')).open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        sent = json.loads(command(['gog', '--account', sender_account, '--json', 'gmail', 'search',
                                  f'in:sent to:{account} subject:"{subject}"', '--max', '5']))
        if sent.get('threads') or sent.get('messages') or (ledger.exists() and json.loads(ledger.read_text()).get('state') == 'sent'):
            return {'state': 'already-sent'}
        if ledger.exists():
            raise ValueError('Envío previo incierto: revisar Enviados antes de reintentar')
        ledger.write_text(json.dumps({'state': 'sending', 'issue': issue['url']})+'\n')
        # Only the configured owner can receive this notification; no arbitrary recipients.
        send = ['gog', '--account', sender_account, '--json', '--no-input', 'gmail', 'send',
                '--to', account, '--subject', subject, '--body-file', str(body_file)]
        if sender_from:
            send += ['--from', sender_from]
        response = json.loads(command(send))
        if not (response.get('id') or response.get('messageId') or response.get('message', {}).get('id')):
            raise ValueError('Respuesta de envío sin ID; verificar Enviados')
        ledger.write_text(json.dumps({'state': 'sent', 'issue': issue['url'], 'response': response})+'\n')
        return {'state': 'sent', 'response': response}


def publish_event(cfg: dict, text: str, routine: str) -> dict:
    """Brief-update's mechanical path: same-day only, content-idempotent."""
    repo = cfg.get('brief', {}).get('repo');label = cfg.get('brief', {}).get('label')
    if not repo or not label:raise ValueError('Brief no configurado')
    zone = ZoneInfo(cfg.get('timezone') or 'UTC');today = datetime.now(zone).date()
    issues = json.loads(command(['gh','issue','list','--repo',repo,'--state','open','--label',label,
                                 '--limit','30','--json','number,createdAt']))
    current = [i for i in issues if datetime.fromisoformat(i['createdAt'].replace('Z','+00:00')).astimezone(zone).date()==today]
    if not current:return {'state':'no-brief-today','reason':'Conserva el evento en su issue/reporte canónico; no se publicó en un brief anterior.'}
    issue = max(current,key=lambda i:i['createdAt']);digest = hashlib.sha256((routine+'\n'+text).encode()).hexdigest()
    marker = '<!-- desk:event '+digest+' -->'
    comments = json.loads(command(['gh','issue','view',str(issue['number']),'--repo',repo,'--json','comments']))['comments']
    if any(marker in c.get('body','') for c in comments):return {'state':'already-published'}
    signer = Path(os.environ.get('SECRETARY_SIGNATURE',str(Path.home()/'.claude/scripts/sec-signature.sh')))
    if not signer.is_file():raise ValueError('Helper de firma ausente; no publicar sin firma')
    body = command([str(signer),'brief-update','--mark'])+'\n'+marker+'\n'+text+'\n\n---\n'+command([str(signer),'brief-update','--footer'])
    # Send the body through stdin to avoid shell quoting or a durable duplicate.
    p = subprocess.run(['gh','issue','comment',str(issue['number']),'--repo',repo,'--body-file','-'],
                       input=body,capture_output=True,text=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return {'state':'published','url':p.stdout.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__);sub = parser.add_subparsers(dest='action', required=True)
    overview = sub.add_parser('overview');overview.add_argument('--context', type=Path, default=Path.cwd())
    sub.add_parser('decisions');sub.add_parser('signals')
    event = sub.add_parser('publish-event');event.add_argument('--body-file',type=Path,required=True);event.add_argument('--routine',required=True)
    check = sub.add_parser('check');check.add_argument('--repo', required=True);check.add_argument('--issue', type=int, required=True)
    guard = sub.add_parser('guard-diff');guard.add_argument('--repo-path', type=Path, required=True);guard.add_argument('--base', default='origin/main')
    mail = sub.add_parser('notify-brief');mail.add_argument('--repo', required=True);mail.add_argument('--issue', type=int, required=True);mail.add_argument('--body-file', type=Path, required=True)
    args = parser.parse_args();cfg = load_config();repos = cfg.get('dispatch', {}).get('executor', {}).get('repos') or []
    owner = cfg.get('brief', {}).get('repo', '').split('/')[0];policy = cfg.get('desk', {}).get('autonomy', {})
    if args.action == 'overview':
        selected = select_repos(args.context, repos)
        result = {'observed_at': datetime.now(ZoneInfo(cfg.get('timezone') or 'UTC')).isoformat(), 'context': str(args.context.resolve()),
                  'repos': [git_snapshot(r) for r in selected], 'decisions': decisions(selected, owner, policy),
                  'routine_reports': report_sources(instance_root()),
                  'sessions': 'Consultar herramientas del harness; los transcripts no acreditan sesiones ejecutándose.'}
        if not selected:
            result['scope_warning'] = 'Contexto fuera de la lista configurada; no se amplió el alcance automáticamente.'
    elif args.action == 'decisions':result = decisions(repos, owner, policy)
    elif args.action == 'signals':result = {'sources': report_sources(instance_root())}
    elif args.action == 'publish-event':result = publish_event(cfg,args.body_file.read_text(),args.routine)
    elif args.action == 'check':
        if args.repo not in {r['repo'] for r in repos}:raise ValueError('Repo fuera de la lista habilitada')
        issue = json.loads(command(['gh', 'issue', 'view', str(args.issue), '--repo', args.repo,
                                   '--json', 'body,state,comments']))
        result = authority(issue, owner, policy)
    elif args.action == 'guard-diff':
        names = command(['git', '-C', str(args.repo_path), 'diff', '--name-only', args.base]).splitlines()
        names += command(['git', '-C', str(args.repo_path), 'ls-files', '--others', '--exclude-standard']).splitlines()
        blocked = protected_changes(names);result = {'blocked_paths': blocked, 'allowed_by_prepare_pr_policy': not blocked}
        print(json.dumps(result, ensure_ascii=False, indent=2));raise SystemExit(20 if blocked else 0)
    else:result = notify(cfg, args.repo, args.issue, args.body_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
