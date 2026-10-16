import base64
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from secretary.conversations import (Store, digest, notification_plan, plain, reconcile,
                                     scan_github, scan_mail, send_notifications, verify_event, verify_mail, refresh_questions)


def address(local):
    return local + '@' + 'example.com'


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'state.sqlite3'); self.addCleanup(self.store.db.close)
        self.now = datetime.now(timezone.utc)
        self.cfg = {'owner':address('owner'),'mailbox':address('work'),'alias':address('desk'),
                    'capture_since':(self.now-timedelta(days=1)).isoformat(),'question_email':True,
                    'timezone':'UTC','repos':['owner/repo'],'brief_repo':'owner/repo','brief_label':'brief'}

    def message(self, body='Prepare the report', sender=address('owner')):
        return {'id':'mail','threadId':'thread','internalDate':str(int(self.now.timestamp()*1000)),
                'labelIds':['SENT'],'payload':{'mimeType':'text/plain','headers':[
                    {'name':'Message-ID','value':'<' + address('message') + '>'},
                    {'name':'From','value':sender},{'name':'To','value':address('desk')}],
                    'body':{'data':base64.urlsafe_b64encode(body.encode()).decode()}}}

    def add_question(self, key='project-report', due=''):
        question=self.store.question(key,'owner/repo',1,'Which scope? '+key,'a'*64,due)
        self.store.publication(question,'synthetic:question-comment')
        return question

    def test_cli_holds_is_a_global_read_without_issue_arguments(self):
        import io
        from contextlib import redirect_stdout
        from secretary.conversations import main
        config={'accounts':{'personal':address('owner'),'work':address('work')},
                'desk':{'conversations':{'enabled':True,'capture_since':self.cfg['capture_since']},
                        'notifications':{'send_account':address('work'),'from':address('desk')}},
                'brief':{'repo':'owner/repo','label':'brief'},'dispatch':{'executor':{'repos':[]}}}
        output=io.StringIO()
        with patch('secretary.conversations.load_config',return_value=config),patch('sys.argv',['conversations','holds']),patch.dict('os.environ',{'SECRETARY_CONVERSATIONS_DB':str(Path(self.tmp.name)/'state.sqlite3')}),redirect_stdout(output):
            main()
        self.assertEqual(json.loads(output.getvalue()),[])

    def test_disabled_cli_does_not_require_sender_or_initialize_database(self):
        import io
        from contextlib import redirect_stdout
        from secretary.conversations import main
        path=Path(self.tmp.name)/'new.sqlite3';output=io.StringIO()
        with patch('secretary.conversations.load_config',return_value={}),patch('sys.argv',['conversations','pending']),patch.dict('os.environ',{'SECRETARY_CONVERSATIONS_DB':str(path)}),redirect_stdout(output):
            main()
        self.assertEqual(json.loads(output.getvalue())['state'],'disabled')
        self.assertFalse(path.exists())

    def test_closed_issue_stops_reminders_and_changed_scope_requires_new_question(self):
        self.add_question()
        with patch('secretary.conversations.github_issue',return_value={'state':'OPEN','body':'changed'}):
            with self.assertRaises(ValueError): refresh_questions(self.store,self.cfg)
        self.assertEqual(len(self.store.questions()),1)
        with patch('secretary.conversations.github_issue',return_value={'state':'CLOSED','body':'changed'}):
            refresh_questions(self.store,self.cfg)
        self.assertEqual(notification_plan(self.store,self.cfg)['state'],'no-op')

    def test_revocation_gate_blocks_only_its_issue_and_resume_is_not_authority(self):
        event=self.store.capture('owner-stop',{'body':'Pause report'},True)
        self.store.hold('owner/repo',1,event,'Pause report')
        self.assertEqual(self.store.gate('owner/repo',1,'a'*64)['state'],'blocked')
        self.assertEqual(self.store.gate('owner/repo',2,'b'*64)['state'],'clear')
        resume=self.store.capture('owner-resume',{'body':'Resume report'},True)
        self.store.hold('owner/repo',1,resume,'Resume report',False)
        result=self.store.gate('owner/repo',1,'a'*64)
        self.assertEqual(result['state'],'clear')
        self.assertIn('no concede',result['meaning'])
        self.add_question()
        self.assertEqual(self.store.gate('owner/repo',1,'a'*64)['state'],'blocked')

    def test_human_reply_with_quoted_agent_message_is_captured(self):
        message=self.message('Solo informe.\nOn Friday Secretary wrote:\n<!-- agent-generated:notice -->')
        def fake(account,*args):
            return {'messages':[{'threadId':'thread'}]} if 'search' in args else {'thread':{'messages':[message]}}
        with patch('secretary.conversations.gog',side_effect=fake),patch('secretary.conversations.verify_mail',return_value=True):
            scan_mail(self.store,self.cfg)
        self.assertEqual(self.store.pending()[0]['payload']['new_text_hint'],'Solo informe.')

    def test_unpublished_question_blocks_email_until_reconciled(self):
        question=self.store.question('unpublished','owner/repo',1,'Scope?','a'*64)
        self.assertEqual(notification_plan(self.store,self.cfg)['state'],'blocked')
        self.store.publication(question,'synthetic:published')
        self.assertEqual(notification_plan(self.store,self.cfg)['state'],'ready')

    def test_deployment_preserves_private_procedures_and_is_repeatable(self):
        from secretary.conversation_deploy import deploy
        source=Path(__file__).resolve().parents[1];root=Path(self.tmp.name)
        scheduled=root/'scheduled';target=scheduled/'revision-correo/SKILL.md'
        target.parent.mkdir(parents=True);target.write_text('Private procedure.\n')
        deploy(source,scheduled,[],root/'runtime')
        self.assertEqual(target.read_text(),'Private procedure.\n')
        deploy(source,scheduled,[],root/'runtime',True)
        first=target.read_text();self.assertTrue(first.startswith('Private procedure.'))
        self.assertIn('claim-event',first)
        deploy(source,scheduled,[],root/'runtime',True)
        self.assertEqual(first,target.read_text())

    def test_two_workers_cannot_claim_same_event_or_release_others_claim(self):
        event = self.store.capture('source', {'body':'Prepare'}, True)
        first = self.store.claim_event(event)
        self.assertTrue(self.store.pending()[0]['claimed'])
        with self.assertRaises(ValueError): self.store.claim_event(event)
        with self.assertRaises(ValueError): self.store.release(event,'other')
        self.store.release(event,first['token'])
        second = self.store.claim_event(event)
        self.assertNotEqual(first['token'],second['token'])

    def test_event_is_once_and_cannot_ack_before_evidence(self):
        first = self.store.capture('source',{'body':'first'},True)
        self.assertEqual(first,self.store.capture('source',{'body':'first'},True))
        self.assertEqual(len(self.store.pending()),1)
        with self.assertRaises(ValueError): self.store.ack(first,'routed','')
        self.store.ack(first,'routed','issue-comment')
        self.store.ack(first,'routed','issue-comment')
        self.assertEqual(self.store.pending(),[])
        with self.assertRaises(ValueError): self.store.ack(first,'ignored','other')

    def test_spoofed_mail_without_sent_copy_is_not_trusted(self):
        with patch('secretary.conversations.gog',return_value={'messages':[]}):
            self.assertFalse(verify_mail(self.cfg,self.message()))
        event = self.store.capture('mail',{'body':'do this'},False)
        with self.assertRaises(ValueError): self.store.ack(event,'routed','issue')

    def test_sent_copy_must_match_text_id_alias_and_sent_label(self):
        original = self.message()
        def fake(account,*args):
            return {'messages':[{'threadId':'original'}]} if 'search' in args else {'thread':{'messages':[original]}}
        with patch('secretary.conversations.gog',side_effect=fake):
            self.assertTrue(verify_mail(self.cfg,self.message()))
            self.assertFalse(verify_mail(self.cfg,self.message('Different instruction')))
            original['labelIds'] = ['INBOX']
            self.assertFalse(verify_mail(self.cfg,self.message()))

    def test_scan_ignores_third_parties_and_agent_messages(self):
        messages = [self.message(),self.message(sender=address('other')),self.message('<!-- agent-generated:report -->')]
        def fake(account,*args):
            return {'messages':[{'threadId':'thread'}]} if 'search' in args else {'thread':{'messages':messages}}
        with patch('secretary.conversations.gog',side_effect=fake),patch('secretary.conversations.verify_mail',return_value=True):
            scan_mail(self.store,self.cfg); scan_mail(self.store,self.cfg)
        self.assertEqual(len(self.store.pending()),1)

    def test_partial_scan_keeps_failed_thread_visible(self):
        def fake(account,*args):
            if 'search' in args: return {'messages':[{'threadId':'failed'}]}
            raise RuntimeError('Access denied')
        with patch('secretary.conversations.gog',side_effect=fake):
            result = scan_mail(self.store,self.cfg)
        self.assertEqual(len(result['errors']),1)
        self.assertEqual(self.store.pending(),[])

    def test_github_capture_filters_agents_and_preserves_owner_edits(self):
        comment = {'id':2,'body':'Please prepare report','user':{'login':'owner','type':'User'},
                   'html_url':'comment','created_at':self.now.isoformat(),'updated_at':self.now.isoformat()}
        generated = {**comment,'id':3,'body':'<!-- agent-generated:report -->','html_url':'generated'}
        other = {**comment,'id':4,'user':{'login':'other','type':'User'},'html_url':'other'}
        def fake(args,text=None):
            return json.dumps([{'number':1}]) if 'list' in args else json.dumps([[comment,generated,other]])
        with patch('secretary.conversations.run',side_effect=fake):
            scan_github(self.store,self.cfg)
            self.assertEqual(len(self.store.pending()),1)
            comment['body']='Prepare narrower report'
            scan_github(self.store,self.cfg)
        self.assertEqual(len(self.store.pending()),1)
        self.assertEqual(self.store.pending()[0]['payload']['body'],'Prepare narrower report')

    def test_answer_requires_version_scope_and_verified_pending_source(self):
        self.add_question(); event = self.store.capture('source',{'body':'Only report'},True)
        for version,scope in [(2,'a'*64),(1,'b'*64)]:
            with self.assertRaises(ValueError): self.store.answer('project-report',version,event,scope,'Only report')
        self.store.answer('project-report',1,event,'a'*64,'Only report')
        self.assertEqual(self.store.questions(),[])
        # An edit to the original instruction reopens only its own question.
        self.add_question('other-work')
        self.store.capture('source',{'body':'Different scope'},True)
        questions = {q['id']:q for q in self.store.questions()}
        self.assertEqual(questions['project-report']['version'],2)
        self.assertEqual(questions['other-work']['version'],1)

    def test_question_repeat_does_not_bump_version_but_scope_change_does(self):
        self.add_question(); self.add_question()
        self.assertEqual(self.store.questions()[0]['version'],1)
        self.store.question('project-report','owner/repo',1,'Scope?','b'*64)
        self.assertEqual(self.store.questions()[0]['version'],2)
        with self.assertRaises(ValueError): self.store.question('project-report','owner/repo',2,'Scope?','b'*64)

    def test_new_questions_group_and_preview_has_no_send(self):
        self.add_question(); self.add_question('other-work')
        with patch('secretary.conversations.run') as command:
            result = send_notifications(self.store,self.cfg)
        command.assert_not_called()
        self.assertEqual(result['state'],'ready'); self.assertEqual(len(result['questions']),2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM deliveries').fetchone()[0],0)

    def test_uncertain_send_is_reserved_and_never_retried(self):
        self.add_question()
        def fake(*args,**kw): raise RuntimeError('Lost response')
        with patch('secretary.conversations.gog',return_value={'sendAs':{'verificationStatus':'accepted'}}),patch('secretary.conversations.signature',side_effect=lambda t:t),patch('secretary.conversations.run',side_effect=fake):
            with self.assertRaises(RuntimeError): send_notifications(self.store,self.cfg,True)
            self.assertEqual(send_notifications(self.store,self.cfg,True)['state'],'blocked')

    def sent(self, plan, when):
        self.store.db.execute('INSERT INTO deliveries VALUES (?,?,?,?,?,?,?)',
            (plan['id'],'sent',plan['kind'],plan['day'],json.dumps(plan['versions']),'{}',when.isoformat()))
        self.store.db.commit()

    def test_no_immediate_reminder_and_one_per_day(self):
        self.add_question(); plan=notification_plan(self.store,self.cfg,self.now); self.sent(plan,self.now)
        self.assertEqual(notification_plan(self.store,self.cfg,self.now)['state'],'no-op')
        tomorrow=self.now+timedelta(hours=25)
        reminder=notification_plan(self.store,self.cfg,tomorrow)
        self.assertEqual(reminder['kind'],'reminder'); self.sent(reminder,tomorrow)
        self.assertEqual(notification_plan(self.store,self.cfg,tomorrow+timedelta(hours=2))['state'],'no-op')

    def test_deadline_exception_requires_specific_due_and_does_not_repeat(self):
        self.add_question(due=(self.now+timedelta(hours=3)).isoformat())
        first=notification_plan(self.store,self.cfg,self.now-timedelta(hours=2));self.sent(first,self.now-timedelta(hours=2))
        urgent=notification_plan(self.store,self.cfg,self.now)
        self.assertEqual(urgent['kind'],'deadline');self.sent(urgent,self.now)
        self.assertEqual(notification_plan(self.store,self.cfg,self.now+timedelta(hours=1))['state'],'no-op')

    def test_sender_and_recipient_are_fixed_by_config_and_delivery_has_id(self):
        self.add_question(); calls=[]
        def fake(args,text=None): calls.append((args,text)); return json.dumps({'messageId':'sent'})
        with patch('secretary.conversations.gog',return_value={'sendAs':{'verificationStatus':'accepted'}}),patch('secretary.conversations.signature',side_effect=lambda t:t),patch('secretary.conversations.run',side_effect=fake):
            result=send_notifications(self.store,self.cfg,True)
        self.assertEqual(result['state'],'sent')
        args=calls[0][0]
        for flag,value in [('--account',address('work')),('--from',address('desk')),('--to',address('owner')),('--reply-to',address('desk'))]:
            self.assertEqual(args[args.index(flag)+1],value)
        self.assertEqual(send_notifications(self.store,self.cfg,True)['state'],'no-op')

    def test_missing_sent_match_keeps_uncertain_ledger(self):
        self.add_question(); plan=notification_plan(self.store,self.cfg,self.now)
        self.store.db.execute('INSERT INTO deliveries VALUES (?,?,?,?,?,?,?)',(plan['id'],'sending','new',plan['day'],json.dumps(plan['versions']),None,self.now.isoformat()));self.store.db.commit()
        with patch('secretary.conversations.gog',return_value={'messages':[]}):
            self.assertEqual(reconcile(self.store,self.cfg)[0]['state'],'uncertain')
        self.assertEqual(notification_plan(self.store,self.cfg)['state'],'blocked')

    def test_edited_or_deleted_original_is_not_authority(self):
        payload={'kind':'github','repo':'owner/repo','comment':1,'body':'Prepare report','author':'owner','updated_at':'before'}
        event=self.store.capture('comment',payload,True)
        with patch('secretary.conversations.run',return_value=json.dumps({'body':'Changed','updated_at':'after','user':{'login':'owner'}})):
            with self.assertRaises(ValueError): verify_event(self.store,self.cfg,event)


if __name__=='__main__': unittest.main()
