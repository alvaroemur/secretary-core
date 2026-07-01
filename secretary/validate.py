"""Run instance CI validators."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from secretary.config import instance_root

VALIDATORS = {
    "wikilinks": "validate_wikilinks.py",
    "paths": "validate_paths.py",
    "ordenamiento": "validate_ordenamiento.py",
}


def validators_dir() -> Path:
    return instance_root() / "scripts" / "ci"


def run_validator(name: str) -> int:
    script = validators_dir() / VALIDATORS[name]
    if not script.is_file():
        raise FileNotFoundError(f"No existe {script}")
    return subprocess.run([sys.executable, str(script)], cwd=str(instance_root())).returncode


def run_all() -> int:
    rc = 0
    for name in VALIDATORS:
        code = run_validator(name)
        if code != 0:
            rc = code
    return rc
