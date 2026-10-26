import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner
from secretary.main import app
from secretary.signatures import signature


class CloseCliTests(unittest.TestCase):
    def test_help_reaches_argparse_and_lists_real_snapshot_arguments(self):
        runner = CliRunner()
        result = runner.invoke(app, ['efficiency', '--help'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('close-snapshot', result.output)
        result = runner.invoke(app, ['efficiency', 'close-snapshot', '--help'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('--session-id', result.output)
        self.assertIn('--output', result.output)

    def test_snapshot_cli_works_without_instance_or_touched_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = root/'repo'; repo.mkdir()
            subprocess.run(['git', 'init', str(repo)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture',
                            '-c', 'user.email=sender@example.com', 'commit', '--allow-empty',
                            '-m', 'fixture'], check=True, capture_output=True)
            output = root/'snapshot.json'
            result = CliRunner().invoke(app, ['efficiency', 'close-snapshot', '--repo', str(repo),
                                            '--session-id', 'fixture', '--output', str(output)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(output.read_text())['files'], [])

    def test_codex_signature_and_unknown_runtime(self):
        with patch.dict('os.environ', {'CODEX_THREAD_ID': 'fixture'}, clear=True):
            mark, footer = signature(date='2026-10-19')
            self.assertIn('runtime=codex', mark)
            self.assertIn('Codex', footer)
            self.assertNotIn('Claude', footer)
        with patch.dict('os.environ', {}, clear=True):
            self.assertIn('Sesión', signature(date='2026-10-19')[1])
        with self.assertRaises(ValueError):
            signature(runtime='unknown')

    def test_signature_cli_explicit_runtime(self):
        with patch('secretary.config.load_config', return_value={'timezone':'UTC'}):
            result = CliRunner().invoke(app, ['signature', 'wind-down', '--runtime', 'codex'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('runtime=codex', result.output)
        self.assertIn('Generado por Codex', result.output)

    def test_status_default_uses_codex_signature_without_legacy_helper(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from secretary.desk import publish_event
        cfg = {'brief': {'repo': 'owner/notes', 'label': 'brief'}, 'timezone': 'UTC'}
        today = {'number': 1, 'createdAt': datetime.now(timezone.utc).isoformat()}
        with patch.dict('os.environ', {'SECRETARY_RUNTIME': 'codex'}, clear=True), \
             patch('secretary.desk.command', side_effect=[json.dumps([today]), '{"comments":[]}']), \
             patch('secretary.desk.subprocess.run',
                   return_value=SimpleNamespace(returncode=0, stdout='comment-url', stderr='')) as publish:
            self.assertEqual(publish_event(cfg, 'Avance', 'routine')['state'], 'published')
        self.assertIn('runtime=codex', publish.call_args.kwargs['input'])
        self.assertIn('Generado por Codex', publish.call_args.kwargs['input'])


if __name__ == '__main__':
    unittest.main()
