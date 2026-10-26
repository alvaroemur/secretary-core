"""Detección de cambios de Drive sin LLM (secretary/routines/ops/drive-scan.py)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'secretary/routines/ops/drive-scan.py'

PLAYBOOK = """# drive-crawler (fixture)

```bash
GDRIVE="$(secretary config get drive.mount)"
MY_DRIVE="$GDRIVE/My Drive"
SHARED="$GDRIVE/Shared drives"
TEAM="$SHARED/Team Drive"
```

| Zona | Política | Notas |
|---|---|---|
| `$MY_DRIVE/Trabajo/` | **delta** | activo |
| `$MY_DRIVE/Trabajo/Viejo/` | **mapa** | solo existencia |
| `$MY_DRIVE/Personal/` | **mapa** | sensible |
| `$MY_DRIVE/Personal/Ensayos/` | **skip** | no indexar |
| `$MY_DRIVE/root` (archivos sueltos) | **delta** | paso 4 |
| `$TEAM/1 PRODUCTOS/2025*/`, `2026*/` | **delta** | productos |
| `$TEAM/4 CRECEMOS/CRM.gsheet` | **delta** | crm |
| `$TEAM/4 CRECEMOS/` (resto) | **delta** | resto |
| `$TEAM/5 PROYECTOS/2026*/` | **delta** | activos |
| `$TEAM/5 PROYECTOS/Z_*` | **mapa** | cerrados |
| `$TEAM/2 FUNDACIONAL/` | **backfill** | doctrina |

**Zonas sensibles — skip absoluto (ni metadata):**
- `$MY_DRIVE/Personal/Passwords.gsheet`
- `$MY_DRIVE/llaves/`
- `$MY_DRIVE/Trabajo/Privado/`

**SKIP completo** (ni metadata):
- Carpeta `Backups` (id: `secretary config get drive.folders.backups`)
- Archivos con título "Untitled document" — registrar pero no leer
"""

MIRRORS = """# Espejos

- `Trabajo/Borradores/` (espejo de `~/Cowork/x/`)
- `Team Drive/5 PROYECTOS/2026 Cliente (piloto)/Salidas/`
  (pipeline; añadido 2026-10-10)
"""

FAKE_SECRETARY = """#!/usr/bin/env bash
case "$3" in
  drive.mount) echo "$FAKE_MOUNT" ;;
  timezone) echo "UTC" ;;
  *) exit 1 ;;
