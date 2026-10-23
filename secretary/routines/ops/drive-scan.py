#!/usr/bin/env python3
"""Detección de cambios de drive-crawler sin LLM (D15.8, n5 pieza 4).

Lista las zonas `delta` del mapa de zonas del playbook, excluye zonas sensibles y
`skip`, aplica el filtro de tipos y compara contra el corte de la corrida previa.
Entrega un JSON compacto con solo lo nuevo o cambiado, clasificado por zona,
política y acción (contenido | metadata | skip), más los archivos sueltos del
root de My Drive para el paso 4.

Fuentes (nada de datos de la instancia en este archivo):
- Mapa de zonas, zonas sensibles y carpetas skip: tablas de
  `playbooks/drive-crawler/SKILL.md` (sección 0 y filtro de tipos).
- Raíz del Drive: `secretary config get drive.mount` (o `--mount`).
- Espejos WIP: `$SECRETARY_INSTANCE/extractors/drive/memory/espejos-wip.md`.
- Corte: fecha de "Última corrida" en `extractors/drive/state.md`; si no se puede
  leer, el marker del playbook; si tampoco, 24 h.

Vía de acceso: filesystem del Drive montado (vía A del playbook). Solo lee
metadata (`os.walk` + `stat`), nunca contenido.

  drive-scan.py [--out FILE] [--state FILE] [--since ISO] [--dry-run]

`--dry-run` no escribe nada: imprime el JSON en stdout. Sin `--dry-run`, escribe
`--out` (por defecto `$TMPDIR/drive-scan-<ts>.json`) e imprime un resumen.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

CORE = Path(__file__).resolve().parents[3]
DEFAULT_PLAYBOOK = CORE / 'playbooks/drive-crawler/SKILL.md'
DEFAULT_MARKER = '/tmp/drive-last-run-marker'

# Filtro de tipos del playbook (sección 1, "Filtro de tipos").
CONTENT_EXT = {'.gdoc', '.gsheet', '.gslides', '.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.csv'}
METADATA_EXT = {
    '.gform', '.gdraw', '.gmap', '.gsite', '.gjam',
    '.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp', '.svg', '.tif', '.tiff', '.bmp',
    '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v',
    '.mp3', '.m4a', '.wav', '.ogg', '.aac', '.flac', '.opus',
}
SKIP_EXT = {'.zip', '.gz', '.tgz', '.tar', '.7z', '.rar', '.bz2', '.xz', '.dmg', '.pkg', '.exe', '.iso'}
SENSITIVE_WORDS = re.compile(r'password|contraseña|credential|token|key', re.IGNORECASE)
UNTITLED = re.compile(r'^Untitled (document|spreadsheet|presentation)', re.IGNORECASE)
IGNORED_NAMES = {'.DS_Store', 'Icon\r', 'desktop.ini', '.localized'}
ROOT_TOKEN = 'root'


@dataclass(frozen=True)
class Zone:
    pattern: str          # tal cual en la tabla (p. ej. `$INSPIRO/1 PRODUCTOS/2025*/`)
    parts: tuple[str, ...]  # componentes absolutos resueltos, con globs
    policy: str           # delta | backfill | mapa | skip | sensible
    is_dir: bool


# ---------------------------------------------------------------- parsing

def secretary_config(key: str) -> str:
    try:
        out = subprocess.run(['secretary', 'config', 'get', key], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return out.stdout.strip() if out.returncode == 0 else ''


def parse_root_vars(text: str, mount: str) -> dict[str, str]:
    """Resuelve el bloque `NAME="$OTHER/…"` del playbook. GDRIVE = raíz montada."""
    env = {'GDRIVE': mount.rstrip('/')}
    pending = re.findall(r'^([A-Z_]+)="\$([A-Z_]+)/([^"]*)"\s*$', text, re.MULTILINE)
    for _ in range(len(pending) + 1):
        for name, base, rest in pending:
            if name not in env and base in env:
                env[name] = f'{env[base]}/{rest}'
    return env


def expand(pattern: str, env: dict[str, str]) -> str | None:
    m = re.match(r'^\$([A-Z_]+)(/.*)?$', pattern)
    if not m or m.group(1) not in env:
        return None
    return env[m.group(1)] + (m.group(2) or '')


def parse_zones(text: str, env: dict[str, str]) -> list[Zone]:
    zones: list[Zone] = []

    def add(raw: str, policy: str) -> None:
        path = expand(raw, env)
        if path is None:
            return
        is_dir = raw.endswith('/') or raw.endswith('/' + ROOT_TOKEN)
        parts = tuple(p for p in path.split('/') if p)
        zones.append(Zone(raw, parts, policy, is_dir))

    # Tablas `| `$X/…`[, `…`] | **política** | notas |`
    for line in text.splitlines():
        m = re.match(r'^\|\s*(`.+?)\|\s*\*\*(delta|backfill|mapa|skip)\*\*\s*\|', line)
        if not m:
            continue
        specs = re.findall(r'`([^`]+)`', m.group(1))
        first = None
        for spec in specs:
            if spec.startswith('$'):
                first = spec
                add(spec, m.group(2))
            elif first is not None:  # `2026*/` relativo al padre del primero
                parent = first.rstrip('/').rsplit('/', 1)[0]
                add(f'{parent}/{spec}', m.group(2))

    # Zonas sensibles: viñetas tras "Zonas sensibles" hasta la primera línea en blanco.
    block = re.search(r'\*\*Zonas sensibles[^\n]*\n((?:- .*\n)+)', text)
    if block:
        for spec in re.findall(r'^- `([^`]+)`', block.group(1), re.MULTILINE):
            add(spec, 'sensible')
    return zones


def parse_skip_folders(text: str) -> set[str]:
    """Carpetas `SKIP completo` del filtro de tipos: `- Carpeta `X` (id: …)`."""
    block = re.search(r'\*\*SKIP completo\*\*[^\n]*\n((?:- .*\n)+)', text)
    if not block:
        return set()
    return set(re.findall(r'^- Carpeta `([^`]+)`', block.group(1), re.MULTILINE))


def parse_mirrors(path: Path) -> list[str]:
    """Rutas espejo de WIP: spans en backticks antes del primer ` (` de cada viñeta."""
    if not path.is_file():
        return []
    text = path.read_text(encoding='utf-8')
    items: list[str] = []
    bullets = re.split(r'\n(?=- )', text)
    for bullet in bullets:
        if not bullet.startswith('- '):
            continue
        flat = re.sub(r'\s*\n\s*', ' ', bullet)
        # Cortar en el primer " (" fuera de backticks: el resto describe el espejo local.
        outside = re.sub(r'`[^`]*`', lambda m: 'x' * len(m.group(0)), flat)
        cut = outside.find(' (')
        head = flat if cut == -1 else flat[:cut]
        for span in re.findall(r'`([^`]+)`', head):
            span = span.replace('/ ', '/').strip()
            if span.startswith('~') or span.startswith('$'):
                continue
            span = re.sub(r'(/?\.\.\.|/?…)$', '', span).rstrip('/')
            if span:
                items.append(span)
    return items


def parse_state_cutoff(path: Path, tz: timezone | object) -> datetime | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding='utf-8')
    sec = re.search(r'^## Última corrida\s*\n(.*?)(?=^#)', text, re.MULTILINE | re.DOTALL)
    body = sec.group(1) if sec else text
    m = re.search(r'Fecha:\s*\**\s*(\d{4}-\d{2}-\d{2})(?:[ T~]*(\d{1,2}:\d{2}))?', body)
    if not m:
        return None
    hhmm = m.group(2) or '00:00'
    return datetime.strptime(f'{m.group(1)} {hhmm}', '%Y-%m-%d %H:%M').replace(tzinfo=tz)  # type: ignore[arg-type]


# ---------------------------------------------------------------- classification

def zone_match(zone: Zone, parts: tuple[str, ...], is_dir: bool) -> bool:
    """¿`parts` (ruta absoluta) cae dentro de la zona?"""
    zp = zone.parts
    if zp and zp[-1] == ROOT_TOKEN:
        return not is_dir and len(parts) == len(zp) and parts[:-1] == zp[:-1]
    if len(parts) < len(zp):
        return False
    if not zone.is_dir and len(parts) != len(zp):
        return False
    return all(fnmatch.fnmatchcase(p, z) for p, z in zip(parts, zp))


def best_zone(zones: list[Zone], parts: tuple[str, ...], is_dir: bool = False) -> Zone | None:
    """La zona más específica; `sensible` gana siempre."""
    hits = [z for z in zones if zone_match(z, parts, is_dir)]
    if not hits:
        return None
    for z in hits:
        if z.policy == 'sensible':
            return z
    return max(hits, key=lambda z: (len(z.parts), z.parts[-1] != ROOT_TOKEN))


def is_mirror(rel: str, mirrors: list[str]) -> bool:
    probe = '/' + rel
    for m in mirrors:
        i = probe.find('/' + m)
        while i != -1:
            end = i + 1 + len(m)
            if end == len(probe) or probe[end] == '/':
                return True
            i = probe.find('/' + m, i + 1)
    return False


def action_for(name: str, rel: str, mirrors: list[str]) -> tuple[str, str]:
    ext = os.path.splitext(name)[1].lower()
    if ext in SKIP_EXT:
        return 'skip', 'tipo'
    if is_mirror(rel, mirrors):
        return 'metadata', 'espejo-wip'
    if SENSITIVE_WORDS.search(name):
        return 'metadata', 'nombre-sensible'
    if UNTITLED.match(name):
        return 'metadata', 'untitled'
    if ext in CONTENT_EXT:
        return 'contenido', 'tipo'
    if ext in METADATA_EXT:
        return 'metadata', 'tipo'
    return 'metadata', 'tipo-desconocido'


# ---------------------------------------------------------------- scan

def iso(ts: float, tz: object) -> str:
    return datetime.fromtimestamp(ts, tz).isoformat(timespec='seconds')  # type: ignore[arg-type]


def scan(args: argparse.Namespace) -> dict:
    tz_name = args.tz or secretary_config('timezone')
    tz: object = timezone.utc
    if tz_name and ZoneInfo is not None:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            tz = datetime.now().astimezone().tzinfo or timezone.utc
    else:
        tz = datetime.now().astimezone().tzinfo or timezone.utc

    mount = args.mount or secretary_config('drive.mount')
    if not mount:
        raise SystemExit('drive-scan: falta la raíz del Drive (drive.mount o --mount)')
    playbook = Path(args.playbook).read_text(encoding='utf-8')
    env = parse_root_vars(playbook, mount)
    zones = parse_zones(playbook, env)
    skip_folders = parse_skip_folders(playbook)
    instance = Path(os.environ.get('SECRETARY_INSTANCE', str(Path.home() / '.secretary')))
    mirrors = parse_mirrors(Path(args.mirrors) if args.mirrors else instance / 'extractors/drive/memory/espejos-wip.md')
    state = Path(args.state) if args.state else instance / 'extractors/drive/state.md'

    now = datetime.now(tz)  # type: ignore[arg-type]
    marker = Path(args.marker)
    marker_dt = datetime.fromtimestamp(marker.stat().st_mtime, tz) if marker.is_file() else None  # type: ignore[arg-type]
    state_dt = parse_state_cutoff(state, tz)
    if args.since:
        cutoff, source = datetime.fromisoformat(args.since), 'since'
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=tz)  # type: ignore[arg-type]
    elif state_dt:
        cutoff, source = state_dt - timedelta(minutes=args.margin), 'state.md'
    elif marker_dt:
        cutoff, source = marker_dt - timedelta(minutes=args.margin), 'marker'
    else:
        cutoff, source = now - timedelta(hours=24), '24h'
    cut_ts = cutoff.timestamp()

    mount_parts = tuple(p for p in mount.rstrip('/').split('/') if p)

    def rel(parts: tuple[str, ...]) -> str:
        return '/'.join(parts[len(mount_parts):])

    def excluded_dir(parts: tuple[str, ...]) -> str | None:
        if parts[-1] in skip_folders:
            return 'skip'
        z = best_zone(zones, parts, is_dir=True)
        if z and z.policy in ('sensible', 'skip', 'mapa', 'backfill') and len(parts) >= len(z.parts):
            return z.policy
        return None

    delta = [z for z in zones if z.policy == 'delta' and z.parts[-1] != ROOT_TOKEN]
    files: list[dict] = []
    excluded = {'sensible': 0, 'skip': 0, 'mapa': 0, 'backfill': 0}
    zone_rows: list[dict] = []
    seen: set[str] = set()

    for zone in delta:
        # Expandir globs de la zona contra el disco.
        starts = [Path('/')]
        ok = True
        for comp in zone.parts:
            nxt: list[Path] = []
            for base in starts:
                if any(c in comp for c in '*?['):
                    try:
                        nxt += [base / n for n in sorted(os.listdir(base)) if fnmatch.fnmatchcase(n, comp)]
                    except OSError:
                        pass
                elif (base / comp).exists():
                    nxt.append(base / comp)
            starts = nxt
            if not starts:
                ok = False
                break
        row = {'zona': zone.pattern, 'montada': ok, 'nuevos': 0}
        zone_rows.append(row)
        for start in starts if ok else []:
            targets: list[tuple[Path, str]] = []
            if start.is_file():
                targets.append((start, start.name))
            else:
                for dirpath, dirnames, filenames in os.walk(start):
                    dparts = tuple(p for p in dirpath.split('/') if p)
                    keep = []
                    for d in sorted(dirnames):
                        why = excluded_dir(dparts + (d,))
                        if why:
                            excluded[why] += 1
                        else:
                            keep.append(d)
                    dirnames[:] = keep
                    targets += [(Path(dirpath) / f, f) for f in filenames]
            for path, name in targets:
                if name in IGNORED_NAMES or str(path) in seen:
                    continue
                fparts = tuple(p for p in str(path).split('/') if p)
                z = best_zone(zones, fparts)
                if z is None or z.policy != 'delta':
                    if z is not None and z.policy in excluded:
                        excluded[z.policy] += 1
                    continue
                if z is not zone:
                    continue  # lo cuenta la zona más específica
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime <= cut_ts:
                    continue
                seen.add(str(path))
                accion, motivo = action_for(name, rel(fparts), mirrors)
                files.append({'ruta': rel(fparts), 'zona': z.pattern, 'politica': z.policy,
                              'accion': accion, 'motivo': motivo, 'modificado': iso(mtime, tz)})
                row['nuevos'] += 1

    # Root de My Drive: todos los archivos sueltos (paso 4), con marca de nuevos.
    root_zone = next((z for z in zones if z.parts[-1] == ROOT_TOKEN), None)
    root_rows: list[dict] = []
    root_info: dict = {'zona': root_zone.pattern if root_zone else None, 'montada': False}
    if root_zone:
        root_dir = Path('/' + '/'.join(root_zone.parts[:-1]))
        if root_dir.is_dir():
            root_info['montada'] = True
            for entry in sorted(os.scandir(root_dir), key=lambda e: e.name):
                if not entry.is_file() or entry.name in IGNORED_NAMES:
                    continue
                eparts = tuple(p for p in entry.path.split('/') if p)
                z = best_zone(zones, eparts)
                if z is not None and z.policy in ('sensible', 'skip'):
                    excluded[z.policy] += 1
                    continue
                mtime = entry.stat().st_mtime
                accion, motivo = action_for(entry.name, rel(eparts), mirrors)
                root_rows.append({'nombre': entry.name, 'modificado': iso(mtime, tz), 'nuevo': mtime > cut_ts,
                                  'accion': accion, 'motivo': motivo})
    root_rows.sort(key=lambda r: r['modificado'], reverse=True)

    files.sort(key=lambda f: f['modificado'], reverse=True)
    by_zone: dict[str, dict[str, int]] = {}
    by_action: dict[str, int] = {}
    for f in files:
        by_zone.setdefault(f['zona'], {}).setdefault(f['accion'], 0)
        by_zone[f['zona']][f['accion']] += 1
        by_action[f['accion']] = by_action.get(f['accion'], 0) + 1

    backfill = []
    for z in zones:
        if z.policy == 'backfill':
            p = Path('/' + '/'.join(z.parts))
            mounted = bool(next(iter(Path('/').glob('/'.join(z.parts))), None)) if any(
                c in z.pattern for c in '*?[') else p.exists()
            backfill.append({'zona': z.pattern, 'montada': mounted})

    return {
        'generado': now.isoformat(timespec='seconds'),
        'corte': cutoff.isoformat(timespec='seconds'),
        'corte_fuente': source,
        'state_md': state_dt.isoformat(timespec='seconds') if state_dt else None,
        'marker': marker_dt.isoformat(timespec='seconds') if marker_dt else None,
        'zonas_delta': zone_rows,
        'conteos': {'por_zona': by_zone, 'por_accion': by_action, 'excluidos': excluded,
                    'root_total': len(root_rows), 'root_nuevos': sum(1 for r in root_rows if r['nuevo'])},
        'archivos': files,
        'root': {**root_info, 'archivos': root_rows},
        'backfill': backfill,
        'espejos_cargados': len(mirrors),
    }


def summary(data: dict) -> str:
    c = data['conteos']
    lines = [f"corte={data['corte']} ({data['corte_fuente']}) nuevos={len(data['archivos'])} "
             f"root={c['root_total']} root_nuevos={c['root_nuevos']}"]
    for z in data['zonas_delta']:
        acc = c['por_zona'].get(z['zona'], {})
        detail = ' '.join(f'{k}={v}' for k, v in sorted(acc.items())) or '-'
        lines.append(f"  {'ok ' if z['montada'] else 'NO '} {z['zona']}: {z['nuevos']} ({detail})")
    lines.append('  excluidos: ' + ' '.join(f'{k}={v}' for k, v in c['excluidos'].items()))
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', help='archivo JSON de salida (por defecto $TMPDIR/drive-scan-<ts>.json)')
    ap.add_argument('--state', help='state.md de la corrida (por defecto el de la instancia)')
    ap.add_argument('--since', help='corte ISO explícito; ignora state.md y marker')
    ap.add_argument('--margin', type=int, default=15, help='minutos de solape antes del corte (15)')
    ap.add_argument('--marker', default=DEFAULT_MARKER, help='marker del playbook (fallback del corte)')
    ap.add_argument('--mount', help='raíz del Drive montado (por defecto drive.mount)')
    ap.add_argument('--playbook', default=str(DEFAULT_PLAYBOOK), help='SKILL.md con el mapa de zonas')
    ap.add_argument('--mirrors', help='lista de espejos WIP (por defecto la de la instancia)')
    ap.add_argument('--tz', help='zona horaria (por defecto la de la config)')
    ap.add_argument('--dry-run', action='store_true', help='no escribe nada; JSON a stdout')
    args = ap.parse_args(argv)

    data = scan(args)
    if args.dry_run:
        print(summary(data), file=sys.stderr)
        json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    out = Path(args.out) if args.out else Path(tempfile.gettempdir()) / f"drive-scan-{datetime.now():%Y%m%d-%H%M}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(summary(data))
    print(f'OUT={out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
