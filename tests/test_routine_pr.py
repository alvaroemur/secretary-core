"""Preludio y cierre comunes de rutinas (secretary/routines/ops/routine-pr.sh)."""
from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'secretary/routines/ops/routine-pr.sh'

FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr list") cat "$GH_PRS" 2>/dev/null || true ;;
  "pr create") echo "https://github.com/owner/repo/pull/42" ;;
esac
"""

FAKE_SIG = """#!/usr/bin/env bash
[ "$2" = --mark ] && echo "<!-- mark:$1 -->" || echo "footer:$1"
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


class RoutinePrTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        remote = root / 'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(remote)], check=True)
        self.repo = root / 'repo'
        subprocess.run(['git', 'clone', '-q', str(remote), str(self.repo)], check=True, capture_output=True)
        git(self.repo, 'config', 'user.email', 't@example.invalid')
        git(self.repo, 'config', 'user.name', 't')
        (self.repo / 'a.md').write_text('a\n')
        git(self.repo, 'add', '-A'); git(self.repo, 'commit', '-q', '-m', 'init'); git(self.repo, 'push', '-q', 'origin', 'main')
        bin_dir = root / 'bin'; bin_dir.mkdir()
        (bin_dir / 'gh').write_text(FAKE_GH); (bin_dir / 'gh').chmod(0o755)
        sig = root / 'sig.sh'; sig.write_text(FAKE_SIG); sig.chmod(0o755)
        self.gh_log = root / 'gh.log'; self.gh_prs = root / 'prs.txt'
        self.env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'GH_LOG': str(self.gh_log),
                    'GH_PRS': str(self.gh_prs), 'SECRETARY_SIGNATURE': str(sig),
                    'SECRETARY_INSTANCE': str(self.repo), 'ROUTINE_WT_ROOT': str(root / 'wt'),
                    'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@example.invalid',
                    'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@example.invalid'}
        (root / 'wt').mkdir()
        self.body = root / 'body.md'; self.body.write_text('Resumen de la corrida.\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, *args: str, check: bool = True) -> dict[str, str]:
        out = subprocess.run(['bash', str(SCRIPT), *args], env=self.env, capture_output=True, text=True)
        if check and out.returncode != 0:
            self.fail(out.stderr)
        last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ''
        return dict(part.split('=', 1) for part in shlex.split(last))

    def open(self, *extra: str) -> dict[str, str]:
        return self.run_script('open', '--scope', 'drive', *extra)

    def close(self, opened: dict[str, str], *extra: str) -> dict[str, str]:
        return self.run_script('close', '--wt', opened['WT'], '--branch', opened['BRANCH'], '--title',
                               'chore(drive): corrida', '--body-file', str(self.body), '--routine',
                               'drive-crawler', '--label', 'hilo:drive', *extra)

    def test_open_creates_worktree_from_main(self) -> None:
        opened = self.open()
        self.assertTrue(Path(opened['WT']).is_dir())
        self.assertRegex(opened['BRANCH'], r'^drive/auto-\d{8}-\d{4}$')
        self.assertEqual(opened['BASE'], 'origin/main')
        self.assertEqual(opened.get('PREV_PR', ''), '')

    def test_close_without_changes_cleans_up_and_opens_no_pr(self) -> None:
        opened = self.open()
        self.assertEqual(self.close(opened)['RESULT'], 'no-changes')
        self.assertFalse(Path(opened['WT']).exists())
        self.assertNotIn('pr create', self.gh_log.read_text() if self.gh_log.exists() else '')
        self.assertNotIn(opened['BRANCH'], git(self.repo, 'branch'))

    def test_close_with_changes_pushes_signed_pr_and_closes_superseded(self) -> None:
        opened = self.open()
        (Path(opened['WT']) / 'b.md').write_text('b\n')
        result = self.close(opened, '--supersede', '7')
        self.assertEqual(result['RESULT'], 'pr')
        self.assertEqual(result['PR_NUMBER'], '42')
        log = self.gh_log.read_text()
        self.assertIn('pr create --base main --head ' + opened['BRANCH'], log)
        self.assertIn('--label hilo:drive', log)
        self.assertIn('pr close 7 --delete-branch', log)
        self.assertIn(opened['BRANCH'], git(self.repo, 'ls-remote', '--heads', 'origin'))
        self.assertFalse(Path(opened['WT']).exists())

    def test_open_chains_on_previous_pr(self) -> None:
        git(self.repo, 'checkout', '-q', '-b', 'drive/auto-20261001-0400')
        (self.repo / 'prev.md').write_text('prev\n'); git(self.repo, 'add', '-A'); git(self.repo, 'commit', '-q', '-m', 'prev')
        git(self.repo, 'push', '-q', 'origin', 'drive/auto-20261001-0400'); git(self.repo, 'checkout', '-q', 'main')
        self.gh_prs.write_text('9 drive/auto-20261001-0400\n')
        opened = self.open('--chain-pattern', '^drive/auto-')
        self.assertEqual(opened['BASE'], 'origin/drive/auto-20261001-0400')
        self.assertEqual(opened['PREV_PR'], '9')
        self.assertTrue((Path(opened['WT']) / 'prev.md').exists())
        self.assertEqual(self.close(opened)['RESULT'], 'no-changes')

    def test_dry_run_has_no_side_effects(self) -> None:
        opened = self.open()
        (Path(opened['WT']) / 'b.md').write_text('b\n')
        self.assertEqual(self.close(opened, '--dry-run')['RESULT'], 'pr')
        self.assertTrue(Path(opened['WT']).exists())
        self.assertNotIn(opened['BRANCH'], git(self.repo, 'ls-remote', '--heads', 'origin'))
        self.assertFalse(self.gh_log.exists() and 'pr create' in self.gh_log.read_text())


if __name__ == '__main__':
    unittest.main()
