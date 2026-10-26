"""Regresión del instalador: aislamiento, preservación y rechazo seguro."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codex_rules", ROOT / "scripts/codex/install_rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class CodexRulesTest(unittest.TestCase):
    def test_preserves_existing_rules_and_is_idempotent(self):
        original = "# Reglas del propietario\nNo ejecutar sin aprobación.\n"
        fragment = rules.FRAGMENT.read_text()
        once = rules.render(original, fragment)
        self.assertTrue(once.startswith(original))
        self.assertEqual(rules.render(once, fragment), once)

    def test_replaces_only_managed_block(self):
        original = "ANTES\n" + rules.START + "\nVersión anterior\n" + rules.END + "\nDESPUÉS\n"
        result = rules.render(original, rules.FRAGMENT.read_text())
        self.assertTrue(result.startswith("ANTES\n"))
        self.assertTrue(result.endswith("\nDESPUÉS\n"))
        self.assertNotIn("Versión anterior", result)

    def test_invalid_markers_do_not_write(self):
        for original in (rules.START, rules.END, rules.END + rules.START,
                         rules.START + rules.END + rules.START + rules.END):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "AGENTS.md"
                target.write_text(original)
                with self.assertRaises(ValueError):
                    rules.install(target)
                self.assertEqual(target.read_text(), original)

    def test_install_preserves_mode_and_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "AGENTS.md"
            target.write_text("Reglas originales\n")
            target.chmod(0o640)
            sibling = Path(directory) / "CLAUDE.md"
            sibling.write_text("Otro harness\n")
            rules.install(target)
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            self.assertEqual(sibling.read_text(), "Otro harness\n")
            once = target.read_bytes()
            rules.install(target)
            self.assertEqual(target.read_bytes(), once)

    def test_failed_replace_preserves_target_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "AGENTS.md"
            target.write_text("Original\n")
            with patch.object(rules.os, "replace", side_effect=OSError("Fallo simulado")):
                with self.assertRaises(OSError):
                    rules.install(target)
            self.assertEqual(target.read_text(), "Original\n")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_symlink_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real.md"
            real.write_text("Original\n")
            target = Path(directory) / "AGENTS.md"
            target.symlink_to(real)
            with self.assertRaises(ValueError):
                rules.install(target)
            self.assertEqual(real.read_text(), "Original\n")


if __name__ == "__main__":
    unittest.main()
