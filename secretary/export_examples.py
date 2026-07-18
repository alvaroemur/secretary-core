"""Generate the public `*.example` dirs from the private playbooks/skills.

The engine keeps a public/private split:

- ``playbooks/`` and ``skills/`` are gitignored — the REAL, private sources.
- ``playbooks.example/`` and ``skills.example/`` are committed, sanitized copies.

This module deterministically regenerates the ``*.example`` dirs by copying every
file from the real dir and applying the redaction rules to text files. Because it
wipes and rebuilds the target dirs, drift between the real sources and the examples
is impossible: the examples are always a pure function of (sources + rules).

Redaction rules come from TWO files, merged:

- ``secretary/data/export_examples_map.yml`` — committed, PUBLIC. Only non-sensitive
  rules (e.g. a generic phone regex) plus the `preserve` allowlist and `detect`
  patterns for the leak-guard.
- ``export_examples_secrets.yml`` — gitignored, PRIVATE. The real sensitive literals
  (owner emails, private repo slugs, Drive folder ids). Absent on fresh clones / CI,
  in which case the exporter warns and applies only the public rules.

It NEVER touches ``docs/``, ``README.md``, or any other root doc — those are
hand-authored prose.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from secretary.config import core_root

# (real source dir, committed example dir) — the only dirs this tool manages.
EXPORT_PAIRS: tuple[tuple[str, str], ...] = (
    ("playbooks", "playbooks.example"),
    ("skills", "skills.example"),
)

MAP_PATH = Path(__file__).resolve().parent / "data" / "export_examples_map.yml"
SECRETS_FILENAME = "export_examples_secrets.yml"


def secrets_path() -> Path:
    """Private secrets file: `SECRETARY_EXPORT_SECRETS` env, else repo root."""
    env = os.environ.get("SECRETARY_EXPORT_SECRETS")
    if env:
        return Path(env).expanduser()
    return core_root() / SECRETS_FILENAME


@dataclass(frozen=True)
class RedactRule:
    replacement: str
    note: str = ""
    pattern: str | None = None  # literal substring
    regex: str | None = None  # compiled below if present

    def apply(self, text: str) -> str:
        if self.regex is not None:
            return re.sub(self.regex, self.replacement, text)
        assert self.pattern is not None
        return text.replace(self.pattern, self.replacement)


@dataclass
class RedactionMap:
    redact: list[RedactRule] = field(default_factory=list)
    preserve: list[str] = field(default_factory=list)

    def apply(self, text: str) -> str:
        for rule in self.redact:
            text = rule.apply(text)
        return text


def _parse_rules(entries: Any) -> list[RedactRule]:
    rules: list[RedactRule] = []
    for entry in entries or []:
        if "replacement" not in entry:
            raise ValueError(f"Regla sin `replacement`: {entry!r}")
        if not (entry.get("pattern") or entry.get("regex")):
            raise ValueError(f"Regla sin `pattern` ni `regex`: {entry!r}")
        rules.append(
            RedactRule(
                replacement=entry["replacement"],
                note=entry.get("note", ""),
                pattern=entry.get("pattern"),
                regex=entry.get("regex"),
            )
        )
    return rules


def load_map(path: Path | None = None) -> RedactionMap:
    """Parse the PUBLIC map (non-sensitive redact rules + preserve allowlist)."""
    src = path or MAP_PATH
    if not src.is_file():
        raise FileNotFoundError(f"No existe el mapa público: {src}")
    data: dict[str, Any] = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    return RedactionMap(
        redact=_parse_rules(data.get("redact")),
        preserve=[str(x) for x in (data.get("preserve") or [])],
    )


def load_secrets(path: Path | None = None) -> list[RedactRule]:
    """Parse the PRIVATE secrets file's redact rules. Empty if absent."""
    src = path or secrets_path()
    if not src.is_file():
        return []
    data: dict[str, Any] = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    return _parse_rules(data.get("redact"))


