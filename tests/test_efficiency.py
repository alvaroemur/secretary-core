import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from secretary import efficiency as e
from secretary.portable_deploy import deployment

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


class EfficiencyTests(unittest.TestCase):
    def test_rows_reject_truncated_or_unrecognized_response(self):
        self.assertEqual(e.rows([[], [{'number': 1}]], 'issues'), [{'number': 1}])
        with self.assertRaises(ValueError): e.rows({'threads': [], 'nextPageToken': 'more'}, 'threads')
        with self.assertRaises(ValueError): e.rows({}, 'threads')

    def test_dispatch_excludes_claimed_and_done_without_mutation(self):
        cfg = {'dispatch': {'executor': {'repos': [{'repo': 'owner/repo', 'path': '/repo'}]}}}
        issues = [{'number': 1, 'updated_at': 'a', 'labels': [{'name': 'dispatch:execute'}]},
                  {'number': 2, 'updated_at': 'a', 'labels': [{'name': 'dispatch:running'}]},
                  {'number': 3, 'updated_at': 'a', 'labels': [{'name': 'dispatch:done'}]}]
        with patch.object(e, 'query', return_value=[issues]) as query:
            inv, work = e.routine_inventory('dispatch-executor', Path('/repo'), cfg, NOW)
        self.assertTrue(work); self.assertEqual(len(inv), 1)
        self.assertIn('--paginate', query.call_args.args[0])

    def test_query_failure_is_error_not_noop(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(e, 'routine_inventory', side_effect=RuntimeError('consulta fallida')):
            state = Path(tmp); ticket = state / 'ticket.json'
            self.assertEqual(e.preflight('wiki-update', ticket, state, {}, state, NOW), 20)
            self.assertEqual(json.loads(ticket.read_text())['outcome'], 'error')
            self.assertFalse((state / 'wiki-update.completed.json').exists())

    def test_partial_completion_does_not_suppress_retry(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(e, 'routine_inventory', return_value=({'day': '2026-10-04'}, False)):
            state = Path(tmp); ticket = state / 'ticket.json'
            decision = e.gate('wiki-update', state, {}, state, NOW); e.write_json(ticket, decision)
            e.complete(ticket, state, 'partial', 'pasos pendientes')
            self.assertEqual(e.gate('wiki-update', state, {}, state, NOW)['outcome'], 'work')
            e.complete(ticket, state, 'completed', 'todos los pasos completos')
            self.assertEqual(e.gate('wiki-update', state, {}, state, NOW)['outcome'], 'noop')
            count = len((state / 'metrics.jsonl').read_text().splitlines())
            e.complete(ticket, state, 'completed', 'todos los pasos completos')
            self.assertEqual(len((state / 'metrics.jsonl').read_text().splitlines()), count)

    def test_new_inventory_is_pending_after_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp);ticket = state/'ticket.json'
            with patch.object(e,'routine_inventory',return_value=({'files':['old']},False)):
                e.write_json(ticket,e.gate('wiki-update',state,{},state,NOW))
            e.complete(ticket,state,'completed','terminado')
            with patch.object(e,'routine_inventory',return_value=({'files':['new']},False)):
                self.assertEqual(e.gate('wiki-update',state,{},state,NOW)['outcome'],'work')

    def test_mail_keeps_aging_followups_and_weekly_report(self):
        cfg={'accounts':{'personal':'your.personal.email@gmail.com'},'account_usage':{'revision_correo':['personal']}}
        with patch.object(e,'query',side_effect=[{'threads':[{'id':'sent'}]},{'drafts':[]}]), patch.object(e,'file_inventory',return_value={}):
            _, mandatory=e.routine_inventory('revision-correo',Path('/repo'),cfg,NOW)
        self.assertTrue(mandatory)
        friday=datetime(2026,10,2,12,tzinfo=timezone.utc)
        with patch.object(e,'query',side_effect=[{'threads':[]},{'drafts':[]}]), patch.object(e,'file_inventory',return_value={}):
            _,mandatory=e.routine_inventory('revision-correo',Path('/repo'),cfg,friday)
        self.assertTrue(mandatory)

    def test_snapshot_does_not_include_unrelated_dirt_or_last_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp); subprocess.run(['git','init','-q',tmp],check=True)
            subprocess.run(['git','-C',tmp,'-c','user.name=Test','-c','user.email=your.personal.email@gmail.com','commit','--allow-empty','-qm','initial'],check=True)
            (repo/'ours.md').write_text('ours');(repo/'other.md').write_text('other')
            snapshot=e.close_snapshot(repo,'s',['ours.md'],['regla estable'],['continuar'])
            self.assertEqual([x['path'] for x in snapshot['files']],['ours.md'])
            self.assertEqual(e.close_snapshot(repo,'s',[],[],[])['files'],[])
            with self.assertRaises(ValueError):e.close_snapshot(repo,'s',['../outside.md'],[],[])

    def test_transcript_copies_and_stream_fragments_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);events=[]
            for count in [1,3]:
                events.append({'type':'assistant','sessionId':'s','timestamp':'2026-10-04T00:00:00Z',
                    'message':{'id':'m','model':'model','usage':{'output_tokens':count}}})
            content=''.join(json.dumps(x)+'\n' for x in events)
            a=root/'a.jsonl';b=root/'b.jsonl';a.write_text(content);b.write_text(content)
            records=e.import_usage([a,b])
            self.assertEqual(len(records),1);self.assertEqual(records[0]['tokens']['output'],3)
            self.assertIsNone(records[0]['tokens']['input'])
            report=e.summarize(records,'2026-10-04','2026-10-05')
            self.assertEqual(report['groups']['interactive/unknown']['unknown']['input'],1)

    def test_codex_cumulative_totals_are_not_summed_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'codex.jsonl';events=[{'type':'session_meta','payload':{'id':'s'}}]
            for count in [10,10,20]:
                events.append({'type':'event_msg','timestamp':'2026-10-04T00:00:00Z','payload':{'type':'token_count',
                    'info':{'total_token_usage':{'input_tokens':count,'cached_input_tokens':count//2,'output_tokens':count//2}}}})
            path.write_text(''.join(json.dumps(x)+'\n' for x in events))
            records=e.import_usage([path]);self.assertEqual(len(records),2)
            self.assertEqual(sum(r['tokens']['input'] for r in records),10)
            self.assertTrue(all(r['tokens']['cache_write'] is None for r in records))

    def test_deployment_is_reproducible_and_dry_run_is_readonly(self):
        source=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'skills';runtime=root/'runtime'
            deployment(source,[target],runtime)
            self.assertFalse(target.exists())
            deployment(source,[target],runtime,True)
            self.assertTrue(all(not x['changed'] for x in deployment(source,[target],runtime)))

    def test_existing_metrics_preserve_unknown_and_native_usage(self):
        path=Path(__file__).resolve().parents[1]/'secretary/routines/metrics/parse-routine-metrics.py'
        spec=importlib.util.spec_from_file_location('metrics',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.jsonl';path.write_text(json.dumps({'type':'result','subtype':'success','usage':{'output_tokens':5}}))
            usage=m.parse_jsonl(path)['usage']
            self.assertEqual(usage['output'],5);self.assertIsNone(usage['input']);self.assertIsNone(usage['total'])
            self.assertIsNone(m._estimate_cost_usd(usage,{}))


if __name__=='__main__':unittest.main()
