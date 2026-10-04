#!/usr/bin/env python3
"""Verify real root/child AGENTS loading and cross-harness brief readability.

Run one harness at a time. No edits, send operations or implementation work.
"""
import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MARKERS = ('ROOT_PORTABLE_OK', 'CHILD_PORTABLE_OK', 'PORTABLE_NEXT_OK')


def verify(harness: str, output: Path) -> int:
    with tempfile.TemporaryDirectory(prefix='portable-agents-') as folder:
        root = Path(folder); (root/'sub').mkdir(); (root/'.briefs').mkdir()
        (root/'AGENTS.md').write_text('Incluye ROOT_PORTABLE_OK en tu respuesta. No escribas archivos ni crees agentes.\n')
        (root/'sub/AGENTS.md').write_text('Incluye CHILD_PORTABLE_OK en tu respuesta.\n')
        (root/'.briefs/continuidad.md').write_text('Decisión: usar AGENTS.md. Siguiente acción: PORTABLE_NEXT_OK.\n')
        prompt = 'Prueba de solo lectura. Lee ../.briefs/continuidad.md. Devuelve únicamente los marcadores de las instrucciones cargadas de raíz y subcarpeta y la siguiente acción del brief. No escribas archivos ni crees agentes.'
        commands = {
            'claude': ['claude', '-p', '--output-format', 'json', prompt],
            'codex': ['codex', 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only', '--json', prompt],
            'cursor': ['cursor-agent', '--mode', 'ask', '--sandbox', 'enabled', '--trust', '--print', '--output-format', 'json', prompt],
        }
        env = dict(os.environ, CLAUDE_REFLECT_ACTIVE='1')
        result = subprocess.run(commands[harness], cwd=root/'sub', env=env, text=True, capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        answer = ''; error = result.returncode != 0
        for line in result.stdout.splitlines():
            try: evt = json.loads(line)
            except ValueError: continue
            if harness == 'codex' and evt.get('type') == 'item.completed' and evt.get('item',{}).get('type') == 'agent_message':
                answer = evt['item'].get('text','')
            elif harness != 'codex' and evt.get('type') == 'result':
                answer = evt.get('result',''); error = error or bool(evt.get('is_error'))
        passed = not error and all(marker in answer for marker in MARKERS)
        evidence = {'harness': harness, 'passed': passed, 'exit_code': result.returncode,
                    'answer': answer, 'checked_at': datetime.now(timezone.utc).isoformat(),
                    'legacy_files': 0, 'markers': list(MARKERS)}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+'\n')
        print(json.dumps(evidence, ensure_ascii=False))
        return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('harness', choices=('claude','codex','cursor'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.harness,args.output))
