"""Reproducible deployment of portable skills and the mechanical runtime."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SKILLS = ('wind-down', 'sec-project-sync', 'handover', 'jump')


def deployment(source: Path, targets: list[Path], runtime: Path, apply: bool = False,
               pilot_source: Path | None = None, pilot_target: Path | None = None, bin_dir: Path | None = None) -> list[dict]:
    core = source.resolve()
    copies = [(core / 'portable/skills' / skill / 'SKILL.md', target / skill / 'SKILL.md')
              for target in targets for skill in SKILLS]
    copies.append((core / 'secretary/efficiency.py', runtime / 'efficiency.py'))
    copies.append((core / 'portable/check_harnesses.py', runtime / 'check_harnesses.py'))
    if bool(pilot_source) != bool(pilot_target):
        raise ValueError('Indica fuente y destino de los pilotos juntos')
    if pilot_source and pilot_target:
        for routine in ('dispatch-executor', 'wiki-update', 'revision-correo'):
            for name in ('SKILL.md', 'procedure.md'):
                copies.append((pilot_source / routine / name, pilot_target / routine / name))
    for src, _ in copies:
        if not src.is_file(): raise FileNotFoundError(src)
    plan = []
    for src, dst in copies:
        data = src.read_bytes(); digest = hashlib.sha256(data).hexdigest()
        changed = not dst.exists() or dst.read_bytes() != data
        plan.append({'source': str(src), 'destination': str(dst), 'sha256': digest, 'changed': changed})
        if apply and changed:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                old_digest = hashlib.sha256(dst.read_bytes()).hexdigest()
                backup = runtime / 'backups' / (hashlib.sha256(str(dst).encode()).hexdigest() + '-' + old_digest)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup)
            temp = dst.with_name(dst.name + '.portable-tmp'); temp.write_bytes(data); temp.replace(dst)
    if apply:
        runtime.mkdir(parents=True, exist_ok=True)
        if bin_dir:
            bin_dir.mkdir(parents=True, exist_ok=True)
            wrapper = bin_dir / 'secretary-portable'
            content = '#!' + sys.executable + '\nimport runpy\nrunpy.run_path(' + repr(str(runtime / 'efficiency.py')) + ', run_name="__main__")\n'
            wrapper.write_text(content); wrapper.chmod(0o755)
        (runtime / 'deployment.json').write_text(json.dumps(plan, indent=2) + '\n')
    return plan


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--target', type=Path, action='append', required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--pilot-source', type=Path); p.add_argument('--pilot-target', type=Path)
    p.add_argument('--bin-dir', type=Path)
    args = p.parse_args()
    print(json.dumps(deployment(args.source, args.target, args.runtime, args.apply, args.pilot_source, args.pilot_target, args.bin_dir), indent=2))


if __name__ == '__main__': main()
