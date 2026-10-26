"""Generate agent signatures without depending on a harness installation."""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

LABELS = {'codex': 'Codex', 'cursor': 'Cursor', 'claude-code': 'Claude Code',
          'api': 'API cron', 'antigravity': 'Antigravity', 'sesion': 'Sesión'}


def signature(context: str = 'sesion', *, runtime: str | None = None,
              date: str | None = None, timezone: str = 'UTC') -> tuple[str, str]:
    runtime = runtime or os.environ.get('SECRETARY_RUNTIME')
    if not runtime:
        runtime = 'codex' if os.environ.get('CODEX_THREAD_ID') else 'sesion'
    if runtime == 'claude':
        runtime = 'claude-code'
    if runtime not in LABELS:
        raise ValueError(f'Runtime de firma desconocido: {runtime}')
    # Context is embedded in both an HTML comment and Markdown.
    if not context or any(not (c.isalnum() or c in '-_') for c in context):
        raise ValueError('Contexto de firma inválido')
    day = date or os.environ.get('SECRETARY_SIGNATURE_DATE') or datetime.now(ZoneInfo(timezone)).date().isoformat()
    datetime.strptime(day, '%Y-%m-%d')
    return (f'<!-- agent-generated:{context} runtime={runtime} -->',
            f'🤖 _Generado por {LABELS[runtime]} — {context} · {day}_')
