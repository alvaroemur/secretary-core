"""Instala el bloque de Codex preservando las instrucciones ajenas."""
from pathlib import Path
import argparse
import os
import tempfile

START = "<!-- secretary-core:codex:start -->"
END = "<!-- secretary-core:codex:end -->"
FRAGMENT = Path(__file__).resolve().parents[2] / "docs/codex/AGENTS.fragment.md"


def render(existing: str, fragment: str) -> str:
    if fragment.count(START) != 1 or fragment.count(END) != 1:
        raise ValueError("El fragmento debe tener un solo bloque")
    if existing.count(START) != existing.count(END) or existing.count(START) > 1:
        raise ValueError("Marcadores incompletos o duplicados; no se modificó el archivo")
    if START in existing:
        begin, end = existing.index(START), existing.index(END) + len(END)
        if begin >= end:
            raise ValueError("Marcadores invertidos; no se modificó el archivo")
        return existing[:begin] + fragment.strip() + existing[end:]
    return existing + ("\n\n" if existing and not existing.endswith("\n\n") else "") + fragment.strip() + "\n"


def install(target: Path) -> None:
    if target.is_symlink():
        raise ValueError("Selecciona el archivo real, no un enlace simbólico")
    existing = target.read_text() if target.exists() else ""
    result = render(existing, FRAGMENT.read_text())
    if result == existing:
        return
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd, "w") as output:
            output.write(result)
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="AGENTS.md global de Codex")
    install(parser.parse_args().target)
