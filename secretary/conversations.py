"""Captura conversaciones del propietario sin convertir texto en órdenes ejecutables."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
from pathlib import Path
from zoneinfo import ZoneInfo

from secretary.config import dispatch_executor_repos, load_config

AGENT = re.compile(r'agent-generated:|Codex-generated:|claude-generated:|desk:question', re.I)


def utc() -> datetime:
    return datetime.now(timezone.utc)


def stamp() -> str:
    return utc().isoformat()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def run(args: list[str], text: str | None = None) -> str:
    result = subprocess.run(args, input=text, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'{args[0]} falló')
    return result.stdout.strip()


def gog(account: str, *args: str) -> dict:
    return json.loads(run(['gog', '--account', account, '--json', '--no-input', *args]))


def settings(cfg: dict) -> dict:
    conv = cfg.get('desk', {}).get('conversations', {})
    notify = cfg.get('desk', {}).get('notifications', {})
    accounts = cfg.get('accounts', {})
    result = {**conv, 'owner': accounts.get('personal'),
              'mailbox': notify.get('send_account'), 'alias': notify.get('from'),
              'repos': [r['repo'] for r in dispatch_executor_repos(cfg)],
              'brief_repo': cfg.get('brief', {}).get('repo'),
              'brief_label': cfg.get('brief', {}).get('label'), 'timezone': cfg.get('timezone', 'UTC')}
    if not result['owner'] or result['mailbox'] not in accounts.values() or not result['alias']:
        raise ValueError('Configurar accounts.personal y notifications.send_account/from registrados')
    # Fix the capture floor at activation; rolling windows must never drop an unanswered thread.
    if not result.get('capture_since'):
        raise ValueError('Falta capture_since explícito con zona horaria')
    if datetime.fromisoformat(result['capture_since']).tzinfo is None:
        raise ValueError('capture_since requiere zona horaria')
    return result


class Store:
    """SQLite compartido entre rutinas; las transacciones protegen cursores y avisos."""
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=20)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, source TEXT NOT NULL, revision TEXT NOT NULL,
          payload TEXT NOT NULL, trusted INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          outcome TEXT, evidence TEXT, captured_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS event_claims (event TEXT PRIMARY KEY, token TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS holds (repo TEXT, number INTEGER, event TEXT NOT NULL, reason TEXT NOT NULL, active INTEGER NOT NULL, PRIMARY KEY(repo,number));
        CREATE TABLE IF NOT EXISTS watches (repo TEXT, number INTEGER, PRIMARY KEY(repo,number));
        CREATE TABLE IF NOT EXISTS questions (
          id TEXT PRIMARY KEY, repo TEXT NOT NULL, number INTEGER NOT NULL,
          version INTEGER NOT NULL, text TEXT NOT NULL, scope_sha TEXT NOT NULL,
          state TEXT NOT NULL, event TEXT, answer TEXT, due TEXT, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS question_publications (id TEXT, version INTEGER, url TEXT NOT NULL, PRIMARY KEY(id,version));
        CREATE TABLE IF NOT EXISTS deliveries (
          id TEXT PRIMARY KEY, state TEXT NOT NULL, kind TEXT NOT NULL,
          day TEXT NOT NULL, question_versions TEXT NOT NULL, response TEXT, created_at TEXT NOT NULL);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def watch(self, repo: str, number: int):
        self.db.execute('INSERT OR IGNORE INTO watches VALUES (?,?)', (repo, number)); self.db.commit()

    def capture(self, source: str, payload: dict, trusted: bool) -> str:
        revision = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        event = digest(source + '\n' + revision)
        with self.transaction():
            # Edits are new revisions, never reinterpret the old approval as current.
            old_ids = [r['id'] for r in self.db.execute('SELECT id FROM events WHERE source=? AND revision!=?', (source,revision))]
            for old_id in old_ids:
                self.db.execute("UPDATE questions SET state='awaiting',version=version+1,event=NULL,answer=NULL,updated_at=? WHERE event=? AND state='answered'", (stamp(),old_id))
            self.db.execute("UPDATE events SET status='superseded' WHERE source=? AND revision!=? AND status='pending'", (source, revision))
            self.db.execute('INSERT OR IGNORE INTO events(id,source,revision,payload,trusted,captured_at) VALUES (?,?,?,?,?,?)',
                            (event, source, revision, json.dumps(payload, ensure_ascii=False), int(trusted), stamp()))
            if trusted:
                self.db.execute("UPDATE events SET trusted=1 WHERE id=? AND status='pending'",(event,))
        return event

    def pending(self) -> list[dict]:
        return [dict(row) | {'payload': json.loads(row['payload']), 'claimed': bool(self.db.execute('SELECT 1 FROM event_claims WHERE event=?',(row['id'],)).fetchone())} for row in self.db.execute("SELECT * FROM events WHERE status='pending' ORDER BY captured_at,id")]

    def event(self, event: str) -> dict:
        row = self.db.execute('SELECT * FROM events WHERE id=?', (event,)).fetchone()
        if row is None:
            raise ValueError('Evento no encontrado')
        return dict(row) | {'payload': json.loads(row['payload'])}

    def ack(self, event: str, outcome: str, evidence: str):
        if outcome not in ['routed', 'clarification', 'progress', 'ignored'] or not evidence:
            raise ValueError('Resultado y evidencia requeridos; no marcar visto antes de persistir')
        with self.transaction():
            row = self.event(event)
            if row['status'] != 'pending':
                if row['status'] == 'processed' and row['outcome'] == outcome and row['evidence'] == evidence:
                    return
                raise ValueError('Revisión procesada o superada; no sobrescribir')
            if not row['trusted'] and outcome in ['routed', 'progress']:
                raise ValueError('Fuente no verificada; solo aclaración o descarte')
            self.db.execute("UPDATE events SET status='processed',outcome=?,evidence=? WHERE id=?", (outcome,evidence,event))

    def claim_event(self, event: str) -> dict:
        with self.transaction():
            if self.event(event)['status'] != 'pending':
                raise ValueError('Evento ya procesado o superado')
            token = uuid.uuid4().hex
            try:
                self.db.execute('INSERT INTO event_claims VALUES (?,?,?)',(event,token,stamp()))
            except sqlite3.IntegrityError as exc:
                raise ValueError('Evento en otro intento; no duplicar ni tomar por timeout') from exc
        return {'event':event,'token':token,'state':'claimed'}

    def require_claim(self, event: str, token: str):
        row = self.db.execute('SELECT token FROM event_claims WHERE event=?',(event,)).fetchone()
        if not row or row['token'] != token:
            raise ValueError('Token de reclamo ausente o ajeno')

    def release(self, event: str, token: str):
        with self.transaction():
            self.require_claim(event,token)
            self.db.execute('DELETE FROM event_claims WHERE event=?',(event,))

    def question(self, key: str, repo: str, number: int, text: str, scope_sha: str, due: str = '') -> dict:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', key) or not re.fullmatch(r'[a-f0-9]{64}', scope_sha) or not text.strip():
            raise ValueError('Identificador, texto y SHA de alcance válidos requeridos')
        if due and datetime.fromisoformat(due).tzinfo is None:
            raise ValueError('Plazo requiere zona horaria')
        with self.transaction():
            old = self.db.execute('SELECT * FROM questions WHERE id=?', (key,)).fetchone()
            if old and (old['repo'], old['number']) != (repo, number):
                raise ValueError('ID de pregunta ya pertenece a otro encargo')
            if old and (old['text'],old['scope_sha'],old['due']) == (text,scope_sha,due) and old['state'] == 'awaiting':
                return dict(old)
            version = old['version'] + 1 if old else 1
            self.db.execute('INSERT OR REPLACE INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            (key,repo,number,version,text,scope_sha,'awaiting',None,None,due,stamp()))
            self.db.execute('INSERT OR IGNORE INTO watches VALUES (?,?)', (repo,number))
        return dict(self.db.execute('SELECT * FROM questions WHERE id=?', (key,)).fetchone())

    def answer(self, key: str, version: int, event: str, scope_sha: str, interpretation: str):
        with self.transaction():
            question = self.db.execute('SELECT * FROM questions WHERE id=?', (key,)).fetchone()
            source = self.event(event)
            if not question or question['version'] != version or question['scope_sha'] != scope_sha:
                raise ValueError('Pregunta o alcance cambió; reevaluar')
            if question['state'] == 'answered' and question['event'] == event and question['answer'] == interpretation:
                return
            if question['state'] != 'awaiting' or not source['trusted'] or source['status'] != 'pending':
                raise ValueError('Fuente no vigente/verificada o pregunta ya respondida')
            if not interpretation.strip():
                raise ValueError('Falta interpretación concreta')
            self.db.execute("UPDATE questions SET state='answered',event=?,answer=?,updated_at=? WHERE id=?", (event,interpretation,stamp(),key))

    def hold(self, repo: str, number: int, event: str, reason: str, active=True):
        if not reason.strip() or not self.event(event)['trusted']:
            raise ValueError('Bloqueo/reanudación requiere motivo y fuente verificada')
        with self.transaction():
            self.db.execute('INSERT OR REPLACE INTO holds VALUES (?,?,?,?,?)',(repo,number,event,reason,int(active)))
            self.db.execute('INSERT OR IGNORE INTO watches VALUES (?,?)',(repo,number))

    def gate(self, repo: str, number: int, scope_sha: str) -> dict:
        reasons = []
        hold = self.db.execute('SELECT * FROM holds WHERE repo=? AND number=? AND active=1',(repo,number)).fetchone()
        if hold:
            reasons.append({'kind':'owner-hold','event':hold['event'],'reason':hold['reason']})
        for question in self.db.execute('SELECT * FROM questions WHERE repo=? AND number=?',(repo,number)):
            if question['state']=='awaiting' or question['scope_sha']!=scope_sha:
                reasons.append({'kind':'question','id':question['id'],'version':question['version'],
                                'reason':'Esperando respuesta o alcance cambiado'})
        return {'state':'blocked' if reasons else 'clear','reasons':reasons,
                'meaning':'Ausencia de bloqueo registrado; no concede autorización'}

    def publication(self, question: dict, url: str):
        if not url:
            raise ValueError('Pregunta sin referencia publicada')
        self.db.execute('INSERT OR REPLACE INTO question_publications VALUES (?,?,?)', (question['id'],question['version'],url))
        self.db.commit()

    def questions(self) -> list[dict]:
        return [dict(row) for row in self.db.execute("SELECT * FROM questions WHERE state='awaiting' ORDER BY updated_at")]


def headers(message: dict) -> dict:
    return {h['name'].lower(): h['value'] for h in message.get('payload', {}).get('headers', [])}


def plain(message: dict) -> str:
    def extract(part):
        if part.get('mimeType') == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', errors='replace')
        return '\n'.join(text for child in part.get('parts', []) if (text := extract(child)))
    return extract(message.get('payload', {})).replace('\r\n', '\n').strip()


def unquoted(text: str) -> str:
    # A hint for interpretation, never a substitute for reading the original.
    markers = [r'^>', r'^On .+wrote:', r'^El .+escribi[oó]:', r'^From:', r'^De:']
    positions = [m.start() for pattern in markers if (m := re.search(pattern,text,re.M | re.I))]
    return text[:min(positions)].strip() if positions else text.strip()


def addresses(value: str) -> set[str]:
    return {email.lower() for _,email in getaddresses([value]) if email}


def verify_mail(cfg: dict, message: dict) -> bool:
    """Verifica una copia exacta en Enviados de la cuenta del propietario."""
    h = headers(message); mid = h.get('message-id', '')
    if addresses(h.get('from', '')) != {cfg['owner'].lower()} or not re.fullmatch(r'<[^<>\s]+@[^<>\s]+>', mid):
        return False
    query = 'in:sent rfc822msgid:' + mid[1:-1]
    results = gog(cfg['owner'], 'gmail', 'messages', 'search', query, '--all', '--max', '100')
    for entry in results.get('messages') or []:
        thread = gog(cfg['owner'], 'gmail', 'thread', 'get', entry['threadId']).get('thread', {})
        for original in thread.get('messages', []):
            oh = headers(original)
            if ('SENT' in original.get('labelIds', []) and oh.get('message-id') == mid
                    and addresses(oh.get('from', '')) == {cfg['owner'].lower()}
                    and cfg['alias'].lower() in (addresses(oh.get('to', '')) | addresses(oh.get('cc', '')))
                    and plain(original) == plain(message) and plain(original)):
                return True
    return False


def scan_mail(store: Store, cfg: dict) -> dict:
    since = int(datetime.fromisoformat(cfg['capture_since']).timestamp())
    # Search from activation, not only unread/inbox. A failed scan cannot advance a cursor.
    query = f'after:{since} to:{cfg["alias"]} -in:trash -in:spam'
    results = gog(cfg['mailbox'], 'gmail', 'messages', 'search', query, '--all', '--max', '100')
    captured = []; errors = []
    if results.get('nextPageToken'):
        raise RuntimeError('Consulta de correo incompleta')
    threads = sorted({m['threadId'] for m in results.get('messages') or []})
    for thread_id in threads:
        try:
            thread = gog(cfg['mailbox'], 'gmail', 'thread', 'get', thread_id)['thread']
            for message in thread.get('messages', []):
                h = headers(message)
                if int(message.get('internalDate', '0')) < since * 1000:
                    continue
                if cfg['alias'].lower() not in (addresses(h.get('to', '')) | addresses(h.get('cc', ''))):
                    continue
                if addresses(h.get('from', '')) != {cfg['owner'].lower()}:
                    continue  # Mail from a third party never becomes owner instruction.
                text = plain(message)
                if not text or AGENT.match(text.lstrip().removeprefix('<!--').lstrip()):
                    continue
                source = f'gmail:{cfg["mailbox"]}:{message["id"]}'
                payload = {'kind':'mail','account':cfg['mailbox'],'thread':thread_id,'message':message['id'],
                           'rfc_message_id':h.get('message-id'),'subject':h.get('subject',''),
                           'body':text,'new_text_hint':unquoted(text),'from':h.get('from'),'to':h.get('to'),'received_at':message.get('internalDate')}
                captured.append(store.capture(source,payload,verify_mail(cfg,message)))
        except (RuntimeError,ValueError,KeyError) as exc:
            errors.append({'thread':thread_id,'error':str(exc)})
    return {'captured':captured,'errors':errors}


def issue_ref(repo: str, number: int, cfg: dict):
    if repo not in cfg['repos'] or number < 1:
        raise ValueError('Issue fuera de allowlist')


def github_issue(repo: str, number: int) -> dict:
    return json.loads(run(['gh','issue','view',str(number),'--repo',repo,'--json','body,state,url']))


def scan_github(store: Store, cfg: dict) -> dict:
    errors = []; captured = []
    # Include closed briefs: a reply to yesterday's report remains actionable.
    briefs = json.loads(run(['gh','issue','list','--repo',cfg['brief_repo'],'--state','all','--label',cfg['brief_label'],
                            '--search','created:>='+cfg['capture_since'][:10],'--limit','1000','--json','number']))
    if len(briefs) >= 1000:
        raise RuntimeError('Listado de briefs posiblemente truncado')
    for brief in briefs:
        store.watch(cfg['brief_repo'],brief['number'])
    for watch in store.db.execute('SELECT * FROM watches').fetchall():
        repo,number = watch['repo'],watch['number']; issue_ref(repo,number,cfg)
        try:
            pages = json.loads(run(['gh','api',f'repos/{repo}/issues/{number}/comments','--paginate','--slurp']))
            owner = repo.split('/')[0]
            for comment in [item for page in pages for item in page]:
                if comment['user']['login'] != owner or comment['user'].get('type') != 'User' or AGENT.search(comment['body']):
                    continue
                if datetime.fromisoformat(comment['created_at'].replace('Z','+00:00')) < datetime.fromisoformat(cfg['capture_since']):
                    continue
                payload = {'kind':'github','repo':repo,'issue':number,'comment':comment['id'],'body':comment['body'],
                           'url':comment['html_url'],'updated_at':comment['updated_at'],'author':comment['user']['login']}
                captured.append(store.capture(comment['html_url'],payload,True))
        except (RuntimeError,ValueError,KeyError) as exc:
            errors.append({'repo':repo,'issue':number,'error':str(exc)})
    return {'captured':captured,'errors':errors}


def verify_event(store: Store, cfg: dict, event: str) -> dict:
    row = store.event(event)
    if not row['trusted'] or row['status'] == 'superseded':
        raise ValueError('Fuente no verificada o revisión superada')
    payload = row['payload']
    if payload['kind'] == 'mail':
        thread = gog(cfg['mailbox'],'gmail','thread','get',payload['thread'])['thread']
        originals = [m for m in thread.get('messages',[]) if m['id'] == payload['message']]
        if not originals or plain(originals[0]) != payload['body'] or not verify_mail(cfg,originals[0]):
            raise ValueError('Mensaje original ausente o distinto; no autorizar')
    else:
        comment = json.loads(run(['gh','api',f"repos/{payload['repo']}/issues/comments/{payload['comment']}"]))
        if (comment['body'] != payload['body'] or comment['updated_at'] != payload['updated_at']
                or comment['user']['login'] != payload['author'] or AGENT.search(comment['body'])):
            raise ValueError('Comentario original editado, eliminado o generado por agente')
    return row


def signature(text: str) -> str:
    helper = Path(os.environ.get('SECRETARY_SIGNATURE',str(Path.home()/'.claude/scripts/sec-signature.sh')))
    return run([str(helper),'desk-conversations','--mark'])+'\n\n'+text+'\n\n---\n'+run([str(helper),'desk-conversations','--footer'])


def publish_question(store: Store, question: dict) -> str:
    marker = f"<!-- desk:question {question['id']} v{question['version']} -->"
    pages = json.loads(run(['gh','api',f"repos/{question['repo']}/issues/{question['number']}/comments",'--paginate','--slurp']))
    previous = [c for page in pages for c in page if marker in c['body'] and c['user']['login']==question['repo'].split('/')[0] and 'agent-generated:' in c['body']]
    if previous:
        if question['text'] not in previous[-1]['body']:
            raise ValueError('Comentario de pregunta editado; reconciliar antes de publicar')
        url = previous[-1]['html_url']
        store.publication(question,url)
        return url
    body = signature(marker+f"\n### Pregunta {question['id']} · v{question['version']}\n\n"+question['text']+
                     '\n\nResponde por correo a Secretary o en este issue, indicando el ID de pregunta. Solo el trabajo dependiente queda bloqueado.')
    url = run(['gh','issue','comment',str(question['number']),'--repo',question['repo'],'--body-file','-'],body)
    store.publication(question,url)
    return url


def notification_plan(store: Store, cfg: dict, now: datetime | None = None) -> dict:
    now = now or utc(); day = now.astimezone(ZoneInfo(cfg['timezone'])).date().isoformat()
    pending = store.questions()
    if not pending:
        return {'state':'no-op','reason':'Sin preguntas pendientes'}
    if any(not store.db.execute('SELECT 1 FROM question_publications WHERE id=? AND version=?',(q['id'],q['version'])).fetchone() for q in pending):
        return {'state':'blocked','reason':'Publicar/reconciliar preguntas en sus issues antes de avisar por correo'}
    deliveries = [dict(row) for row in store.db.execute('SELECT * FROM deliveries')]
    if any(d['state']=='sending' for d in deliveries):
        return {'state':'blocked','reason':'Envío previo incierto: reconciliar Enviados, no reintentar'}
    sent = [d for d in deliveries if d['state']=='sent']
    delivered = {(q['id'],q['version']) for d in sent for q in json.loads(d['question_versions'])}
    new = [q for q in pending if (q['id'],q['version']) not in delivered]
    if new:
        selected = new; kind = 'new'
    elif not any(d['kind']=='reminder' and d['day']==day for d in sent):
        # Never remind immediately after the first notice: wait at least 24 hours.
        selected = [q for q in pending if all(now-datetime.fromisoformat(d['created_at']) >= timedelta(hours=24)
                    for d in sent if any(x['id']==q['id'] for x in json.loads(d['question_versions'])))]
        kind = 'reminder'
    else:
        selected = []; kind = 'reminder'
    if not selected:
        urgent_sent = {(q['id'],q['version']) for d in sent if d['kind']=='deadline' for q in json.loads(d['question_versions'])}
        selected = [q for q in pending if q['due'] and timedelta(0) < datetime.fromisoformat(q['due'])-now <= timedelta(hours=4)
                    and (q['id'],q['version']) not in urgent_sent
                    and all(now-datetime.fromisoformat(d['created_at']) >= timedelta(hours=1)
                    for d in sent if any(x['id']==q['id'] for x in json.loads(d['question_versions'])))]
        kind = 'deadline'
    if not selected:
        return {'state':'no-op','reason':'Sin aviso nuevo ni recordatorio vencido'}
    versions = [{'id':q['id'],'version':q['version']} for q in selected]
    return {'state':'ready','kind':kind,'day':day,'questions':selected,'versions':versions,
            'id':digest(kind+'\n'+day+'\n'+json.dumps(versions,sort_keys=True))}


def send_notifications(store: Store, cfg: dict, apply: bool = False) -> dict:
    # Recompute under the same transaction as reservation, not only a prior plan.
    with store.transaction():
        plan = notification_plan(store,cfg)
        if not apply or plan['state'] != 'ready':
            return plan
        if cfg.get('question_email') is not True:
            raise ValueError('Avisos de preguntas no habilitados')
        store.db.execute('INSERT INTO deliveries VALUES (?,?,?,?,?,?,?)',
                         (plan['id'],'sending',plan['kind'],plan['day'],json.dumps(plan['versions']),None,stamp()))
    # A crash or transport error leaves sending; it is never retried automatically.
    sender = gog(cfg['mailbox'],'gmail','settings','sendas','get',cfg['alias']).get('sendAs',{})
    if sender.get('verificationStatus') != 'accepted':
        raise ValueError('Alias de envío no verificado; revisar reserva antes de reintentar')
    lines = ['Secretary necesita tu decisión.','']
    for q in plan['questions']:
        lines += [f"{q['id']} · v{q['version']}", q['text'],f"https://github.com/{q['repo']}/issues/{q['number']}",'']
    lines += ['Responde indicando el ID de pregunta. Una respuesta ambigua mantiene el bloqueo.']
    body = signature('\n'.join(lines))
    subject = f"Secretary · {dict(new='preguntas nuevas',reminder='recordatorio',deadline='plazo próximo')[plan['kind']]} · {plan['day']} · {plan['id'][:12]}"
    response = json.loads(run(['gog','--account',cfg['mailbox'],'--json','--no-input','gmail','send',
                              '--from',cfg['alias'],'--reply-to',cfg['alias'],'--to',cfg['owner'],
                              '--subject',subject,'--body-file','-'],body))
    if not (response.get('id') or response.get('messageId') or response.get('message',{}).get('id')):
        raise ValueError('Respuesta sin ID: envío incierto, reconciliar')
    with store.transaction():
        store.db.execute("UPDATE deliveries SET state='sent',response=? WHERE id=?",(json.dumps(response),plan['id']))
    return {'state':'sent','id':plan['id'],'response':response}


def reconcile(store: Store, cfg: dict) -> list[dict]:
    """Solo confirma envíos encontrados; una ausencia no habilita reintentos."""
    results = []
    for delivery in store.db.execute("SELECT * FROM deliveries WHERE state='sending'").fetchall():
        query = f'in:sent to:{cfg["owner"]} subject:{delivery["id"][:12]}'
        search = gog(cfg['mailbox'],'gmail','messages','search',query,'--all','--max','100')
        matches = []
        for entry in search.get('messages') or []:
            thread = gog(cfg['mailbox'],'gmail','thread','get',entry['threadId'])['thread']
            for message in thread.get('messages',[]):
                h = headers(message)
                if ('SENT' in message.get('labelIds',[]) and delivery['id'][:12] in h.get('subject','')
                        and addresses(h.get('to','')) == {cfg['owner'].lower()}
                        and addresses(h.get('from','')) == {cfg['alias'].lower()}):
                    matches.append(message['id'])
        if matches:
            with store.transaction():
                store.db.execute("UPDATE deliveries SET state='sent',response=? WHERE id=?", (json.dumps({'reconciled':sorted(set(matches))}),delivery['id']))
            results.append({'id':delivery['id'],'state':'sent','messages':matches})
        else:
            results.append({'id':delivery['id'],'state':'uncertain','reason':'No encontrado; no se habilita reintento automático'})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['scan','pending','questions','watch','question','answer','ack','verify-source','receipt','notify','reconcile','claim-event','release-event','hold','resume','gate'])
    parser.add_argument('--repo'); parser.add_argument('--issue',type=int); parser.add_argument('--event')
    parser.add_argument('--id'); parser.add_argument('--version',type=int); parser.add_argument('--body-file',type=Path)
    parser.add_argument('--scope-sha'); parser.add_argument('--due',default=''); parser.add_argument('--outcome')
    parser.add_argument('--token'); parser.add_argument('--evidence'); parser.add_argument('--apply',action='store_true')
    args = parser.parse_args(); config = load_config()
    if config.get('desk',{}).get('conversations',{}).get('enabled') is not True:
        print(json.dumps({'state':'disabled','reason':'Circuito no activado'})); return
    cfg = settings(config)
    path = Path(os.environ.get('SECRETARY_CONVERSATIONS_DB',str(Path.home()/'.local/state/secretary/conversations.sqlite3')))
    if args.action in ['pending','questions'] and not path.is_file():
        print(json.dumps({'state':'uninitialized','reason':'Sin registro inicializado; no demuestra ausencia de pendientes'})); return
    store = Store(path)
    if args.action in ['watch','question','receipt','hold','resume','gate']:
        issue_ref(args.repo,args.issue,cfg)
    if args.action == 'scan':
        result = {'mail':scan_mail(store,cfg),'github':scan_github(store,cfg)}
        result['state'] = 'partial' if result['mail']['errors'] or result['github']['errors'] else 'observed'
    elif args.action == 'pending': result = store.pending()
    elif args.action == 'claim-event': result = store.claim_event(args.event)
    elif args.action == 'release-event':
        store.release(args.event,args.token); result = {'state':'released'}
    elif args.action == 'questions': result = store.questions()
    elif args.action == 'gate':
        issue = github_issue(args.repo,args.issue)
        result = store.gate(args.repo,args.issue,digest(issue['body']))
        if issue['state'] != 'OPEN':
            result = {'state':'blocked','reasons':[{'kind':'closed-issue','reason':'Encargo cerrado'}]}
    elif args.action in ['hold','resume']:
        store.require_claim(args.event,args.token); verify_event(store,cfg,args.event)
        store.hold(args.repo,args.issue,args.event,args.body_file.read_text(),args.action=='hold')
        result = {'state':'held' if args.action=='hold' else 'hold-released-not-authorized'}
    elif args.action == 'watch':
        store.watch(args.repo,args.issue); result = {'state':'watching'}
    elif args.action == 'question':
        issue = github_issue(args.repo,args.issue)
        if issue['state'] != 'OPEN': raise ValueError('Encargo cerrado; no crear pregunta')
        q = store.question(args.id,args.repo,args.issue,args.body_file.read_text(),digest(issue['body']),args.due)
        result = {**q,'url':publish_question(store,q)}
    elif args.action == 'answer':
        store.require_claim(args.event,args.token)
        verify_event(store,cfg,args.event)
        question = store.db.execute('SELECT * FROM questions WHERE id=?',(args.id,)).fetchone()
        if not question or digest(github_issue(question['repo'],question['number'])['body']) != args.scope_sha:
            raise ValueError('El alcance canónico cambió; revisar antes de responder')
        store.answer(args.id,args.version,args.event,args.scope_sha,args.body_file.read_text()); result = {'state':'answered-not-executed'}
    elif args.action == 'ack':
        store.require_claim(args.event,args.token)
        if args.outcome in ['routed','progress']: verify_event(store,cfg,args.event)
        store.ack(args.event,args.outcome,args.evidence); store.release(args.event,args.token); result = {'state':'processed'}
    elif args.action == 'verify-source': result = verify_event(store,cfg,args.event)
    elif args.action == 'receipt':
        store.require_claim(args.event,args.token)
        event = verify_event(store,cfg,args.event); issue = github_issue(args.repo,args.issue)
        if issue['state'] != 'OPEN': raise ValueError('Encargo cerrado')
        result = {'scope_sha256':digest(issue['body']),'source':'desk-event:'+args.event,
                  'owner_quote':event['payload']['body'],'effects':['read','local-edit','branch','open-pr'],
                  'requires_source_verification':True,'meaning':'Evidencia original, no clasificación semántica ni autorización automática'}
    elif args.action == 'reconcile': result = reconcile(store,cfg)
    else: result = send_notifications(store,cfg,args.apply)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError,RuntimeError,OSError,KeyError,TypeError,sqlite3.Error,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'state':'error','reason':str(exc)},ensure_ascii=False))
        raise SystemExit(1) from exc
