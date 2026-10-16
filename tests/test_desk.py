import tempfile
import unittest
from pathlib import Path
from secretary.desk import authority, scope_hash, protected_changes, select_repos
from secretary.desk_deploy import deployment
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from secretary.desk import notify, publish_event


class DeskTests(unittest.TestCase):
    def test_label_alone_is_not_authority(self):
        issue={'body':'Trabajo','state':'OPEN','labels':[{'name':'dispatch:execute'}]}
        self.assertEqual(authority(issue,'owner',{})['state'],'needs-decision')

    def test_manual_authorization_is_invalidated_by_scope_change(self):
        issue={'body':'Trabajo','state':'OPEN','comments':[{'author':{'login':'owner'},
               'body':'desk:authorize '+scope_hash('Trabajo'),'url':'comment'}]}
        self.assertEqual(authority(issue,'owner',{})['state'],'owner-authorized')
        issue['body']='Trabajo ampliado'
        self.assertEqual(authority(issue,'owner',{})['state'],'needs-decision')

    def test_agent_cannot_impersonate_manual_authorization(self):
        issue={'body':'Trabajo','state':'OPEN','comments':[{'author':{'login':'owner'},
               'body':'<!-- agent-generated:sesion -->\ndesk:authorize '+scope_hash('Trabajo')}]}
        self.assertEqual(authority(issue,'owner',{})['state'],'needs-decision')

    def test_policy_allows_preparation_but_not_send_or_merge(self):
        import json
        policy={'enabled':True,'id':'prepare-pr-v1'}
        p={'policy':'prepare-pr-v1','kind':'prepare-pr','effects':['local-edit','open-pr'],'requires_decision':False}
        def issue():return {'body':'<!-- desk:proposal '+json.dumps(p)+' -->','state':'OPEN'}
        self.assertEqual(authority(issue(),'owner',policy)['state'],'policy-authorized')
        for effect in ['send','merge','spend','publish','share']:
            p['effects']=['local-edit',effect]
            self.assertEqual(authority(issue(),'owner',policy)['state'],'needs-decision')

    def test_protected_policy_files_and_untracked_secrets_are_blocked(self):
        self.assertEqual(protected_changes(['src/feature.py','tests/test_feature.py']),[])
        self.assertEqual(len(protected_changes(['AGENTS.md','.github/workflows/ci.yml','.env','canon/rules.md'])),4)

    def test_context_selects_project_or_container_without_global_expansion(self):
        repos=[{'repo':'owner/a','path':'/work/a'},{'repo':'owner/b','path':'/work/b'}]
        self.assertEqual(select_repos(Path('/work/a/src'),repos),repos[:1])
        self.assertEqual(select_repos(Path('/work'),repos),repos)
        self.assertEqual(select_repos(Path('/elsewhere'),repos),[])

    def test_deploy_dry_run_and_apply_are_reproducible(self):
        source=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'skills';runtime=root/'runtime'
            deployment(source,[target],runtime)
            self.assertFalse(target.exists())
            deployment(source,[target],runtime,True)
            self.assertTrue((target/'desk-overview/SKILL.md').exists())
            self.assertTrue((target/'pulse/SKILL.md').exists())
            self.assertTrue(all(not x['changed'] for x in deployment(source,[target],runtime)))

    def test_catalog_does_not_count_alias_as_an_extra_procedure(self):
        from secretary.context import collect_skills
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            for name in ['pulse','desk-overview']:
                p=home/'.agents/skills'/name/'SKILL.md';p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('---\nname: '+name+'\ndescription: Consulta el estado\n---\n')
            with patch('secretary.context.Path.home',return_value=home),patch('secretary.context.core_root',return_value=home/'core'):
                self.assertEqual([s.name for s in collect_skills()],['desk-overview'])

    def test_notification_only_targets_configured_owner_and_is_once_daily(self):
        cfg={'desk':{'notifications':{'brief_email':True}},'accounts':{'personal':'sender@example.com'},
             'brief':{'repo':'owner/notes','label':'brief'},'timezone':'UTC'}
        calls=[]
        def fake(args):
            calls.append(args)
            if args[0]=='gh':return json.dumps({'createdAt':datetime.now(ZoneInfo('UTC')).isoformat(),'url':'issue','labels':[{'name':'brief'}]})
            if 'search' in args:return json.dumps({'threads':[]})
            return json.dumps({'id':'message'})
        with tempfile.TemporaryDirectory() as tmp, patch('secretary.desk.instance_root',return_value=Path(tmp)), patch('secretary.desk.command',side_effect=fake):
            body=Path(tmp)/'body';body.write_text('Reporte')
            self.assertEqual(notify(cfg,'owner/notes',1,body)['state'],'sent')
            self.assertEqual(notify(cfg,'owner/notes',1,body)['state'],'already-sent')
            sends=[c for c in calls if 'send' in c]
            self.assertEqual(len(sends),1)
            self.assertEqual(sends[0][sends[0].index('--to')+1],'sender@example.com')
            with self.assertRaises(ValueError):notify(cfg,'another/repo',1,body)

    def test_notification_can_send_from_configured_alias_to_owner_only(self):
        cfg={'desk':{'notifications':{'brief_email':True,'send_account':'your.work.email@company.com','from':'dest@example.com'}},
             'accounts':{'personal':'sender@example.com','work':'your.work.email@company.com'},
             'brief':{'repo':'owner/notes','label':'brief'},'timezone':'UTC'}
        calls=[]
        def fake(args):
            calls.append(args)
            if args[0]=='gh':return json.dumps({'createdAt':datetime.now(ZoneInfo('UTC')).isoformat(),'url':'issue','title':'Brief','number':1,'body':'## ✅ Requiere tu decisión\n\n- [ ] ver #12\n','labels':[{'name':'brief'}]})
            if 'search' in args:return json.dumps({'threads':[]})
            return json.dumps({'id':'message'})
        with tempfile.TemporaryDirectory() as tmp, patch('secretary.desk.instance_root',return_value=Path(tmp)), patch('secretary.desk.command',side_effect=fake):
            body=Path(tmp)/'body';body.write_text('Reporte')
            self.assertEqual(notify(cfg,'owner/notes',1,body)['state'],'sent')
            send=[c for c in calls if 'send' in c][0]
            html_path=Path(send[send.index('--body-html-file')+1])
            self.assertIn('Requiere tu decisión',html_path.read_text())
            self.assertEqual(send[send.index('--account')+1],'your.work.email@company.com')
            self.assertEqual(send[send.index('--from')+1],'dest@example.com')
            self.assertEqual(send[send.index('--to')+1],'sender@example.com')
            search=[c for c in calls if 'search' in c][0]
            self.assertEqual(search[search.index('--account')+1],'your.work.email@company.com')

    def test_notification_rejects_unregistered_send_account(self):
        cfg={'desk':{'notifications':{'brief_email':True,'send_account':'your.personal.email@gmail.com'}},
             'accounts':{'personal':'sender@example.com'},'brief':{'repo':'owner/notes','label':'brief'},'timezone':'UTC'}
        with tempfile.TemporaryDirectory() as tmp, patch('secretary.desk.instance_root',return_value=Path(tmp)), patch('secretary.desk.command') as cmd:
            body=Path(tmp)/'body';body.write_text('Reporte')
            with self.assertRaisesRegex(ValueError,'send_account'):notify(cfg,'owner/notes',1,body)
            cmd.assert_not_called()

    def test_uncertain_notification_does_not_retry_send(self):
        cfg={'desk':{'notifications':{'brief_email':True}},'accounts':{'personal':'sender@example.com'},
             'brief':{'repo':'owner/notes','label':'brief'},'timezone':'UTC'}
        def fake(args):
            if args[0]=='gh':return json.dumps({'createdAt':datetime.now(ZoneInfo('UTC')).isoformat(),'url':'issue','labels':[{'name':'brief'}]})
            if 'search' in args:return json.dumps({'threads':[]})
            raise RuntimeError('Envío incierto')
        with tempfile.TemporaryDirectory() as tmp, patch('secretary.desk.instance_root',return_value=Path(tmp)), patch('secretary.desk.command',side_effect=fake):
            body=Path(tmp)/'body';body.write_text('Reporte')
            with self.assertRaises(RuntimeError):notify(cfg,'owner/notes',1,body)
            with self.assertRaisesRegex(ValueError,'incierto'):notify(cfg,'owner/notes',1,body)

    def test_event_does_not_publish_into_yesterdays_brief(self):
        from datetime import timedelta
        cfg={'brief':{'repo':'owner/notes','label':'brief'},'timezone':'UTC'}
        old={'number':1,'createdAt':(datetime.now(ZoneInfo('UTC'))-timedelta(days=1)).isoformat()}
        with patch('secretary.desk.command',return_value=json.dumps([old])) as cmd:
            self.assertEqual(publish_event(cfg,'Aviso','routine')['state'],'no-brief-today')
            self.assertEqual(cmd.call_count,1)

    def test_same_event_is_not_published_twice(self):
        import hashlib
        cfg={'brief':{'repo':'owner/notes','label':'brief'},'timezone':'UTC'}
        today={'number':1,'createdAt':datetime.now(ZoneInfo('UTC')).isoformat()}
        marker='<!-- desk:event '+hashlib.sha256(b'routine\nAviso').hexdigest()+' -->'
        with patch('secretary.desk.command',side_effect=[json.dumps([today]),json.dumps({'comments':[{'body':marker}]})]):
            self.assertEqual(publish_event(cfg,'Aviso','routine')['state'],'already-published')


if __name__=='__main__':unittest.main()
