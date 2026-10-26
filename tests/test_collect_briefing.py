"""Tests sin red del recolector de secretary-briefing (secretary/routines/ops/briefing-collect.py)."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT = Path(__file__).resolve().parents[1] / "secretary/routines/ops/briefing-collect.py"
spec = importlib.util.spec_from_file_location("briefing_collect", SCRIPT)
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

CONFIG = {
    "instance": "/tmp/instancia-inexistente",
    "timezone": "America/New_York",
    "brief": {"repo": "owner/briefs", "label": "tipo:informe-diario"},
    "dispatch": {"executor": {"repos": [{"repo": "owner/a", "path": "~/a"}, {"repo": "owner/b", "path": "~/b"}]}},
}

SECTIONS = ["config", "briefs", "decisions", "signals", "conversations", "repos", "heartbeat",
            "freshness", "routine_runs", "loops", "instance_git", "calendar", "sources", "failed_sources"]


class FakeCollector(bc.Collector):
    """Sin subprocess: cada fuente devuelve un dato fijo o falla."""

    def config_section(self):
        return {"brief_repo": self.brief_repo, "repos_enabled": [r["repo"] for r in self.repos]}

    def briefs(self):
        return {"recent": [], "today_issue": None, "previous_open": None}

    def decisions(self):
        return {"count": 0, "items": [], "errors": []}

    def signals(self):
        raise bc.SourceError("comando no disponible: secretary-desk")

    def conversations(self):
        return {"questions": [], "pending": []}

    def repo_prs(self, repo):
        if repo == "owner/b":
            raise RuntimeError("gh caído")
        return {"open": [{"number": 1}], "merged_recent": []}

    def freshness(self):
        return {"modules": {}}

    def instance_git(self):
        return {"count": 0, "commits": []}

    def calendar(self):
        return {"count": 0, "events": []}


class BriefingCollectTests(unittest.TestCase):
    def collect(self):
        now = datetime(2026, 1, 15, 7, 45, tzinfo=ZoneInfo("America/New_York"))
        return bc.collect(now=now, config_loader=lambda: CONFIG, collector_cls=FakeCollector)

    def test_secciones_fijas_y_fecha_en_zona_configurada(self):
        data = self.collect()
        for key in SECTIONS:
            self.assertIn(key, data)
        self.assertEqual(data["today"], "2026-01-15")
        self.assertEqual(data["timezone"], "America/New_York")
        self.assertEqual(sorted(data["repos"]), ["owner/a", "owner/b"])
        self.assertIsNone(data["repos"]["owner/b"])

    def test_fuentes_fallidas_se_reportan_sin_abortar(self):
        data = self.collect()
        failed = set(data["failed_sources"])
        # signals (SourceError), repo owner/b (excepción genérica) e instancia inexistente
        self.assertTrue({"signals", "repo:owner/b", "heartbeat", "routine_runs", "loops"} <= failed, failed)
        self.assertEqual(data["sources"]["signals"]["status"], "error")
        self.assertIn("secretary-desk", data["sources"]["signals"]["error"])
        self.assertEqual(data["sources"]["decisions"]["status"], "ok")
        self.assertIsNone(data["signals"])
        json.dumps(data)

    def test_config_caida_no_aborta(self):
        def broken():
            raise bc.SourceError("comando no disponible: secretary")

        data = bc.collect(config_loader=broken, collector_cls=FakeCollector)
        self.assertEqual(data["sources"]["config"]["status"], "error")
        self.assertIn("config", data["failed_sources"])
        self.assertEqual(data["repos"], {})

    def test_routine_runs_lee_meta_de_la_ventana(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = Path(tmp, "subsystem/routines/runs/2026-01-15")
            day.mkdir(parents=True)
            (day / "x-1.meta.json").write_text(json.dumps({
                "routine_id": "x", "started_at": "2026-01-15T06:00:00-05:00", "status": "success", "exit_code": 0}))
            (day / "x-2.meta.json").write_text(json.dumps({
                "routine_id": "x", "started_at": "2026-01-15T07:00:00-05:00", "status": "error", "exit_code": 1}))
            now = datetime(2026, 1, 15, 7, 45, tzinfo=ZoneInfo("America/New_York"))
            col = bc.Collector({**CONFIG, "instance": tmp}, now, 36)
            runs = col.routine_runs()
            self.assertEqual(runs["count"], 2)
            self.assertEqual(runs["by_routine"]["x"]["failed"], 1)
            self.assertEqual(runs["by_routine"]["x"]["last_status"], "error")

    def test_main_escribe_archivo_en_directorio_indicado(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = bc.collect
            bc.collect = lambda since_hours=36: {"sources": {"config": {"status": "ok"}}, "failed_sources": []}
            try:
                self.assertEqual(bc.main(["--dry-run", "--out-dir", tmp]), 0)
            finally:
                bc.collect = original
            self.assertTrue(Path(tmp, "briefing-input.json").is_file())


if __name__ == "__main__":
    unittest.main()
