import os
import plistlib
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from secretary.context import collect_routines, format_compact
from secretary.routines.launchd_cron import parse_cron

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "secretary" / "routines" / "install-routine-schedule.sh"

MANIFEST = textwrap.dedent(
    """\
    timezone: America/Lima
    routines:
      - id: housekeeping
        cron: "0 6 * * *"
        enabled: true
      - id: sales-crawler
        cron: "0 8 * * 1-5"
      - id: whatsapp-monitor
        cron: "*/15 8-20 * * *"
        enabled: false
      - id: soltrak-correo
        cron: "0 11 * * *"
        enabled: false
    """
)


def _instance(tmp: str) -> Path:
    inst = Path(tmp)
    (inst / ".cursor" / "routines").mkdir(parents=True)
    (inst / ".cursor" / "routines" / "manifest.yaml").write_text(MANIFEST, encoding="utf-8")
    return inst


class CollectRoutinesTests(unittest.TestCase):
    def test_enabled_false_marks_routine_disabled(self):
        with tempfile.TemporaryDirectory() as tmp, patch("secretary.context.instance_root", return_value=_instance(tmp)):
            data = collect_routines({})
        status = {r["id"]: r["status"] for r in data["routines"]}
        self.assertEqual(
            status,
            {
                "housekeeping": "active",
                "sales-crawler": "active",
                "whatsapp-monitor": "disabled",
                "soltrak-correo": "disabled",
            },
        )

    def test_config_disabled_list_still_applies(self):
        cfg = {"dispatch": {"routines": {"disabled": ["housekeeping"]}}}
        with tempfile.TemporaryDirectory() as tmp, patch("secretary.context.instance_root", return_value=_instance(tmp)):
            data = collect_routines(cfg)
        status = {r["id"]: r["status"] for r in data["routines"]}
        self.assertEqual(status["housekeeping"], "disabled")
        self.assertEqual(status["sales-crawler"], "active")

    def test_compact_counts_only_active_routines(self):
        with tempfile.TemporaryDirectory() as tmp, patch("secretary.context.instance_root", return_value=_instance(tmp)):
            data = {"routines": collect_routines({})}
        self.assertIn("Scheduled Routines: 2", format_compact(data))


class ParseCronTests(unittest.TestCase):
    def test_weekday_range_matches_weekday_list(self):
        expected = [{"Weekday": d, "Hour": 8, "Minute": 0} for d in range(1, 6)]
        self.assertEqual(parse_cron("0 8 * * 1-5"), expected)
        self.assertEqual(parse_cron("0 8 * * 1,2,3,4,5"), expected)
        self.assertEqual(parse_cron("0 8 * * mon-fri"), expected)

    def test_ranges_lists_and_steps_in_minute_and_hour(self):
        intervals = parse_cron("0,30 8-10 * * *")
        self.assertEqual(
            [(i["Hour"], i["Minute"]) for i in intervals],
            [(8, 0), (8, 30), (9, 0), (9, 30), (10, 0), (10, 30)],
        )
        self.assertEqual([i["Minute"] for i in parse_cron("*/20 9 * * *")], [0, 20, 40])
        self.assertEqual([i["Hour"] for i in parse_cron("0 8-18/5 * * *")], [8, 13, 18])

    def test_sunday_as_seven_and_mixed_list(self):
        self.assertEqual([i["Weekday"] for i in parse_cron("0 10 * * 7")], [0])
        self.assertEqual([i["Weekday"] for i in parse_cron("0 7 * * 1,3-5")], [1, 3, 4, 5])

    def test_day_of_month_and_month(self):
        self.assertEqual(parse_cron("0 9 1,15 jan *"), [
            {"Month": 1, "Day": 1, "Hour": 9, "Minute": 0},
            {"Month": 1, "Day": 15, "Hour": 9, "Minute": 0},
        ])

    def test_invalid_expressions_raise(self):
        for cron in ("0 8 * *", "0 25 * * *", "0 8 * * 5-1", "0 8 * * x", "*/0 8 * * *", "0 8 1 * 1"):
            with self.subTest(cron=cron), self.assertRaises(ValueError):
                parse_cron(cron)


class InstallerTests(unittest.TestCase):
    def test_installer_writes_range_cron_and_skips_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = _instance(str(Path(tmp) / "inst"))
            (inst / ".secretary.yml").write_text(
                "paths:\n  subsystem:\n    routines: subsystem/routines\n"
                "dispatch:\n  routines:\n    executor: cursor-cron\n",
                encoding="utf-8",
            )
            home = Path(tmp) / "home"
            home.mkdir()
            env = {
                **os.environ,
                "HOME": str(home),
                "SECRETARY_INSTANCE": str(inst),
                "SECRETARY_CORE": str(REPO),
                "SECRETARY_ROUTINES_EXECUTOR": "cursor-cron",
            }
            result = subprocess.run(["bash", str(INSTALLER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            agents = home / "Library" / "LaunchAgents"
            plists = {p.name.rsplit(".", 2)[-2]: p for p in agents.glob("*.plist")}
            self.assertEqual(sorted(plists), ["housekeeping", "sales-crawler"])
            sales = plistlib.loads(plists["sales-crawler"].read_bytes())
            self.assertEqual([i["Weekday"] for i in sales["StartCalendarInterval"]], [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
