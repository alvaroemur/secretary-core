"""Contract tests for the conductor skill's status source."""

import unittest
from pathlib import Path

import yaml


SKILL = Path(__file__).resolve().parents[1] / "skills" / "conductor" / "SKILL.md"


class ConductorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = SKILL.read_text(encoding="utf-8")
        _, frontmatter, cls.body = text.split("---", 2)
        cls.meta = yaml.safe_load(frontmatter)

    def test_frontmatter_preserves_invocation_contract(self):
        self.assertEqual(self.meta["name"], "conductor")
        self.assertTrue(self.meta["user-invocable"])

    def test_estado_is_the_primary_reconciled_source(self):
        self.assertIn("secretary estado --json", self.body)
        self.assertIn("--with-prs", self.body)
        self.assertNotIn("secretary-desk overview", self.body)
        self.assertNotIn("gh pr list", self.body)
        self.assertNotIn("git worktree list", self.body)


if __name__ == "__main__":
    unittest.main()
