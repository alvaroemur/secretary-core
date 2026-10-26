import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from secretary.desk_deploy import deployment
from secretary.dream import entrega_meta, open_dream_prs
from secretary.dream_hook import fresh, overlaps

ROOT = Path(__file__).resolve().parents[1]


class DreamOpenPrsTests(unittest.TestCase):
    def test_keeps_only_dream_branches_and_drops_report_files(self):
        listing = [
            {'number': 7, 'title': 'Diagnóstico', 'url': 'u7', 'headRefName': 'dream/erp-2026-10-26',
             'files': [{'path': 'docs/runbook.md'}, {'path': 'subsystem/dream/latest.json'}],
             'createdAt': '2026-10-26T10:00:00Z', 'reviews': [], 'reviewDecision': '',
             'body': '<!-- dream:entrega {"tipo": "diagnostico", "compromiso": "acc-1"} -->'},
            {'number': 8, 'title': 'Otro', 'url': 'u8', 'headRefName': 'skills/x', 'files': [],
             'createdAt': '', 'reviews': [], 'reviewDecision': '', 'body': ''},
        ]
        run = lambda *a, **k: subprocess.CompletedProcess(a, 0, json.dumps(listing), '')
        prs = open_dream_prs([{'repo': 'o/r', 'path': '/w/r'}], run=run)
        self.assertEqual([p['number'] for p in prs], [7])
        self.assertEqual(prs[0]['files'], ['docs/runbook.md'])
        self.assertFalse(prs[0]['reviewed'])
        self.assertEqual(prs[0]['entrega']['tipo'], 'diagnostico')

    def test_entrega_meta_tolerates_missing_or_broken_marker(self):
        self.assertEqual(entrega_meta(''), {})
        self.assertEqual(entrega_meta('<!-- dream:entrega {roto} -->'), {})


class DreamHookTests(unittest.TestCase):
    def cache(self, repo):
        return {'generated_at': datetime.now(timezone.utc).isoformat(),
                'prs': [{'repo': 'o/r', 'number': 7, 'path': str(repo), 'branch': 'dream/erp-x',
                         'title': 'Diagnóstico', 'url': 'u7', 'files': ['docs/runbook.md']}]}

    def test_overlap_in_checkout_and_session_worktrees_but_not_in_own_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            cache = self.cache(repo)
            self.assertEqual(len(overlaps(cache, str(repo/'docs/runbook.md'))), 1)
            self.assertEqual(len(overlaps(cache, str(repo/'.wt/skills-y/docs/runbook.md'))), 1)
            self.assertEqual(len(overlaps(cache, str(repo/'.claude/worktrees/abc/docs/runbook.md'))), 1)
            self.assertEqual(overlaps(cache, str(repo/'.wt/dream-erp-x/docs/runbook.md')), [])
            self.assertEqual(overlaps(cache, str(repo/'docs/otro.md')), [])
            self.assertEqual(overlaps(cache, '/elsewhere/docs/runbook.md'), [])

    def test_stale_cache_is_silent(self):
        old = {'generated_at': (datetime.now(timezone.utc) - timedelta(hours=40)).isoformat()}
        self.assertFalse(fresh(old))
        self.assertFalse(fresh({}))

    def test_hook_warns_once_per_session_and_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'state'; repo = Path(tmp)/'repo'
            (state/'dream').mkdir(parents=True)
            (state/'dream/open-prs.json').write_text(json.dumps(self.cache(repo)))
            env = {**os.environ, 'SECRETARY_STATE_DIR': str(state)}
            event = json.dumps({'session_id': 's1', 'tool_input': {'file_path': str(repo/'docs/runbook.md')}})
            hook = [sys.executable, str(ROOT/'secretary/dream_hook.py')]
            first = subprocess.run(hook, input=event, capture_output=True, text=True, env=env)
            self.assertEqual(first.returncode, 0)
            self.assertIn('o/r#7', json.loads(first.stdout)['hookSpecificOutput']['additionalContext'])
            second = subprocess.run(hook, input=event, capture_output=True, text=True, env=env)
            self.assertEqual((second.returncode, second.stdout), (0, ''))
            broken = subprocess.run(hook, input='no json', capture_output=True, text=True, env=env)
            self.assertEqual((broken.returncode, broken.stdout), (0, ''))


class RetiredSkillsTests(unittest.TestCase):
    def test_retired_dream_and_heartbeat_skills_are_not_sources(self):
        for name in ['desk-dream', 'desk-heartbeat', 'sec-dream', 'sec-heartbeat']:
            self.assertFalse((ROOT/'skills'/name).exists(), name)
        for name in ['sec-dream', 'sec-heartbeat']:
            self.assertTrue((ROOT/'playbooks'/name/'procedure.md').is_file(), name)

    def test_deploy_removes_installed_copies_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); agents = root/'agents'; claude = root/'claude'; codex = root/'codex'
            for folder in [agents, codex]:
                for name in ['desk-dream', 'sec-heartbeat']:
                    (folder/name).mkdir(parents=True)
                    (folder/name/'SKILL.md').write_text('old')
            claude.mkdir()
            (claude/'desk-dream').symlink_to(agents/'desk-dream', target_is_directory=True)
            plan = deployment(ROOT, [agents], root/'runtime', links=[claude], prunes=[codex])
            self.assertEqual(len([p for p in plan if 'retire' in p]), 5)
            self.assertTrue((agents/'desk-dream').exists())
            deployment(ROOT, [agents], root/'runtime', True, links=[claude], prunes=[codex])
            for folder in [agents, claude, codex]:
                for name in ['desk-dream', 'sec-heartbeat']:
                    self.assertFalse((folder/name).exists() or (folder/name).is_symlink())
            self.assertTrue((root/'runtime/dream_hook.py').is_file())
            self.assertTrue((agents/'desk-overview/SKILL.md').is_file())


if __name__ == '__main__':
    unittest.main()
