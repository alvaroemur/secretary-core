from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "skills/handover/scripts/check_handoff.py"


class HandoffSkillTests(unittest.TestCase):
    def test_compact_handoff_contract_is_shared(self):
        handover = (REPO / "skills/handover/SKILL.md").read_text(encoding="utf-8")
        jump = (REPO / "skills/jump/SKILL.md").read_text(encoding="utf-8")
        conductor = (REPO / "skills/conductor/references/relevo.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("4096 bytes", handover)
        self.assertIn(".briefs/", handover)
        for harness in ("Claude Code", "Codex", "Cursor"):
            self.assertIn(harness, jump)
        self.assertIn("single source of truth", conductor)
        self.assertIn("references the brief instead of duplicating", conductor)

    def test_checker_accepts_complete_brief(self):
        validate = runpy.run_path(str(CHECKER))["validate"]
        content = """---
status: pending
---
# Handoff
plan: p1 | node: n4
branch: skills/handoff | worktree: /repo/.wt/skills-handoff | PR: none
## Done
- Contract drafted.
## Decisions
- Keep one payload.
## Pending
- Open the PR.
## Blockers
None.
## Verify first
`git status --short`
"""
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.md"
            brief.write_text(content, encoding="utf-8")
            self.assertEqual(validate(brief), [])

    def test_checker_rejects_oversized_or_incomplete_brief(self):
        validate = runpy.run_path(str(CHECKER))["validate"]
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.md"
            brief.write_text("x" * 4097, encoding="utf-8")
            errors = validate(brief)
        self.assertTrue(any("exceeds" in error for error in errors))
        self.assertTrue(any("missing required markers" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
