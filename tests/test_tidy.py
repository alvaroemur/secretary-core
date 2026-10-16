import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from secretary.tidy import claim, evaluate, inspect, observe, scope, status_paths, validate


class TidyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.request = {'version': 1, 'action': 'reorganize', 'targets': [{'from': 'docs/old', 'to': 'docs/new'}]}
        self.observed = {'captured_at': self.now.isoformat(), 'worktrees': [{'dirty': []}], 'pending': [], 'prs': [], 'errors': []}
        self.activity = {'captured_at': self.now.isoformat(), 'coverage': 'known', 'source': 'trusted-collector', 'active': []}

    def result(self, **kw):
        return evaluate(self.request, self.observed, ['docs/old', 'docs/new'], [], [], now=self.now, **kw)

    def test_claim_serializes_repo_and_wrong_token_cannot_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = claim(root, 'owner/repo', 'a' * 64)
            with self.assertRaises(ValueError): claim(root, 'owner/repo', 'b' * 64)
            with self.assertRaises(ValueError): claim(root, 'owner/repo', '', 'wrong')
            self.assertEqual(claim(root, 'owner/repo', '', first['token'])['state'], 'released')
            second = claim(root, 'owner/repo', 'b' * 64)
            with self.assertRaises(ValueError): claim(root, 'owner/repo', '', first['token'])
            self.assertNotEqual(first['token'], second['token'])

    def test_duplicate_destinations_and_crossed_targets_are_rejected(self):
        self.request['targets'].append({'from': 'other/source', 'to': 'docs/new'})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): validate(self.request, Path(tmp))

    def test_parked_clean_worktrees_do_not_block(self):
        self.observed['worktrees'] *= 5
        self.assertEqual(self.result()['state'], 'eligible-for-pr')
        self.assertEqual(self.result()['effects'], [])

    def test_unknown_harness_requires_every_worktree_clean_and_no_pr(self):
        self.observed['worktrees'].append({'dirty': ['unrelated/file']})
        self.assertEqual(self.result()['state'], 'blocked')
        self.observed['worktrees'] = [{'dirty': []}]
        self.observed['prs'] = [{'number': 3}]
        self.assertEqual(self.result()['state'], 'blocked')

    def test_known_activity_blocks_only_affected_paths(self):
        self.observed['pending'] = [{'kind': 'pr', 'paths': ['other/file'], 'source': 'pr'}]
        self.observed['prs'] = [{'number': 3}]
        self.activity['active'] = [{'paths': ['other/file'], 'ref': 'session'}]
        self.assertEqual(self.result(activity=self.activity)['state'], 'eligible-for-pr')
        self.activity['active'] = [{'paths': ['docs/old/file'], 'ref': 'session'}]
        self.assertEqual(self.result(activity=self.activity)['state'], 'blocked')

    def test_pending_stash_or_commit_overlapping_parent_blocks(self):
        for kind in ['stash', 'unmerged-commit', 'dirty', 'pr']:
            self.observed['pending'] = [{'kind': kind, 'paths': ['docs'], 'source': kind}]
            self.assertEqual(self.result(activity=self.activity)['state'], 'blocked')

    def test_unknown_scope_and_failed_reads_block(self):
        self.observed['pending'] = [{'kind': 'pr', 'paths': [], 'source': 'pr'}]
        self.assertEqual(self.result(activity=self.activity)['state'], 'blocked')
        self.observed['pending'] = []
        self.observed['errors'] = ['API unavailable']
        self.assertEqual(self.result()['state'], 'blocked')

    def test_stale_or_future_evidence_blocks(self):
        for delta in [-301, 30]:
            self.observed['captured_at'] = (self.now + timedelta(seconds=delta)).isoformat()
            self.assertEqual(self.result()['state'], 'blocked')
        self.observed['captured_at'] = self.now.isoformat()
        self.activity['captured_at'] = (self.now - timedelta(seconds=301)).isoformat()
        self.assertEqual(self.result(activity=self.activity)['state'], 'blocked')

    def test_condition_false_waits_unknown_blocks(self):
        for value, expected in [(False, 'waiting'), (None, 'blocked'), (True, 'eligible-for-pr')]:
            result = evaluate(self.request, self.observed, ['docs/old'], [], [{'value': value}], now=self.now)
            self.assertEqual(result['state'], expected)

    def test_delete_and_archive_are_always_proposals(self):
        for action in ['delete', 'archive']:
            self.request['action'] = action
            self.assertEqual(self.result()['state'], 'proposal-only')

    def test_invalid_paths_overlap_and_unknown_conditions_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ['../escape', '/absolute', '.git/config', '.', 'bad\npath']:
                self.request['targets'][0]['from'] = path
                with self.assertRaises(ValueError): validate(self.request, root)
            self.request['targets'][0]['from'] = 'docs'
            with self.assertRaises(ValueError): validate(self.request, root)
            self.request['targets'][0]['from'] = 'docs/old'
            self.request['conditions'] = [{'type': 'run-shell', 'command': 'echo'}]
            with self.assertRaises(ValueError): validate(self.request, root)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp); (root/'docs').symlink_to(outside)
            with self.assertRaises(ValueError): validate(self.request, root)

    def test_status_rename_has_both_paths_and_spaces(self):
        self.assertEqual(status_paths('R  docs/new name\0docs/old name\0?? other\0'), ['docs/new name', 'docs/old name', 'other'])

    def test_references_expand_scope_and_ambiguous_basename_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'index.md').write_text('docs/old')
            (root/'other.md').write_text('see old')
            with patch('secretary.tidy.git', return_value='index.md\0other.md\0'):
                affected, errors = scope(validate(self.request, root), root)
            self.assertIn('index.md', affected)
            self.assertTrue(errors)

    def test_real_git_collects_dirty_commits_and_untracked_stash_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'repo'; root.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()
            git('init', '-b', 'main'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.com')
            (root/'tracked').write_text('one'); git('add', '.'); git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD'); git('update-ref', 'refs/remotes/origin/main', base)
            wt = Path(tmp)/'parked'; git('worktree', 'add', '-b', 'parked', str(wt))
            (root/'stash-file').write_text('saved'); git('stash', 'push', '--include-untracked', '-m', 'pending')
            (root/'tracked').write_text('two'); git('add', '.'); git('commit', '-m', 'pending commit')
            (wt/'dirty').write_text('pending')
            def gh(args):
                if 'commits/main' in ' '.join(args): return base
                if 'list' in args: return '[]'
                raise AssertionError(args)
            from secretary.tidy import command as actual
            with patch('secretary.tidy.command', side_effect=lambda args: gh(args) if args[0] == 'gh' else actual(args)):
                observed = observe(root, 'owner/repo')
            self.assertEqual(observed['errors'], [])
            kinds = [p['kind'] for p in observed['pending']]
            self.assertEqual(kinds.count('stash'), 1)
            stash = next(p for p in observed['pending'] if p['kind'] == 'stash')
            self.assertIn('stash-file', stash['paths'])
            self.assertIn('dirty', kinds)
            self.assertIn('unmerged-commit', kinds)

    def test_pr_rename_covers_old_path_and_stale_main_blocks(self):
        def fake_git(root, *args):
            if args[:2] == ('worktree', 'list'): return ''
            if args[:1] == ('rev-parse',): return 'local-base\n'
            if args[:2] == ('stash', 'list'): return ''
            raise AssertionError(args)
        def fake(args):
            if 'commits/main' in ' '.join(args): return 'remote-base'
            if 'list' in args: return json.dumps([{'number': 2, 'url': 'pr'}])
            if 'view' in args: return json.dumps({'headRefOid': 'head'})
            return json.dumps([[{'filename': 'docs/new', 'previous_filename': 'docs/old'}]])
        with patch('secretary.tidy.git', side_effect=fake_git), patch('secretary.tidy.command', side_effect=fake):
            result = observe(Path('/repo'), 'owner/repo')
        self.assertIn('docs/old', result['pending'][0]['paths'])
        self.assertTrue(result['errors'])


if __name__ == '__main__': unittest.main()
