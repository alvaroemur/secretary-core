"""Read-only macOS WhatsApp capture and shared, message-level review receipts.

No login, send, read-receipt, or application database mutation operations.
Private paths, chat identities, and provider configuration belong to the instance.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from secretary.signatures import signature

import yaml

APPLE_EPOCH = 978307200


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_config(instance, config_path=None):
    settings = yaml.safe_load((Path(instance) / '.secretary.yml').read_text()) or {}
    relative = settings.get('paths', {}).get('whatsapp', {}).get('review_config')
    if not relative:
        raise ValueError('Configure paths.whatsapp.review_config with secretary config')
    path = Path(config_path).resolve() if config_path else (Path(instance) / relative).resolve()
    if not path.is_relative_to(Path(instance).resolve()):
        raise ValueError('Review configuration must belong to the private instance')
    cfg = yaml.safe_load(path.read_text())
    cfg['database'] = str(Path(cfg['database']).expanduser())
    cfg['media_root'] = str(Path(cfg['media_root']).expanduser())
    return cfg


@contextmanager
def source(db):
    # SQLite read transaction includes committed WAL pages. No immutable=1:
    # that option can silently hide recently synced messages in the WAL.
    c = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    c.execute('BEGIN')
    try:
        required = {'ZWAMESSAGE', 'ZWACHATSESSION', 'ZWAMEDIAITEM', 'ZWAGROUPMEMBER'}
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= tables:
            raise ValueError('Esquema WhatsApp no compatible; no se avanzó la cobertura')
        yield c
    finally:
        c.rollback()
        c.close()


def probe(cfg):
    with source(cfg['database']) as c:
        row = c.execute('SELECT count(*),max(ZMESSAGEDATE) FROM ZWAMESSAGE').fetchone()
        latest = datetime.fromtimestamp(row[1] + APPLE_EPOCH, timezone.utc).isoformat() if row[1] else None
        return {'checked_at': now(), 'source': 'macos-sqlite', 'readable': True,
                'messages': row[0], 'latest_message_at': latest,
                'database_modified_at': datetime.fromtimestamp(Path(cfg['database']).stat().st_mtime, timezone.utc).isoformat(),
                'sync_status': 'unknown', 'note': 'Acceso comprobado; fecha de mensaje no acredita sincronización completa'}


def chats(cfg):
    with source(cfg['database']) as c:
        return [dict(r) for r in c.execute('SELECT Z_PK AS local_id,ZCONTACTJID AS jid,ZPARTNERNAME AS name,ZCONTACTABID AS contact_id,ZLASTMESSAGEDATE AS apple_last_date FROM ZWACHATSESSION WHERE ZCONTACTJID IS NOT NULL AND ZCONTACTJID NOT LIKE "%.status"')]


def ledger(instance):
    p = Path(instance) / 'extractors/whatsapp/inbox/local-review.sqlite'
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=30)
    os.chmod(p, 0o600)
    c.execute('CREATE TABLE IF NOT EXISTS receipts (message_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, summary TEXT NOT NULL, processed_at TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS transcripts (audio_hash TEXT PRIMARY KEY, text TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL)')
    c.commit()
    return c


def media_path(cfg, relative):
    if not relative:
        return None
    root = Path(cfg['media_root']).resolve()
    p = (root / relative).resolve()
    if not p.is_relative_to(root):
        raise ValueError('Ruta de media fuera de su raíz')
    return p if p.is_file() else None


def capture(cfg, instance, selectors=None, days=30, historical=False, include_audio=False, include_reviewed=False):
    if days < 1 or (days > 90 and not historical):
        raise ValueError('Más de 90 días requiere consulta histórica explícita')
    approved = cfg.get('chats', [])
    requested = selectors or [x['jid'] for x in approved]
    selected = []
    for q in requested:
        matches = [x for x in approved if q in (x['jid'], x.get('slug'), x.get('name'))]
        if len(matches) != 1:
            raise ValueError('Selector ausente o ambiguo en lista aprobada: ' + q)
        selected.append(matches[0])
    since = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp() - APPLE_EPOCH
    entries, discovery = [], []
    state = ledger(instance)
    try:
        with source(cfg['database']) as c:
            catalog = {r['jid']: r for r in [dict(x) for x in c.execute('SELECT Z_PK AS pk,ZCONTACTJID AS jid,ZPARTNERNAME AS name FROM ZWACHATSESSION')]}
            known = {x['jid'] for x in approved}
            # Only metadata is read for chats outside the allowlist.
            discovery = [dict(r) for r in c.execute('SELECT ZCONTACTJID AS jid,ZPARTNERNAME AS name,ZCONTACTABID AS contact_id,ZLASTMESSAGEDATE AS apple_last_date FROM ZWACHATSESSION WHERE ZLASTMESSAGEDATE>=? AND ZCONTACTJID NOT LIKE "%.status"', (since,)) if r['jid'] not in known]
            for chat in selected:
                if chat['jid'] not in catalog:
                    entries.append({'chat': chat['slug'], 'error': 'chat_not_found'})
                    continue
                sql = '''SELECT m.Z_PK AS local_id,m.ZSTANZAID AS stanza_id,m.ZTEXT AS text,
                m.ZMESSAGETYPE AS type,m.ZMESSAGEDATE AS date,m.ZISFROMME AS from_me,
                g.ZMEMBERJID AS member_jid,i.ZMEDIALOCALPATH AS media_relative
                FROM ZWAMESSAGE m LEFT JOIN ZWAGROUPMEMBER g ON m.ZGROUPMEMBER=g.Z_PK
                LEFT JOIN ZWAMEDIAITEM i ON m.ZMEDIAITEM=i.Z_PK
                WHERE m.ZCHATSESSION=? AND m.ZMESSAGEDATE>=? ORDER BY m.ZMESSAGEDATE,m.Z_PK'''
                for r in c.execute(sql, (catalog[chat['jid']]['pk'], since)):
                    sender = 'self' if r['from_me'] else (r['member_jid'] or (chat['jid'] if not chat['jid'].endswith('@g.us') else None))
                    identity = r['stanza_id'] or 'local:' + str(r['local_id'])
                    key = chat['jid'] + ':' + identity + ':' + str(sender)
                    fingerprint = hashlib.sha256(json.dumps([r['text'],r['type'],r['media_relative'],sender],ensure_ascii=False).encode()).hexdigest()
                    old = state.execute('SELECT fingerprint,summary FROM receipts WHERE message_key=?',(key,)).fetchone()
                    # A receipt on an unmerged PR is valid only while its summary still exists.
                    if not include_reviewed and old and old[0] == fingerprint and Path(old[1]).is_file():
                        continue
                    audio = r['type'] == 3
                    active = bool(chat.get('active_commitments', False))
                    entry = {'key': key, 'fingerprint': fingerprint, 'local_id': r['local_id'],
                        'chat': chat['slug'], 'jid':chat['jid'], 'sender_jid':sender,
                        'date':datetime.fromtimestamp(r['date']+APPLE_EPOCH,timezone.utc).isoformat(),
                        'text':r['text'], 'type':r['type'], 'audio':audio,
                        'audio_eligible':audio and active, 'media_relative':r['media_relative'],
                        'media_present':bool(media_path(cfg,r['media_relative'])) if audio else False}
                    entries.append(entry)
        if include_audio:
            for entry in entries:
                if entry.get('audio_eligible'):
                    try:
                        entry['transcript'] = transcribe(cfg, instance, entry['local_id'])
                    except (ValueError, OSError, subprocess.SubprocessError) as error:
                        entry['audio_error'] = str(error)
        return {'schema_version':1,'captured_at':now(),'days':days,'historical':historical,
                'selected_chats':[x['jid'] for x in selected], 'messages':entries,
                'discovery_metadata_only':discovery, 'coverage':'partial_pending_review'}
    finally:
        state.close()


def protobuf_bytes(blob):
    """Decode length-delimited media metadata, never print keys."""
    i = 0
    def varint():
        nonlocal i
        n = shift = 0
        while i < len(blob) and shift <= 63:
            b = blob[i]; i += 1
            n |= (b & 127) << shift
            if b < 128:
                return n
            shift += 7
        raise ValueError('Metadatos multimedia no compatibles')
    out = {}
    while i < len(blob):
        tag = varint(); wire = tag & 7
        if wire == 2:
            size = varint()
            if i + size > len(blob):
                raise ValueError('Metadatos truncados')
            out[tag >> 3] = blob[i:i+size]; i += size
        elif wire == 0:
            varint()
        elif wire in (1,5):
            i += 8 if wire == 1 else 4
        else:
            raise ValueError('Metadatos multimedia no compatibles')
    return out


def decrypt_media(payload, key):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if len(key) != 32 or len(payload) < 26:
        raise ValueError('Media o clave inválida')
    prk = hmac.digest(bytes(32), key, 'sha256')
    result = prev = b''
    for index in range(1,5):
        prev = hmac.digest(prk, prev + b'WhatsApp Audio Keys' + bytes([index]), 'sha256')
        result += prev
    iv, cipher_key, mac_key = result[:16], result[16:48], result[48:80]
    encrypted, mac = payload[:-10], payload[-10:]
    if not hmac.compare_digest(mac,hmac.digest(mac_key,iv+encrypted,'sha256')[:10]):
        raise ValueError('Integridad HMAC de audio inválida')
    d = Cipher(algorithms.AES(cipher_key),modes.CBC(iv)).decryptor()
    padded = d.update(encrypted) + d.finalize()
    pad = padded[-1]
    if not 1 <= pad <= 16 or padded[-pad:] != bytes([pad])*pad:
        raise ValueError('Padding de audio inválido')
    return padded[:-pad]


def fetch_audio(cfg, instance, local_id):
    with source(cfg['database']) as c:
        row = c.execute('''SELECT s.ZCONTACTJID,i.ZMEDIALOCALPATH,i.ZMEDIAURL,i.ZMEDIAKEY
        FROM ZWAMESSAGE m JOIN ZWAMEDIAITEM i ON m.ZMEDIAITEM=i.Z_PK
        JOIN ZWACHATSESSION s ON m.ZCHATSESSION=s.Z_PK WHERE m.Z_PK=? AND m.ZMESSAGETYPE=3''',(local_id,)).fetchone()
    allowed = {x['jid']:x for x in cfg.get('chats',[])}
    if not row or row[0] not in allowed or not allowed[row[0]].get('active_commitments'):
        raise ValueError('Audio fuera de contactos/proyectos activos aprobados')
    local = media_path(cfg,row[1])
    if local:
        return local
    cache = Path(instance)/'extractors/whatsapp/inbox/media'/f'local-{local_id}.opus'
    if cache.is_file():
        return cache
    url = row[2] or ''
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'mmg.whatsapp.net':
        raise ValueError('URL de media ausente o fuera del CDN autorizado')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):
            raise ValueError('Redirección de descarga no permitida')
    # URL query and keys must never enter logs or exception messages.
    try:
        with urllib.request.build_opener(NoRedirect).open(url,timeout=45) as response:
            data = response.read(25*1024*1024+1)
        if len(data)>25*1024*1024:
            raise ValueError('Audio demasiado grande')
        fields = protobuf_bytes(row[3])
        plain = None
        for key in (row[3], *fields.values()):
            if len(key) != 32:
                continue
            try:
                plain = decrypt_media(data,key);break
            except ValueError:
                continue
        if plain is None:
            raise ValueError('No se pudo validar/descifrar el audio')
    except Exception as e:
        raise ValueError('Audio download unavailable: '+type(e).__name__+(' HTTP '+str(e.code) if hasattr(e,'code') else '')) from None
    cache.parent.mkdir(parents=True,exist_ok=True)
    cache.write_bytes(plain);cache.chmod(0o600)
    return cache


def transcribe(cfg, instance, local_id, provider=None):
    try:
        return _transcribe(cfg, instance, local_id, provider)
    except (ValueError, OSError, subprocess.SubprocessError):
        fallback = cfg.get("transcription", {}).get("fallback")
        if provider is None and fallback and fallback != cfg.get("transcription", {}).get("default", "local"):
            return _transcribe(cfg, instance, local_id, fallback)
        raise


def _transcribe(cfg, instance, local_id, provider=None):
    audio = fetch_audio(cfg, instance, local_id)
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    choice = provider or cfg.get('transcription',{}).get('default','local')
    options = cfg.get('transcription',{}).get('providers',{})
    opt = options.get(choice)
    if not opt:
        raise ValueError('Proveedor no configurado')
    state = ledger(instance)
    try:
        cached = state.execute('SELECT text,provider,model FROM transcripts WHERE audio_hash=?',(digest,)).fetchone()
        if cached and cached[1] == choice and cached[2] == opt['model']:
            return {'text':cached[0],'provider':cached[1],'model':cached[2],'cached':True,'audio_hash':digest}
        if opt['kind'] == 'mlx':
            python = str(Path(opt['python']).expanduser())
            code = 'import json,sys,mlx_whisper; r=mlx_whisper.transcribe(sys.argv[1],path_or_hf_repo=sys.argv[2],language="es"); print(json.dumps({"text":r["text"]}))'
            run = subprocess.run([python,'-c',code,str(audio),opt['model']],capture_output=True,text=True,timeout=opt.get('timeout_seconds',600))
            if run.returncode:
                raise ValueError('Falló transcripción local; no se cambió de proveedor')
            text = json.loads(run.stdout.strip().splitlines()[-1])['text']
        elif opt['kind'] == 'openai-transcriptions':
            endpoint = opt['base_url'].rstrip('/')+'/audio/transcriptions'
            if urlparse(endpoint).scheme != 'https':
                raise ValueError('API requiere HTTPS')
            secret = os.environ.get(opt['key_env'])
            if not secret:
                raise ValueError('Falta la variable de credencial del proveedor')
            boundary = 'secretary-'+os.urandom(12).hex()
            chunks=[]
            for k,v in [('model',opt['model']),('language','es')]:
                chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.ogg"\r\nContent-Type: audio/ogg\r\n\r\n'.encode(),audio.read_bytes(),f'\r\n--{boundary}--\r\n'.encode()]
            req=urllib.request.Request(endpoint,data=b''.join(chunks),headers={'Authorization':'Bearer '+secret,'Content-Type':'multipart/form-data; boundary='+boundary})
            class NoApiRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args):
                    raise ValueError('API redirects are not allowed')
            try:
                with urllib.request.build_opener(NoApiRedirect).open(req,timeout=180) as response:
                    text=json.load(response)['text']
            except Exception as e:
                raise ValueError('Falló API de transcripción: '+type(e).__name__) from None
        else:
            raise ValueError('Proveedor sin adaptador de transcripción verificado')
        state.execute('INSERT OR REPLACE INTO transcripts VALUES (?,?,?,?,?)',(digest,text,choice,opt['model'],now()));state.commit()
        return {'text':text,'provider':choice,'model':opt['model'],'cached':False,'audio_hash':digest}
    finally:
        state.close()


def record(cfg, instance, output, batch_path, review_path):
    """Persist only reviewed message IDs; summary precedes receipt commit.

    The caller provides the synthesis. Receipt coverage is per message revision,
    never a high-water mark that could swallow unreviewed conversations.
    """
    batch=json.loads(Path(batch_path).read_text()); review=json.loads(Path(review_path).read_text())
    rows={m['key']:m for m in batch['messages'] if 'key' in m}
    keys=review['message_keys']
    if not keys or len(keys)!=len(set(keys)) or any(k not in rows for k in keys):
        raise ValueError('IDs revisados inválidos o duplicados')
    for k in keys:
        m=rows[k]
        if m.get('audio_eligible'):
            t=m.get('transcript') or {}
            if not t.get('text','').strip() or m.get('audio_error'):
                raise ValueError('Audio sin transcripción; no avanzar cobertura')
    summary=review['summary'].strip()
    marker, footer = signature('whatsapp-review')
    summary = marker + '\n\n' + summary + '\n\n' + footer
    if not summary:
        raise ValueError('Resumen vacío')
    tag=hashlib.sha256(json.dumps(sorted((k,rows[k]['fingerprint']) for k in keys)).encode()).hexdigest()[:20]
    root=Path(output).resolve()/'extractors/whatsapp'
    dest=root/'summaries'/f'{datetime.now(timezone.utc).date()}-review-{tag}.md'
    state=ledger(instance)
    try:
        state.execute('BEGIN IMMEDIATE')
        pending=[k for k in keys if not (r:=state.execute('SELECT fingerprint,summary FROM receipts WHERE message_key=?',(k,)).fetchone()) or r[0]!=rows[k]['fingerprint'] or not Path(r[1]).is_file()]
        if not pending:
            return {'status':'already_recorded','messages':0}
        dest.parent.mkdir(parents=True,exist_ok=True)
        evidence='\n'.join('- '+rows[k]['date']+' · '+rows[k]['chat']+' · '+k for k in pending)
        content='---\ntipo: whatsapp-review\nfecha: '+now()+'\n---\n\n'+summary+'\n\n## Evidencia\n\n'+evidence+'\n'
        fd,tmp=tempfile.mkstemp(dir=dest.parent)
        with os.fdopen(fd,'w') as f:f.write(content)
        os.replace(tmp,dest)
        # Separate deterministic items avoid concurrent append races. wiki-update
        # reads this directory; summary contains the synthesis, never just a pointer.
        item=root/'memory/reviews'/f'{tag}.md'
        item.parent.mkdir(parents=True,exist_ok=True)
        item.write_text('## whatsapp-review-'+tag+'\n- tipo: chat\n- resumen_path: '+str(dest.relative_to(Path(output).resolve()))+'\n- pendiente_wiki: true\n\n'+summary+'\n\n'+evidence+'\n')
        for k in pending:
            state.execute('INSERT OR REPLACE INTO receipts VALUES (?,?,?,?)',(k,rows[k]['fingerprint'],str(dest),now()))
        state.commit()
        return {'status':'recorded','messages':len(pending),'summary':str(dest),'memory':str(item),'coverage':'partial'}
    except Exception:
        state.rollback();raise
    finally:
        state.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance',default=os.environ.get('SECRETARY_INSTANCE'))
    parser.add_argument('--config',help='Private temporary configuration for an explicit scoped query')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('probe');sub.add_parser('chats')
    collect=sub.add_parser('collect');collect.add_argument('--chat',action='append');collect.add_argument('--days',type=int,default=30);collect.add_argument('--historical',action='store_true');collect.add_argument('--out',required=True);collect.add_argument('--transcribe',action='store_true');collect.add_argument('--include-reviewed',action='store_true')
    for name in ('audio','transcribe'):
        p=sub.add_parser(name);p.add_argument('local_id',type=int)
        if name=='transcribe':p.add_argument('--provider')
    p=sub.add_parser('record');p.add_argument('--batch',required=True);p.add_argument('--review',required=True);p.add_argument('--output-root',required=True)
    args=parser.parse_args(argv)
    if not args.instance:parser.error('--instance o SECRETARY_INSTANCE requerido')
    try:
        cfg=read_config(args.instance,args.config)
        if args.command=='probe':result=probe(cfg)
        elif args.command=='chats':result=chats(cfg)
        elif args.command=='collect':
            result=capture(cfg,args.instance,args.chat,args.days,args.historical,args.transcribe,args.include_reviewed)
            atomic_json(args.out,result)
            result={'batch':args.out,'messages':len(result['messages']),'discovery_count':len(result['discovery_metadata_only'])}
        elif args.command=='audio':result={'path':str(fetch_audio(cfg,args.instance,args.local_id))}
        elif args.command=='transcribe':result=transcribe(cfg,args.instance,args.local_id,args.provider)
        else:result=record(cfg,args.instance,args.output_root,args.batch,args.review)
    except (ValueError,OSError,sqlite3.Error) as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False),file=sys.stderr);return 1
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0


if __name__=='__main__':
    raise SystemExit(main())
