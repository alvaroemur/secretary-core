import unittest
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner
from secretary.main import app
from secretary.status import post_status


class StatusTests(unittest.TestCase):
    def test_path_is_exact_even_with_spaces_and_narrow_terminal(self):
        path = Path("/vol/" + "long directory/" * 12 + "config.yaml")
        with patch("secretary.main.resolve_path_key", return_value=path):
            result = CliRunner().invoke(app, ["config", "path", "meetings.distribution"], env={"COLUMNS": "20"})
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, str(path) + "\n")

    def test_progress_preserves_details_and_next_decision(self):
        with patch("secretary.status.load_config", return_value={}), patch("secretary.status.publish_event", return_value={"state": "already-published", "issue": 5}) as publish:
            issue, result = post_status("✅", "project", "Report uploaded", state="Slides pending", evidence="PR link", next_step="Review slides")
        text = publish.call_args.args[1]
        for part in ["Report uploaded", "Slides pending", "PR link", "Review slides"]:
            self.assertIn(part, text)
        self.assertEqual(issue, 5)
        self.assertIn("ya registrado", result)

    def test_missing_current_brief_is_explicit_failure(self):
        with patch("secretary.status.load_config", return_value={}), patch("secretary.status.publish_event", return_value={"state": "no-brief-today", "reason": "No current brief"}):
            with self.assertRaisesRegex(RuntimeError, "No current brief"):
                post_status("✅", "project", "done")
