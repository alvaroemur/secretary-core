"""Añade contratos de conversaciones conservando procedimientos y scheduler existentes."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import json

MARKER = '\n\n## Conversaciones del propietario · Desk'


def deploy(source: Path, scheduled: Path, skills: list[Path], runtime: Path, apply=False) -> list[dict]:
    destinations = []
    for name in ['sec-dream','revision-correo','pulse-headless','secretary-briefing']:
        destinations.append((source/'routine-overlays/conversations'/f'{name}.md',scheduled/name/'SKILL.md'))
    for target in skills:
        destinations.append((source/'routine-overlays/conversations/desk-overview.md',target/'desk-overview/SKILL.md'))
    plan = []
    for contract,target in destinations:
        if not contract.is_file() or not target.is_file():
            plan.append({'destination':str(target),'state':'missing-target-or-contract','changed':False})
            continue
        original = target.read_bytes()
        content = (original.decode().split(MARKER)[0] + contract.read_text()).encode()
        changed = content != original
        plan.append({'destination':str(target),'state':'ready','changed':changed,'sha256':hashlib.sha256(content).hexdigest()})
        if changed and apply:
            backup = runtime/'conversation-backups'/hashlib.sha256(str(target).encode()).hexdigest()/hashlib.sha256(original).hexdigest()
            backup.parent.mkdir(parents=True,exist_ok=True); backup.write_bytes(original)
            temporary = target.with_name(target.name+'.conversations-tmp')
            temporary.write_bytes(content); temporary.replace(target)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--scheduled',type=Path,required=True)
    parser.add_argument('--target',type=Path,action='append',default=[]);parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    print(json.dumps(deploy(args.source,args.scheduled,args.target,args.runtime,args.apply),indent=2))


if __name__ == '__main__': main()
