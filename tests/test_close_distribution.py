import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from secretary.desk_deploy import deployment


def skill(version, body='proposal and close'):
    return f'---\nname: wind-down\nmetadata:\n  close-contract: "{version}"\n---\n{body}\n'


class CloseDistributionTests(unittest.TestCase):
    def fixture(self, root):
        source = root/'source'
        for name, text in [('secretary/data/desk_names.json', '{"skills":{}}'),
                           ('secretary/desk.py', '# fixture'),
                           ('secretary/brief_html.py', '# fixture'),
                           ('secretary/signatures.py', '# fixture'),
                           ('skills.example/wind-down/SKILL.md', skill(2))]:
            path = source/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return source

    def test_private_old_contract_blocks_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            private = source/'skills/wind-down/SKILL.md'
            private.parent.mkdir(parents=True); private.write_text('old portable')
            for apply in [False, True]:
                with self.assertRaisesRegex(ValueError, 'Fuente privada'):
                    deployment(source, [root/'target'], root/'runtime', apply)
                self.assertFalse((root/'target').exists())
                self.assertFalse((root/'runtime').exists())

    def test_newer_last_target_blocks_the_entire_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            newer = root/'last/wind-down/SKILL.md'
            newer.parent.mkdir(parents=True); newer.write_text(skill(3))
            with self.assertRaisesRegex(ValueError, 'degradar'):
                deployment(source, [root/'first', root/'last'], root/'runtime', True)
            self.assertFalse((root/'first').exists())
            self.assertFalse((root/'runtime').exists())
            self.assertEqual(newer.read_text(), skill(3))

    def test_old_export_cannot_erase_the_minimum_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            (source/'skills.example/wind-down/SKILL.md').write_text('obsolete export')
            with self.assertRaisesRegex(ValueError, 'Contrato de cierre obsoleto'):
                deployment(source, [root/'target'], root/'runtime', True)
            self.assertFalse((root/'target').exists())

    def test_private_current_and_public_fallback_install_to_four_targets(self):
        for private in [False, True]:
            with self.subTest(private=private), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); source = self.fixture(root)
                if private:
                    path = source/'skills/wind-down/SKILL.md'
                    path.parent.mkdir(parents=True); path.write_text(skill(2, 'private proposal'))
                # An unrelated private skill must not hide the public close.
                (source/'skills/other').mkdir(parents=True, exist_ok=True)
                legacy = source/'portable/skills/wind-down/SKILL.md'
                legacy.parent.mkdir(parents=True); legacy.write_text('obsolete')
                targets = [root/name for name in ['agents', 'codex', 'claude', 'cursor']]
                runtime = root/'runtime'
                plan = deployment(source, targets, runtime)
                self.assertFalse(any(p.exists() for p in targets))
                close = [p for p in plan if p.get('close_contract')]
                self.assertEqual(len(close), 4)
                self.assertTrue(all(p['close_contract'] == 2 for p in close))
                expected = skill(2, 'private proposal') if private else skill(2)
                deployment(source, targets, runtime, True)
                for target in targets:
                    self.assertEqual((target/'wind-down/SKILL.md').read_text(), expected)
                self.assertTrue(all(not p['changed'] for p in deployment(source, targets, runtime)))
                self.assertIn('source_commit', json.loads((runtime/'deployment.json').read_text())[0])

    def test_upgrade_preserves_installed_content_in_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            old = root/'target/wind-down/SKILL.md'
            old.parent.mkdir(parents=True); old.write_text('old close')
            deployment(source, [root/'target'], root/'runtime', True)
            self.assertTrue(any(p.read_text() == 'old close'
                                for p in (root/'runtime/backups').glob('*/*')))

    def test_setup_checks_sources_before_legacy_copy_phase(self):
        from secretary.routines import setup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            private = source/'skills/wind-down/SKILL.md'
            private.parent.mkdir(parents=True); private.write_text('obsolete')
            home = root/'home'
            with patch.object(setup, '__file__', str(source/'secretary/routines/setup.py')), \
                 patch('pathlib.Path.home', return_value=home), patch('shutil.copytree') as copy:
                with self.assertRaisesRegex(ValueError, 'Fuente privada'):
                    setup._sync_playbooks_and_skills()
                copy.assert_not_called()
                self.assertFalse(home.exists())

    def test_export_refuses_stale_private_close_before_wiping(self):
        from secretary import export_examples
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            private = source/'skills/wind-down/SKILL.md'
            private.parent.mkdir(parents=True); private.write_text('old portable')
            (source/'playbooks').mkdir()
            with patch.object(export_examples, 'core_root', return_value=source), \
                 patch.object(export_examples, 'load_secrets', return_value=[]):
                for check in [True, False]:
                    code, messages = export_examples.export_examples(check=check)
                    self.assertEqual(code, 2)
                    self.assertIn('contrato de cierre 2', messages[0])
            self.assertEqual((source/'skills.example/wind-down/SKILL.md').read_text(), skill(2))

    def test_invalid_close_frontmatter_fails_closed(self):
        from secretary.skill_sources import close_contract
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'SKILL.md'
            path.write_text('---\ndescription: a: b\n---\n')
            with self.assertRaisesRegex(ValueError, 'Frontmatter'):
                close_contract(path)

    def test_catalog_can_discover_codex_without_prioritizing_portable(self):
        from secretary.context import collect_skills
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            installed = root/'.codex/skills/wind-down/SKILL.md'
            installed.parent.mkdir(parents=True); installed.write_text(skill(2))
            legacy = source/'portable/skills/wind-down/SKILL.md'
            legacy.parent.mkdir(parents=True); legacy.write_text('obsolete')
            with patch('secretary.context.Path.home', return_value=root), \
                 patch('secretary.context.core_root', return_value=source):
                result = collect_skills()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].path, str(installed))


if __name__ == '__main__':
    unittest.main()
