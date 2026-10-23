"""Recolector de hilos nuevos de revision-correo (secretary/routines/ops/mail-collect.py)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'secretary/routines/ops/mail-collect.py'

FAKE_SECRETARY = """#!/usr/bin/env bash
case "$3" in
  account_usage.revision_correo) echo '["personal", "work"]' ;;
  accounts.personal) echo 'p@localhost' ;;
  accounts.work) echo 'w@localhost' ;;
  *) exit 1 ;;
esac
"""

# Responde según la cuenta y el subcomando; registra cada llamada.
FAKE_GOG = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ['GOG_LOG'], 'a').write(' '.join(args) + '\\n')
account = next(a.split('=', 1)[1] for a in args if a.startswith('--account='))
if account.startswith('w@'):
    print('invalid_grant: token expired', file=sys.stderr); sys.exit(1)
if args[1] == 'search':
    print(json.dumps({'threads': [
        {'id': 't1', 'date': '2026-10-22 10:00', 'from': 'A <a@localhost>', 'subject': 'Hola\\tmundo',
         'labels': ['INBOX', 'UNREAD'], 'messageCount': 2},
        {'id': 't2', 'date': '2026-10-22 11:00', 'from': 'B', 'subject': 'Pago', 'labels': ['INBOX'],
         'messageCount': 1}], 'nextPageToken': 'x'}))
else:
    tid = args[3]
    msgs = {'t1': [{'labelIds': ['INBOX'], 'snippet': 'pregunta', 'payload': {'headers': []}},
                   {'labelIds': ['SENT'], 'snippet': 'respuesta &amp; cierre ' + 'x' * 300,
                    'payload': {'headers': [{'name': 'From', 'value': 'Owner'}]}}],
            't2': [{'labelIds': ['INBOX'], 'snippet': 'factura\\npendiente', 'payload': {'headers': []}}]}[tid]
    print(json.dumps({'thread': {'id': tid, 'messages': msgs}}))
"""


class MailCollectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        bin_dir = root / 'bin'; bin_dir.mkdir()
        for name, body in (('secretary', FAKE_SECRETARY), ('gog', FAKE_GOG)):
            (bin_dir / name).write_text(body); (bin_dir / name).chmod(0o755)
        self.instance = root / 'instance'
        (self.instance / 'extractors/mail').mkdir(parents=True)
        (self.instance / 'extractors/mail/contract.yaml').write_text(
            'freshness:\n  last_success_at: "2026-10-01T18:00:00-05:00"\n')
        self.log = root / 'gog.log'
        self.out = root / 'out.tsv'
        self.env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'GOG_LOG': str(self.log)}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(['python3', str(SCRIPT), '--instance', str(self.instance), *args],
                              env=self.env, capture_output=True, text=True)

    def test_collects_compact_rows_per_account(self) -> None:
        res = self.run_script('--out', str(self.out), '--since', '2026-10-22T00:00:00+00:00',
                              '--min-lookback-hours', '0', '--max-lookback-days', '100000')
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = self.out.read_text().splitlines()
        self.assertIn('# account=personal since=2026-10-22T00:00:00+00:00 status=ok threads=2 truncated=yes', lines)
        rows = [line.split('\t') for line in lines if line.startswith('t')]
        self.assertTrue(all(len(r) == 8 for r in rows))
        t1, t2 = rows
        self.assertEqual(t1[3], 'Hola mundo')
        self.assertEqual(t1[4], 'INBOX')
        self.assertEqual(t1[6], 'last')
        self.assertTrue(t1[7].startswith('respuesta & cierre'))
        self.assertLessEqual(len(t1[7]), 160)
        self.assertEqual((t2[6], t2[7]), ('no', 'factura pendiente'))

    def test_failed_account_is_reported_not_fatal(self) -> None:
        res = self.run_script('--out', str(self.out))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(self.out.read_text(), r'# account=work since=\S+ status=error error=invalid_grant')

    def test_only_read_only_gog_calls(self) -> None:
        self.run_script('--out', str(self.out))
        for call in self.log.read_text().splitlines():
            self.assertIn(call.split()[1], {'search', 'thread'})
            self.assertIn('--readonly', call)
            self.assertIn('--gmail-no-send', call)

    def test_since_comes_from_contract_and_is_bounded(self) -> None:
        res = self.run_script('--dry-run', '--max-lookback-days', '100000')
        self.assertIn('since=2026-10-01T18:00:00-05:00', res.stdout)
        res = self.run_script('--dry-run')  # el contrato es más viejo que 7 días
        self.assertNotIn('since=2026-10-01', res.stdout)

    def test_dry_run_calls_no_gmail(self) -> None:
        res = self.run_script('--dry-run')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.count('[dry-run] account='), 2)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
