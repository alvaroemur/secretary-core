import tempfile
import unittest
from pathlib import Path
from secretary.desk_deploy import deployment


class TidyDeployTests(unittest.TestCase):
    def test_existing_audit_is_preserved_and_reinstall_does_not_duplicate_contract(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scheduled = root/'scheduled'
            target = scheduled/'tidy-up/SKILL.md'
            target.parent.mkdir(parents=True); target.write_text('Existing audit.\n')
            deployment(source, [], root/'runtime', False, scheduled)
            self.assertEqual(target.read_text(), 'Existing audit.\n')
            deployment(source, [], root/'runtime', True, scheduled)
            first = target.read_text()
            self.assertTrue(first.startswith('Existing audit.'))
            self.assertIn('tidy.conditional.enabled', first)
            deployment(source, [], root/'runtime', True, scheduled)
            self.assertEqual(target.read_text(), first)
