import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from secretary.desk_deploy import deployment

REPO = Path(__file__).resolve().parents[1]


def skill(version, body='proposal and close'):
    return f'---\nname: wind-down\nmetadata:\n  close-contract: "{version}"\n---\n{body}\n'


class CloseDistributionTests(unittest.TestCase):
    def fixture(self, root):
        source = root/'source'
        for name, text in [('secretary/data/desk_names.json', '{"skills":{}}'),
                           ('secretary/desk.py', '# fixture'),
                           ('secretary/brief_html.py', '# fixture'),
                           ('secretary/signatures.py', '# fixture'),
                           ('secretary/dream_hook.py', '# fixture'),
                           ('skills/wind-down/SKILL.md', skill(2)),
                           ('skills/notes/SKILL.md', '---\nname: notes\n---\nnotes\n')]:
            path = source/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return source

    def test_newer_installation_blocks_the_entire_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            newer = root/'claude/wind-down/SKILL.md'
            newer.parent.mkdir(parents=True); newer.write_text(skill(3))
            with self.assertRaisesRegex(ValueError, 'degradar'):
                deployment(source, [root/'agents'], root/'runtime', True, links=[root/'claude'])
            self.assertFalse((root/'agents').exists())
            self.assertFalse((root/'runtime').exists())
            self.assertEqual(newer.read_text(), skill(3))

    def test_stale_source_cannot_erase_the_minimum_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            (source/'skills/wind-down/SKILL.md').write_text('obsolete close')
            with self.assertRaisesRegex(ValueError, 'Contrato de cierre obsoleto'):
                deployment(source, [root/'agents'], root/'runtime', True)
            self.assertFalse((root/'agents').exists())

    def test_one_copy_links_and_prunes(self):
        """#73: each harness sees one copy, and every copy is the versioned source."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            agents, claude, codex, cursor = (root/n for n in ['agents', 'claude', 'codex', 'cursor'])
            for folder, text in [(claude, 'old claude copy'), (codex, 'old codex copy')]:
                (folder/'wind-down').mkdir(parents=True); (folder/'wind-down/SKILL.md').write_text(text)
            (codex/'foreign').mkdir(); (codex/'foreign/SKILL.md').write_text('not ours')
            runtime = root/'runtime'
            kwargs = dict(links=[claude], prunes=[codex, cursor])
            plan = deployment(source, [agents], runtime, **kwargs)
            self.assertFalse(agents.exists())
            self.assertTrue(any(p.get('link') == str(claude/'wind-down') and p['changed'] for p in plan))
            deployment(source, [agents], runtime, True, **kwargs)
            self.assertEqual((agents/'wind-down/SKILL.md').read_text(), skill(2))
            for name in ['wind-down', 'notes']:
                self.assertTrue((claude/name).is_symlink())
                self.assertEqual((claude/name).resolve(), (agents/name).resolve())
                self.assertFalse((codex/name).exists())
                self.assertFalse((cursor/name).exists())
            self.assertEqual((codex/'foreign/SKILL.md').read_text(), 'not ours')
            self.assertTrue(any((p/'SKILL.md').is_file() and (p/'SKILL.md').read_text() == 'old codex copy'
                                for p in (runtime/'backups').glob('*/tree')))
            self.assertTrue(all(not p['changed'] for p in deployment(source, [agents], runtime, **kwargs)))
            self.assertIn('source_commit', json.loads((runtime/'deployment.json').read_text())[0])

    def test_instance_skill_with_core_name_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            instance = root/'instance/canon/skills'
            (instance/'notes').mkdir(parents=True); (instance/'notes/SKILL.md').write_text('fork')
            (instance/'own').mkdir(); (instance/'own/SKILL.md').write_text('---\nname: own\n---\n')
            with self.assertRaisesRegex(ValueError, 'duplicado.*notes'):
                deployment(source, [root/'agents'], root/'runtime', instance_skills=instance)
            (instance/'notes/SKILL.md').unlink(); (instance/'notes').rmdir()
            deployment(source, [root/'agents'], root/'runtime', True, instance_skills=instance)
            self.assertTrue((root/'agents/own/SKILL.md').is_file())

    def test_upgrade_preserves_installed_content_in_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            old = root/'agents/wind-down/SKILL.md'
            old.parent.mkdir(parents=True); old.write_text('old close')
            deployment(source, [root/'agents'], root/'runtime', True)
            self.assertTrue(any(p.read_text() == 'old close'
                                for p in (root/'runtime/backups').glob('*/*') if p.is_file()))

    def test_setup_checks_sources_before_copy_phase(self):
        from secretary.routines import setup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            (source/'skills/wind-down/SKILL.md').write_text('obsolete')
            home = root/'home'
            with patch.object(setup, '__file__', str(source/'secretary/routines/setup.py')), \
                 patch.object(setup, '_instance_dir', return_value=None), \
                 patch('pathlib.Path.home', return_value=home), patch('shutil.copytree') as copy:
                with self.assertRaisesRegex(ValueError, 'Contrato de cierre obsoleto'):
                    setup._sync_playbooks_and_skills()
                copy.assert_not_called()
                self.assertFalse(home.exists())

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
                result = [s for s in collect_skills() if s.name == 'wind-down']
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].path, str(installed))

    def test_repository_skills_carry_the_close_contract(self):
        """The versioned tree itself must be deployable (no private copy needed)."""
        from secretary.skill_sources import skill_origins
        origins = skill_origins(REPO)
        self.assertIn('wind-down', origins)
        self.assertFalse((REPO/'skills.example').exists())
        self.assertFalse((REPO/'playbooks.example').exists())

    def test_versioned_procedures_never_squash(self):
        """Policy: merge commit only; squash hides integration from git."""
        from secretary.skill_sources import close_contract
        offenders = [str(p.relative_to(REPO)) for root in ('skills', 'playbooks')
                     for p in (REPO/root).rglob('*.md') if '--squash' in p.read_text(encoding='utf-8')]
        self.assertEqual(offenders, [])
        self.assertGreaterEqual(close_contract(REPO/'skills/wind-down/SKILL.md'), 4)

    def test_close_skills_carry_lifecycle_and_continuity_rules(self):
        """dream-utilidad F3: cleanup, brief lifecycle, paste block and archive answer."""
        from secretary.skill_sources import close_contract
        read = lambda name: (REPO/'skills'/name/'SKILL.md').read_text(encoding='utf-8')
        self.assertGreaterEqual(close_contract(REPO/'skills/jump/SKILL.md'), 3)
        self.assertGreaterEqual(close_contract(REPO/'skills/handover/SKILL.md'), 3)
        wind_down, jump, handover, merge = map(read, ['wind-down', 'jump', 'handover', 'desk-merge'])
        for text in (wind_down, merge):
            self.assertIn('merge-base --is-ancestor', text)
            self.assertIn('push origin --delete', text)
            self.assertIn('lsof -a -d cwd', text)
        for text in (wind_down, handover):
            self.assertIn('_archivo/', text)
            self.assertIn('superseded', text)
        self.assertIn('Can you archive this session?', wind_down)
        self.assertIn('already done', jump)
        self.assertIn('fenced `text` block', jump)
        self.assertNotIn('tier per row', jump)
        for name, text in [('wind-down', wind_down), ('jump', jump),
                           ('handover', handover), ('desk-merge', merge)]:
            self.assertNotIn('skills/desk-dream', text, name)
            self.assertNotIn('invoke `desk-heartbeat`', text, name)


if __name__ == '__main__':
    unittest.main()
