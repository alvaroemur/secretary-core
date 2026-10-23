import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "secretary" / "routines" / "routines-log-dir.sh"


def _run(inst: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "SECRETARY_INSTANCE": str(inst), "SECRETARY_CORE": str(REPO)}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


class RoutinesLogDirTests(unittest.TestCase):
    def test_falls_back_when_config_has_no_routines_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp).resolve()
            (inst / ".secretary.yml").write_text("timezone: America/Lima\n", encoding="utf-8")
            result = _run(inst)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(inst / "subsystem" / "routines"))
            self.assertTrue((inst / "subsystem" / "routines").is_dir())

    def test_uses_configured_routines_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp).resolve()
            (inst / ".secretary.yml").write_text(
                "paths:\n  subsystem:\n    routines: logs/rutinas\n", encoding="utf-8"
            )
            result = _run(inst)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(inst / "logs" / "rutinas"))


if __name__ == "__main__":
    unittest.main()
