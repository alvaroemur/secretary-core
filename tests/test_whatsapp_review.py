"""Synthetic coverage, WAL, authorization, receipt, and media integrity tests."""
import hashlib
import hmac
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from secretary.whatsapp_review import APPLE_EPOCH, capture, decrypt_media, media_path, probe, record, source


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root/'ChatStorage.sqlite'
        self.writer = sqlite3.connect(self.db)
        self.addCleanup(self.writer.close)
        self.writer.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE ZWACHATSESSION(Z_PK INTEGER,ZCONTACTJID TEXT,ZPARTNERNAME TEXT,ZCONTACTABID INTEGER,ZLASTMESSAGEDATE REAL);
        CREATE TABLE ZWAGROUPMEMBER(Z_PK INTEGER,ZMEMBERJID TEXT);
        CREATE TABLE ZWAMEDIAITEM(Z_PK INTEGER,ZMEDIALOCALPATH TEXT,ZMEDIAURL TEXT,ZMEDIAKEY BLOB);
        CREATE TABLE ZWAMESSAGE(Z_PK INTEGER,ZSTANZAID TEXT,ZTEXT TEXT,ZMESSAGETYPE INTEGER,ZMESSAGEDATE REAL,ZISFROMME INTEGER,ZGROUPMEMBER INTEGER,ZMEDIAITEM INTEGER,ZCHATSESSION INTEGER);
        ''')
        t = datetime.now(timezone.utc).timestamp()-APPLE_EPOCH
        self.writer.executemany('INSERT INTO ZWACHATSESSION VALUES (?,?,?,?,?)',[(1,'approved@lid','Selected',1,t),(2,'other@lid','Other',0,t),(3,'group' + '@g.us','Group',1,t)])
        self.writer.executemany('INSERT INTO ZWAMESSAGE VALUES (?,?,?,?,?,?,?,?,?)',[(1,'one','A commitment',0,t,0,None,None,1),(2,'two','PRIVATE EXCLUDED BODY',0,t,0,None,None,2),(3,'three','Group fact',0,t,0,None,None,3)])
        self.writer.commit()
        self.cfg={'database':str(self.db),'media_root':str(self.root/'media'),'chats':[{'jid':'approved@lid','slug':'selected','active_commitments':False},{'jid':'group' + '@g.us','slug':'group','active_commitments':True}]}

    def batch(self,**kwargs):
        return capture(self.cfg,self.root,**kwargs)

    def test_wal_visible_and_no_database_mutation(self):
        before=self.writer.execute('SELECT count(*) FROM ZWAMESSAGE').fetchone()[0]
        self.assertEqual(probe(self.cfg)['messages'],before)
        self.assertEqual(probe(self.cfg)['sync_status'],'unknown')
        with source(self.db) as c:
            with self.assertRaises(sqlite3.OperationalError):
                c.execute('DELETE FROM ZWAMESSAGE')
        self.assertEqual(self.writer.execute('SELECT count(*) FROM ZWAMESSAGE').fetchone()[0],before)

    def test_excluded_content_not_captured_and_group_author_unknown(self):
        b=self.batch()
        self.assertNotIn('PRIVATE EXCLUDED BODY',json.dumps(b))
        self.assertEqual(len(b['discovery_metadata_only']),1)
        self.assertIsNone(next(m for m in b['messages'] if m['chat']=='group')['sender_jid'])

    def test_history_and_allowlist_guards(self):
        with self.assertRaises(ValueError):self.batch(days=91)
        self.assertEqual(self.batch(days=91,historical=True)['days'],91)
        with self.assertRaises(ValueError):self.batch(selectors=['other@lid'])

    def test_partial_receipts_edit_and_missing_output_recovery(self):
        b=self.batch();self.assertEqual(len(b['messages']),2)
        bp=self.root/'batch.json';bp.write_text(json.dumps(b))
        rp=self.root/'review.json';rp.write_text(json.dumps({'message_keys':[b['messages'][0]['key']],'summary':'Recorded decision'}))
        with patch.dict('os.environ',{'SECRETARY_RUNTIME':'codex'}):
            result=record(self.cfg,self.root,self.root,bp,rp)
        self.assertEqual(result['messages'],1)
        self.assertEqual(record(self.cfg,self.root,self.root,bp,rp)['status'],'already_recorded')
        self.assertEqual(len(self.batch()['messages']),1)
        self.writer.execute('UPDATE ZWAMESSAGE SET ZTEXT=? WHERE Z_PK=1',('Changed commitment',));self.writer.commit()
        self.assertEqual(len(self.batch()['messages']),2)
        Path(result['summary']).unlink()
        self.assertEqual(len(self.batch()['messages']),2)

    def test_include_reviewed_supports_raw_evidence_queries(self):
        b=self.batch();bp=self.root/'batch.json';bp.write_text(json.dumps(b))
        rp=self.root/'review.json';rp.write_text(json.dumps({'message_keys':[b['messages'][0]['key']],'summary':'A supported fact'}))
        record(self.cfg,self.root,self.root,bp,rp)
        self.assertEqual(len(self.batch()['messages']),1)
        self.assertEqual(len(self.batch(include_reviewed=True)['messages']),2)

    def test_audio_cannot_be_receipted_without_reviewed_transcript(self):
        b=self.batch();b['messages'][0]['audio_eligible']=True
        bp=self.root/'batch.json';bp.write_text(json.dumps(b))
        rp=self.root/'review.json';rp.write_text(json.dumps({'message_keys':[b['messages'][0]['key']],'summary':'No transcript read'}))
        with self.assertRaises(ValueError):record(self.cfg,self.root,self.root,bp,rp)
        self.assertEqual(len(self.batch()['messages']),2)

    def test_api_fallback_requires_explicit_configuration(self):
        from secretary.whatsapp_review import transcribe
        self.cfg['transcription']={'default':'local','fallback':None}
        with patch('secretary.whatsapp_review._transcribe',side_effect=ValueError('local failed')) as backend:
            with self.assertRaises(ValueError):transcribe(self.cfg,self.root,1)
            self.assertEqual(backend.call_count,1)
        self.cfg['transcription']['fallback']='configured-api'
        with patch('secretary.whatsapp_review._transcribe',side_effect=[ValueError('local failed'),{'text':'fallback'}]) as backend:
            self.assertEqual(transcribe(self.cfg,self.root,1)['text'],'fallback')
            self.assertEqual(backend.call_args.args[-1],'configured-api')
        with patch('secretary.whatsapp_review._transcribe',side_effect=ValueError('explicit failed')) as backend:
            with self.assertRaises(ValueError):transcribe(self.cfg,self.root,1,'explicit-provider')
            self.assertEqual(backend.call_count,1)

    def test_record_is_visible_to_existing_wiki_inventory(self):
        import importlib.util
        script=Path(__file__).resolve().parents[1]/'secretary/routines/ops/wiki-pending.py'
        spec=importlib.util.spec_from_file_location('review_wiki_pending',script)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        b=self.batch();bp=self.root/'batch.json';bp.write_text(json.dumps(b))
        rp=self.root/'review.json';rp.write_text(json.dumps({'message_keys':[b['messages'][0]['key']],'summary':'A durable finding'}))
        record(self.cfg,self.root,self.root,bp,rp)
        inventory=mod.build(self.root,None,False)
        self.assertEqual(inventory['total'],1)
        self.assertIn('memory/reviews/',inventory['items'][0]['archivo'])

    def test_media_path_escape_rejected(self):
        with self.assertRaises(ValueError):media_path(self.cfg,'../private.opus')

    def test_authenticated_decryption_and_tamper(self):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        except ImportError:
            self.skipTest('optional cryptography dependency')
        key=bytes(range(32));prk=hmac.digest(bytes(32),key,'sha256');expanded=prev=b''
        for n in range(1,5):
            prev=hmac.digest(prk,prev+b'WhatsApp Audio Keys'+bytes([n]),'sha256');expanded+=prev
        plain=b'OggS synthetic test';pad=16-len(plain)%16
        e=Cipher(algorithms.AES(expanded[16:48]),modes.CBC(expanded[:16])).encryptor()
        enc=e.update(plain+bytes([pad])*pad)+e.finalize()
        payload=enc+hmac.digest(expanded[48:80],expanded[:16]+enc,'sha256')[:10]
        self.assertEqual(decrypt_media(payload,key),plain)
        with self.assertRaises(ValueError):decrypt_media(bytes([payload[0]^1])+payload[1:],key)


if __name__=='__main__':unittest.main()