def build_redaction() -> tuple[RedactionMap, bool]:
    """Merge private (first) + public redact rules. Returns (map, secrets_present)."""
    public = load_map()
    private = load_secrets()
    merged = RedactionMap(
        redact=private + public.redact,  # private literals win; public phone regex last
        preserve=public.preserve,
    )
    return merged, bool(private)


def _is_binary(path: Path) -> bool:
    try:
        path.read_text(encoding="utf-8")
        return False
    except (UnicodeDecodeError, ValueError):
        return True


def _generate(src_dir: Path, dst_dir: Path, redaction: RedactionMap) -> None:
    """Copy `src_dir` → `dst_dir`, redacting text files. Assumes dst is fresh."""
    for item in sorted(src_dir.rglob("*")):
        rel = item.relative_to(src_dir)
        target = dst_dir / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if _is_binary(item):
            shutil.copy2(item, target)
        else:
            text = item.read_text(encoding="utf-8")
            target.write_text(redaction.apply(text), encoding="utf-8")
            shutil.copymode(item, target)  # keep +x on scripts like run.sh


def _iter_files(root: Path) -> dict[str, Path]:
    """Map of relative-posix-path → absolute path for every file under `root`."""
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file()
    }


def _diff_trees(expected: Path, committed: Path) -> list[str]:
    """Return human-readable differences between freshly generated and committed."""
    diffs: list[str] = []
    exp = _iter_files(expected)
    com = _iter_files(committed)
    for rel in sorted(set(exp) | set(com)):
        if rel not in com:
            diffs.append(f"  + faltante en commit: {rel}")
        elif rel not in exp:
            diffs.append(f"  - sobra en commit:   {rel}")
        elif exp[rel].read_bytes() != com[rel].read_bytes():
            diffs.append(f"  ~ difiere:           {rel}")
    return diffs


def export_examples(*, check: bool = False) -> tuple[int, list[str]]:
    """Regenerate (or, with `check`, verify) the `*.example` dirs.

    Returns (exit_code, messages). Exit code is non-zero on missing sources or,
    in check mode, on any drift.
    """
    root = core_root()
    redaction, secrets_present = build_redaction()
    messages: list[str] = []

    if not secrets_present:
        messages.append(
            f"⚠️  ADVERTENCIA: no se encontró {secrets_path()} — "
            "se aplican SOLO las reglas públicas (regex genéricas). "
            "Las redacciones de literales sensibles (emails, ids de Drive, repos "
            "privados) NO se aplicarán. Copiá export_examples_secrets.example.yml "
            "a export_examples_secrets.yml con tus valores reales."
        )

    missing = [src for src, _ in EXPORT_PAIRS if not (root / src).is_dir()]
    if missing:
        joined = ", ".join(missing)
        return 2, [
            f"Fuente(s) real(es) ausente(s): {joined}.",
            "Los `*.example` se generan desde los dirs privados (gitignored).",
            "Sin la fuente no se puede regenerar — abortando para no crear basura.",
        ]

    if check:
        drift = False
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for src, dst in EXPORT_PAIRS:
                staged = tmp_root / dst
                _generate(root / src, staged, redaction)
                committed = root / dst
                if not committed.is_dir():
                    drift = True
                    messages.append(f"{dst}: no existe en el árbol commiteado.")
                    continue
                d = _diff_trees(staged, committed)
                if d:
                    drift = True
                    messages.append(f"{dst}: difiere de la fuente regenerada:")
                    messages.extend(d)
                else:
                    messages.append(f"{dst}: ✓ al día.")
        return (1 if drift else 0), messages

    for src, dst in EXPORT_PAIRS:
        target = root / dst
        if target.exists():
            shutil.rmtree(target)
        _generate(root / src, target, redaction)
        n = sum(1 for _ in (target).rglob("*") if _.is_file())
        messages.append(f"{dst}: regenerado desde {src}/ ({n} archivos).")
    return 0, messages
