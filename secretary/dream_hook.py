"""PreToolUse hook: avisa cuando una sesión edita archivos de un PR abierto de dream (U9).

La rutina sec-dream refresca la lista con `secretary dream open-prs --write`. Este
archivo se instala junto al runtime de Desk y corre en cada Edit/Write de Claude
Code: solo biblioteca estándar, sin red, nunca bloquea. Un aviso por PR y sesión.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

STALE_HOURS = 36
SKIP_PREFIXES = (('.wt',), ('.claude', 'worktrees'))


def state_dir() -> Path:
    base = os.environ.get('SECRETARY_STATE_DIR') or str(Path.home()/'.local/share/secretary')
    return Path(base).expanduser()/'dream'


def cache_path() -> Path:
    return state_dir()/'open-prs.json'


def _relative(file_path: Path, repo_path: Path) -> tuple[str, str] | None:
    """Ruta relativa al repo y slug del worktree (`''` si es el checkout principal)."""
    try:
        parts = file_path.relative_to(repo_path).parts
    except ValueError:
        return None
    for prefix in SKIP_PREFIXES:
        n = len(prefix)
        if parts[:n] == prefix and len(parts) > n + 1:
            return '/'.join(parts[n+1:]), parts[n]
    return '/'.join(parts), ''


def overlaps(cache: dict, file_path: str) -> list[dict]:
    target = Path(os.path.realpath(os.path.expanduser(file_path)))
    hits = []
    for pr in cache.get('prs', []):
        if not pr.get('path'):
            continue
        rel = _relative(target, Path(os.path.realpath(os.path.expanduser(pr['path']))))
        if rel is None:
            continue
        rel_path, slug = rel
        if slug and slug == pr.get('branch', '').replace('/', '-'):
            continue  # La sesión trabaja en el worktree del propio PR de dream.
        if rel_path in pr.get('files', []):
            hits.append(pr)
    return hits


def fresh(cache: dict, now: datetime | None = None) -> bool:
    try:
        generated = datetime.fromisoformat(cache['generated_at'])
    except (KeyError, ValueError):
        return False
    now = now or datetime.now(timezone.utc)
    return (now - generated).total_seconds() < STALE_HOURS*3600


def _first_warning(session: str, keys: list[str]) -> list[str]:
    seen_file = state_dir()/'hook-seen'/f'{session or "sin-sesion"}.json'
    try:
        seen = set(json.loads(seen_file.read_text()))
    except (OSError, ValueError):
        seen = set()
    new = [k for k in keys if k not in seen]
    if new:
        try:
            seen_file.parent.mkdir(parents=True, exist_ok=True)
            seen_file.write_text(json.dumps(sorted(seen | set(new))))
        except OSError:
            pass
    return new


def message(hits: list[dict]) -> str:
    lines = ['Este archivo también lo cambia un PR abierto de dream:']
    for pr in hits:
        lines.append(f"- {pr['repo']}#{pr['number']} «{pr.get('title', '')}» ({pr.get('url', '')})")
    lines.append('Revisa ese PR antes de seguir: intégralo, ciérralo o coordina los cambios.')
    return '\n'.join(lines)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool_input = event.get('tool_input') or {}
        file_path = tool_input.get('file_path') or tool_input.get('notebook_path')
        if not file_path:
            return 0
        cache = json.loads(cache_path().read_text())
    except (OSError, ValueError, AttributeError):
        return 0
    if not fresh(cache):
        return 0
    hits = overlaps(cache, file_path)
    new = set(_first_warning(event.get('session_id', ''), [f"{h['repo']}#{h['number']}" for h in hits]))
    hits = [h for h in hits if f"{h['repo']}#{h['number']}" in new]
    if not hits:
        return 0
    text = message(hits)
    print(json.dumps({'systemMessage': '🤖 ' + text,
                      'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': text}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
