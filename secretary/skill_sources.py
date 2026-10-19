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
    public = source/'skills.example'/name
    private = source/'skills'/name
    origin = private if private.is_dir() else public
    if name in CLOSE_SKILLS and private.is_dir():
        if close_contract(private/'SKILL.md') < close_contract(public/'SKILL.md'):
            raise ValueError(f'Fuente privada de {name} obsoleta; reconcilia skills/ con '
                             'skills.example/ revisado antes de desplegar')
    if name in CLOSE_SKILLS and origin.is_dir():
        if close_contract(origin/'SKILL.md') < MIN_CLOSE_CONTRACT:
            raise ValueError(f'Contrato de cierre obsoleto en {origin}; requiere versión '
                             f'{MIN_CLOSE_CONTRACT} o superior')
    return origin


def check_close_destination(src: Path, dst: Path) -> None:
    if src.name == 'SKILL.md' and src.parent.name in CLOSE_SKILLS:
        if close_contract(src) < close_contract(dst):
            raise ValueError(f'No se permite degradar el contrato de cierre: {dst}')


def check_export_sources(private: Path, public: Path) -> None:
    """Refuse an export that would erase or lower a reviewed close contract."""
    for name in sorted(CLOSE_SKILLS):
        source = private/name/'SKILL.md'
        if not source.is_file():
            continue
        required = max(MIN_CLOSE_CONTRACT, close_contract(public/name/'SKILL.md'))
        if close_contract(source) < required:
            raise ValueError(f'Fuente privada de {name} obsoleta; el export perdería el '
                             f'contrato de cierre {required}')
