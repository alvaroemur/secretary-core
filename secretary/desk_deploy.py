"""Deploy desk skills, aliases and runtime without changing scheduler registrations."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def deployment(source: Path, targets: list[Path], runtime: Path, apply: bool = False,
               scheduled: Path | None = None, bin_dir: Path | None = None) -> list[dict]:
    names = json.loads((source/'secretary/data/desk_names.json').read_text())
    skills = source/'skills'
    if not skills.is_dir():skills = source/'skills.example'
    playbooks = source/'playbooks'
    if not playbooks.is_dir():playbooks = source/'playbooks.example'
    copies = []
    overrides = {}
    for target in targets:
        for name in set(names['skills']) | set(names['skills'].values()) | {'wind-down', 'handover', 'jump'}:
            origin = source/'portable/skills'/name
            if not origin.is_dir():origin = skills/name
            if origin.is_dir():
                copies.extend((p, target/name/p.relative_to(origin)) for p in origin.rglob('*') if p.is_file())
    copies.append((source/'secretary/desk.py', runtime/'desk.py'))
    copies.append((source/'secretary/brief_html.py', runtime/'brief_html.py'))
    if scheduled:
        # Existing IDs and paths remain stable; no extra schedule is registered.
        for name in ['dispatch-executor','pulse-headless','secretary-briefing','sec-dream',
                     'sec-heartbeat','job-search-crawler']:
            origin = playbooks/name
            if origin.is_dir():copies.extend((p, scheduled/name/p.relative_to(origin)) for p in origin.rglob('*') if p.is_file())
        # Sales owns its private business procedure and supporting scripts.
        # Append only the shared reporting contract; never export or replace it.
        for name in ['sales-crawler', 'sales-inbox']:
            origin = source/'routine-overlays'/name/'reporting.md'
            dst = scheduled/name/'SKILL.md'
            if origin.is_file() and dst.is_file():
                marker = '\n\n## Visibilidad de decisiones pendientes · Desk'
                existing = dst.read_text().split(marker)[0]
                overrides[str(dst)] = (existing + origin.read_text()).encode()
                copies.append((origin, dst))
    plan = []
    for src, dst in copies:
        data = overrides.get(str(dst), src.read_bytes());changed = not dst.exists() or dst.read_bytes() != data
        plan.append({'source': str(src), 'destination': str(dst), 'changed': changed,
                     'sha256': hashlib.sha256(data).hexdigest()})
        if apply and changed:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                backup = runtime/'backups'/hashlib.sha256(str(dst).encode()).hexdigest()/hashlib.sha256(dst.read_bytes()).hexdigest()
                backup.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(dst, backup)
            tmp = dst.with_name(dst.name+'.desk-tmp');tmp.write_bytes(data);tmp.replace(dst)
    if apply:
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime/'deployment.json').write_text(json.dumps(plan, indent=2)+'\n')
        if bin_dir:
            bin_dir.mkdir(parents=True, exist_ok=True);wrapper = bin_dir/'secretary-desk'
            wrapper.write_text('#!'+sys.executable+'\nimport runpy\nrunpy.run_path('+repr(str(runtime/'desk.py'))+', run_name="__main__")\n');wrapper.chmod(0o755)
    return plan


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--target',type=Path,action='append',required=True);p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--scheduled',type=Path);p.add_argument('--bin-dir',type=Path);p.add_argument('--apply',action='store_true')
    a=p.parse_args();print(json.dumps(deployment(a.source,a.target,a.runtime,a.apply,a.scheduled,a.bin_dir),indent=2))


if __name__=='__main__':main()