esac
"""

OLD = time.time() - 10 * 86400
NEW = time.time() - 3600


def load_module():
    spec = importlib.util.spec_from_file_location('drive_scan', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['drive_scan'] = mod
    spec.loader.exec_module(mod)
    return mod


class DriveScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.mount = root / 'drive'
        files = {
            'My Drive/Trabajo/a.gdoc': NEW,
            'My Drive/Trabajo/viejo.pdf': OLD,
            'My Drive/Trabajo/foto.jpg': NEW,
            'My Drive/Trabajo/paquete.zip': NEW,
            'My Drive/Trabajo/api key notes.txt': NEW,
            'My Drive/Trabajo/Untitled document.gdoc': NEW,
            'My Drive/Trabajo/Viejo/x.pdf': NEW,
            'My Drive/Trabajo/Privado/s.pdf': NEW,
            'My Drive/Trabajo/Backups/b.pdf': NEW,
            'My Drive/Trabajo/Borradores/d.gdoc': NEW,
            'My Drive/Trabajo/.DS_Store': NEW,
            'My Drive/Personal/Ensayos/e.gdoc': NEW,
            'My Drive/Personal/Passwords.gsheet': NEW,
            'My Drive/llaves/k.txt': NEW,
            'My Drive/suelto-nuevo.csv': NEW,
            'My Drive/suelto-viejo.pdf': OLD,
            'Shared drives/Team Drive/1 PRODUCTOS/2025 A/p.pptx': NEW,
            'Shared drives/Team Drive/1 PRODUCTOS/2026 B/q.docx': NEW,
            'Shared drives/Team Drive/1 PRODUCTOS/2024 C/r.docx': NEW,
            'Shared drives/Team Drive/4 CRECEMOS/CRM.gsheet': NEW,
            'Shared drives/Team Drive/4 CRECEMOS/prop.pdf': NEW,
            'Shared drives/Team Drive/5 PROYECTOS/2026 Cliente (piloto)/Salidas/o.pdf': NEW,
            'Shared drives/Team Drive/5 PROYECTOS/2026 Cliente (piloto)/plan.xlsx': NEW,
            'Shared drives/Team Drive/5 PROYECTOS/Z_cerrado/z.pdf': NEW,
            'Shared drives/Team Drive/2 FUNDACIONAL/f.pdf': NEW,
        }
        for rel, mtime in files.items():
            p = self.mount / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('x')
            os.utime(p, (mtime, mtime))
        self.playbook = root / 'SKILL.md'; self.playbook.write_text(PLAYBOOK)
        self.instance = root / 'instance'
        mem = self.instance / 'extractors/drive/memory'; mem.mkdir(parents=True)
        (mem / 'espejos-wip.md').write_text(MIRRORS)
        self.state = self.instance / 'extractors/drive/state.md'
        cut = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() - 2 * 86400))
        self.state.write_text(f'# Estado\n\n## Última corrida\n- Fecha: {cut[:10]} ~{cut[11:]} UTC — incremental\n\n### Corrida previa\n- Fecha: 2020-01-01 ~04:00\n')
        bin_dir = root / 'bin'; bin_dir.mkdir()
        (bin_dir / 'secretary').write_text(FAKE_SECRETARY); (bin_dir / 'secretary').chmod(0o755)
        self.out = root / 'out.json'
        self.env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'FAKE_MOUNT': str(self.mount),
                    'SECRETARY_INSTANCE': str(self.instance)}
        self.marker = root / 'no-marker'

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        out = subprocess.run([sys.executable, str(SCRIPT), '--playbook', str(self.playbook),
                              '--marker', str(self.marker), *args],
                             env=self.env, capture_output=True, text=True)
        if out.returncode != 0:
            self.fail(out.stderr)
        return out

    def scan(self, *args: str) -> dict:
        return json.loads(self.run_script('--dry-run', *args).stdout)

    def test_classifies_only_new_delta_files(self) -> None:
        data = self.scan()
        got = {f['ruta']: (f['accion'], f['motivo']) for f in data['archivos']}
        self.assertEqual(got, {
            'My Drive/Trabajo/a.gdoc': ('contenido', 'tipo'),
            'My Drive/Trabajo/foto.jpg': ('metadata', 'tipo'),
            'My Drive/Trabajo/paquete.zip': ('skip', 'tipo'),
            'My Drive/Trabajo/api key notes.txt': ('metadata', 'nombre-sensible'),
            'My Drive/Trabajo/Untitled document.gdoc': ('metadata', 'untitled'),
            'My Drive/Trabajo/Borradores/d.gdoc': ('metadata', 'espejo-wip'),
            'Shared drives/Team Drive/1 PRODUCTOS/2025 A/p.pptx': ('contenido', 'tipo'),
            'Shared drives/Team Drive/1 PRODUCTOS/2026 B/q.docx': ('contenido', 'tipo'),
            'Shared drives/Team Drive/4 CRECEMOS/CRM.gsheet': ('contenido', 'tipo'),
            'Shared drives/Team Drive/4 CRECEMOS/prop.pdf': ('contenido', 'tipo'),
            'Shared drives/Team Drive/5 PROYECTOS/2026 Cliente (piloto)/Salidas/o.pdf': ('metadata', 'espejo-wip'),
            'Shared drives/Team Drive/5 PROYECTOS/2026 Cliente (piloto)/plan.xlsx': ('contenido', 'tipo'),
        })
        zones = {f['ruta']: f['zona'] for f in data['archivos']}
        self.assertEqual(zones['Shared drives/Team Drive/4 CRECEMOS/CRM.gsheet'], '$TEAM/4 CRECEMOS/CRM.gsheet')
        self.assertEqual(zones['Shared drives/Team Drive/1 PRODUCTOS/2026 B/q.docx'], '$TEAM/1 PRODUCTOS/2026*/')
        self.assertTrue(all(f['politica'] == 'delta' for f in data['archivos']))
        excl = data['conteos']['excluidos']
        self.assertEqual((excl['sensible'], excl['skip'], excl['mapa']), (1, 1, 1))
        self.assertEqual(data['corte_fuente'], 'state.md')

    def test_root_lists_all_loose_files_with_new_flag(self) -> None:
        data = self.scan()
        root = {r['nombre']: r['nuevo'] for r in data['root']['archivos']}
        self.assertEqual(root, {'suelto-nuevo.csv': True, 'suelto-viejo.pdf': False})
        self.assertEqual((data['conteos']['root_total'], data['conteos']['root_nuevos']), (2, 1))
        self.assertEqual(data['backfill'], [{'zona': '$TEAM/2 FUNDACIONAL/', 'montada': True}])

    def test_cutoff_falls_back_to_marker_then_24h(self) -> None:
        self.state.unlink()
        self.marker.write_text('')
        t = time.time() - 30 * 86400
        os.utime(self.marker, (t, t))
        data = self.scan('--margin', '0')
        self.assertEqual(data['corte_fuente'], 'marker')
        self.assertIn('My Drive/Trabajo/viejo.pdf', {f['ruta'] for f in data['archivos']})
        self.marker.unlink()
        self.assertEqual(self.scan()['corte_fuente'], '24h')

    def test_since_overrides_state(self) -> None:
        data = self.scan('--since', '2000-01-01T00:00:00+00:00')
        self.assertEqual(data['corte_fuente'], 'since')
        self.assertIn('My Drive/Trabajo/viejo.pdf', {f['ruta'] for f in data['archivos']})

    def test_dry_run_writes_nothing_and_normal_run_writes_out(self) -> None:
        self.run_script('--dry-run', '--out', str(self.out))
        self.assertFalse(self.out.exists())
        res = self.run_script('--out', str(self.out))
        self.assertIn(f'OUT={self.out}', res.stdout)
        self.assertEqual(len(json.loads(self.out.read_text())['archivos']), 12)

    def test_real_playbook_zone_map_parses(self) -> None:
        mod = load_module()
        text = (ROOT / 'playbooks/drive-crawler/SKILL.md').read_text(encoding='utf-8')
        env = mod.parse_root_vars(text, '/mnt')
        zones = mod.parse_zones(text, env)
        policies = {z.policy for z in zones}
        self.assertTrue({'delta', 'backfill', 'mapa', 'skip', 'sensible'} <= policies)
        self.assertTrue(any(z.parts[-1] == mod.ROOT_TOKEN for z in zones))
        self.assertTrue(all(z.parts[0] == 'mnt' for z in zones))
        self.assertTrue(mod.parse_skip_folders(text))


if __name__ == '__main__':
    unittest.main()
