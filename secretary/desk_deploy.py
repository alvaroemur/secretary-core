"""Deploy desk skills, aliases and runtime without changing scheduler registrations."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
import subprocess
from pathlib import Path

from secretary.skill_sources import CLOSE_SKILLS, check_close_destination, close_contract, skill_origins


def deployment(source: Path, targets: list[Path], runtime: Path, apply: bool = False,
               scheduled: Path | None = None, bin_dir: Path | None = None,
               instance_skills: Path | None = None, links: list[Path] = (),
               prunes: list[Path] = ()) -> list[dict]:
    """Install one physical copy per skill in `targets`.

    `links` are harness skill dirs that cannot read `targets` (they get one symlink
    per skill into the first target). `prunes` are harness dirs that already read
    `targets`; their copies of these skills are removed so each skill appears once.
    Skills listed in `retired_skills` of `desk_names.json` are removed from every dir.
    """
    playbooks = source/'playbooks'
    origins = skill_origins(source, instance_skills)
    copies = []
    overrides = {}
    for target in targets:
        for name, origin in origins.items():
            copies.extend((p, target/name/p.relative_to(origin)) for p in origin.rglob('*') if p.is_file())
    copies.append((source/'secretary/desk.py', runtime/'desk.py'))
    copies.append((source/'secretary/brief_html.py', runtime/'brief_html.py'))
    copies.append((source/'secretary/signatures.py', runtime/'signatures.py'))
    copies.append((source/'secretary/dream_hook.py', runtime/'dream_hook.py'))
    if scheduled:
        # Preserve the existing audit; append the gated conditional-reorganization contract.
        tidy_contract = source/'routine-overlays/tidy-up/conditional.md'
        tidy_target = scheduled/'tidy-up/SKILL.md'
        if tidy_contract.is_file() and tidy_target.is_file():
            marker = '\n\n## Tareas condicionales · tidy-up'
            existing = tidy_target.read_text().split(marker)[0]
            overrides[str(tidy_target)] = (existing + tidy_contract.read_text()).encode()
            copies.append((tidy_contract, tidy_target))
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
    if scheduled:
        # Add a reporting-only contract to existing routines, preserving their procedure.
        common = source/'routine-overlays/reporting.md'
        if common.is_file():
            copy_map = {dst: src for src, dst in copies}
            destinations = set(scheduled.glob('*/SKILL.md')) | {dst for _, dst in copies if dst.parent.parent == scheduled and dst.name == 'SKILL.md'}
            marker = '\n\n## Avances durante el día · Desk'
            for dst in sorted(destinations):
                if dst.parent.name == 'secretary-briefing':
                    continue  # It creates the report; it must not report its own report.
                original = overrides.get(str(dst))
                if original is None:
                    original = copy_map[dst].read_bytes() if dst in copy_map else dst.read_bytes()
                overrides[str(dst)] = (original.decode().split(marker)[0] + common.read_text()).encode()
                if dst not in copy_map:
                    copies.append((common, dst))
    # Validate the whole batch before the first write, including stale private
    # sources and newer installations. A failed preflight leaves every target intact.
    for src, dst in copies:
        check_close_destination(src, dst)
    primary = targets[0] if targets else None
    layout = []  # (kind, path): 'link' → symlink into primary, 'prune' → remove copy
    for kind, dirs in (('link', links), ('prune', prunes)):
        for folder in dirs:
            for name, origin in origins.items():
                dst = folder/name
                if not dst.is_symlink():
                    check_close_destination(origin/'SKILL.md', dst/'SKILL.md')
                layout.append((kind, dst))
    names = source/'secretary/data/desk_names.json'
    retired = json.loads(names.read_text()).get('retired_skills', []) if names.is_file() else []
    for folder in [*targets, *links, *prunes]:
        for name in retired:
            if name not in origins and ((folder/name).exists() or (folder/name).is_symlink()):
                layout.append(('retire', folder/name))
    revision = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True)
    source_commit = revision.stdout.strip() if revision.returncode == 0 else None
    plan = []
    for src, dst in copies:
        data = overrides.get(str(dst), src.read_bytes());changed = not dst.exists() or dst.read_bytes() != data
        plan.append({'source': str(src), 'destination': str(dst), 'changed': changed,
                     'sha256': hashlib.sha256(data).hexdigest(), 'source_commit': source_commit,
                     **({'close_contract': close_contract(src)}
                        if src.name == 'SKILL.md' and src.parent.name in CLOSE_SKILLS else {})})
        if apply and changed:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                backup = runtime/'backups'/hashlib.sha256(str(dst).encode()).hexdigest()/hashlib.sha256(dst.read_bytes()).hexdigest()
                backup.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(dst, backup)
            tmp = dst.with_name(dst.name+'.desk-tmp');tmp.write_bytes(data);tmp.replace(dst)
    for kind, dst in layout:
        want = primary/dst.name if kind == 'link' else None
        if kind == 'link':
            changed = not (dst.is_symlink() and dst.resolve() == want.resolve())
        else:  # 'prune' and 'retire' remove whatever is installed there.
            changed = dst.exists() or dst.is_symlink()
        plan.append({kind: str(dst), 'changed': changed, **({'target': str(want)} if want else {})})
        if apply and changed:
            if dst.is_symlink():
                dst.unlink()
            elif dst.exists():
                backup = runtime/'backups'/hashlib.sha256(str(dst).encode()).hexdigest()/'tree'
                shutil.rmtree(backup, ignore_errors=True);shutil.copytree(dst, backup, symlinks=True)
                shutil.rmtree(dst)
            if want is not None:
                dst.parent.mkdir(parents=True, exist_ok=True);dst.symlink_to(want, target_is_directory=True)
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
    p.add_argument('--link',type=Path,action='append',default=[]);p.add_argument('--prune',type=Path,action='append',default=[])
    p.add_argument('--instance-skills',type=Path)
    p.add_argument('--scheduled',type=Path);p.add_argument('--bin-dir',type=Path);p.add_argument('--apply',action='store_true')
    a=p.parse_args();print(json.dumps(deployment(a.source,a.target,a.runtime,a.apply,a.scheduled,a.bin_dir,
                                                 a.instance_skills,a.link,a.prune),indent=2))


if __name__=='__main__':main()
