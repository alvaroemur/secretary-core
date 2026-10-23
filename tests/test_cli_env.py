"""`secretary env` exporta las rutas que usan los playbooks de rutinas."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from secretary.main import app


class EnvCommandTest(unittest.TestCase):
    def test_exports_instance_and_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); instance = root / 'instance'; core = root / 'core'
            instance.mkdir(); core.mkdir()
            env = {'SECRETARY_INSTANCE': str(instance), 'SECRETARY_CORE': str(core)}
            with patch.dict(os.environ, env):
                out = CliRunner().invoke(app, ['env']).output
        self.assertIn(f'export SECRETARY_INSTANCE="{instance}"', out)
        self.assertIn(f'export SECRETARY_CORE="{core}"', out)

    def test_core_falls_back_to_instance_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); instance = root / 'instance'; core = root / 'core'
            instance.mkdir(); core.mkdir()
            (instance / '.secretary.yml').write_text(f'core_path: {core}\n')
            clean = {k: v for k, v in os.environ.items() if k != 'SECRETARY_CORE'}
            clean['SECRETARY_INSTANCE'] = str(instance)
            with patch.dict(os.environ, clean, clear=True):
                out = CliRunner().invoke(app, ['env']).output
        self.assertIn(f'export SECRETARY_CORE="{core}"', out)


if __name__ == '__main__':
    unittest.main()
