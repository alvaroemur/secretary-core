"""Validate close contracts before selecting or replacing installed skills."""
from __future__ import annotations

from pathlib import Path

import yaml

CLOSE_SKILLS = frozenset({'wind-down', 'handover', 'jump', 'desk-project-sync'})
MIN_CLOSE_CONTRACT = 2


def close_contract(path: Path) -> int:
    if not path.is_file():
        return 0
    text = path.read_text()
    if not text.startswith('---\n'):
        return 0
    try:
        header = yaml.safe_load(text.split('---', 2)[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f'Frontmatter inválido: {path}') from exc
    metadata = header.get('metadata') if isinstance(header, dict) else None
    value = (metadata if isinstance(metadata, dict) else {}).get('close-contract', 0)
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f'Contrato de cierre inválido: {path}')
    return int(value)


def skill_source(source: Path, name: str) -> Path:
    """Single versioned source: `skills/<name>` in core, with a minimum close contract."""
    origin = source/'skills'/name
    if name in CLOSE_SKILLS and origin.is_dir():
        if close_contract(origin/'SKILL.md') < MIN_CLOSE_CONTRACT:
            raise ValueError(f'Contrato de cierre obsoleto en {origin}; requiere versión '
                             f'{MIN_CLOSE_CONTRACT} o superior')
    return origin


def skill_origins(source: Path, instance_skills: Path | None = None) -> dict[str, Path]:
    """Every skill to install: core `skills/` plus the instance's own skills.

    A name present in both is an error, not an override: an override would bring
    back two diverging copies of the same skill.
    """
    def scan(root: Path | None) -> dict[str, Path]:
        if root is None or not root.is_dir():
            return {}
        return {p.name: p for p in sorted(root.iterdir()) if (p/'SKILL.md').is_file()}
    core = {name: skill_source(source, name) for name in scan(source/'skills')}
    instance = scan(instance_skills)
    clash = sorted(set(core) & set(instance))
    if clash:
        raise ValueError(f'Skill duplicado entre core e instancia: {", ".join(clash)}')
    return {**core, **instance}


def check_close_destination(src: Path, dst: Path) -> None:
    if src.name == 'SKILL.md' and src.parent.name in CLOSE_SKILLS:
        if close_contract(src) < close_contract(dst):
            raise ValueError(f'No se permite degradar el contrato de cierre: {dst}')
