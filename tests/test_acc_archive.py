"""Tests for `secretary.acc` archive/show/fold. Synthetic fixture, stdlib only.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from secretary import acc

TODAY = date(2026, 9, 21)

PREAMBLE = """# Acciones — consolidado

Plantilla:

```markdown
## acc-YYYYMMDD-NNN
- estado: abierta
```

"""


def entry(acc_id: str, estado: str, cerrado: str = "null", wiki: str = "false", update: bool = False) -> str:
    head = f"## {acc_id} [update]" if update else f"## {acc_id}"
    key = "estado_nuevo" if update else "estado"
    return (
        f"{head}\n- titulo: t {acc_id}\n- {key}: {estado}\n- cerrado: {cerrado}\n"
        f"- pendiente_wiki: {wiki}  # comentario\n\n---\n\n"
    )


LEDGER = PREAMBLE + "".join(
    [
        entry("acc-20260101-001", "caducada", "2026-06-16"),  # old closed → moves (2026-06)
        entry("acc-20260101-001", "caducada", "2026-06-16", update=True),  # its update travels
        entry("acc-20260102-001", "hecha", "2026-08-30"),  # → 2026-08
        entry("acc-20260103-001", "hecha", "2026-09-15"),  # inside retention → stays
        entry("acc-20260104-001", "abierta"),  # alive → stays
        entry("acc-20260105-001", "en-curso"),  # alive → stays
        entry("acc-20260106-001", "caducada", "2026-06-16", wiki="true"),  # wiki pending → stays
        entry("acc-20260107-001", "caducada"),  # closed without cerrado → stays, reported
        entry("acc-20260108-001", "caducada", "2026-06-16"),  # duplicate id → stays
        entry("acc-20260108-001", "caducada", "2026-06-17"),
        entry("acc-20260109-001", "hecha", "2026-06-20", update=True),  # orphan update → stays
        "## acc-20260110-001 al 005\n- titulo: rango\n- estado: caducada\n- cerrado: 2026-06-16\n\n---\n\n",
        entry("acc-20260111-001", "caducada", "2026-06-16"),  # moves; must not drag the irregular block
    ]
)


class LedgerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / ".secretary.yml").write_text(
            "paths:\n  meetings:\n    memory: extractors/meetings/memory\n", encoding="utf-8"
        )
        self.mem = root / "extractors" / "meetings" / "memory"
        self.mem.mkdir(parents=True)
        self.ledger = self.mem / "acciones.md"
        self.ledger.write_text(LEDGER, encoding="utf-8")
        self._old = os.environ.get("SECRETARY_INSTANCE")
        os.environ["SECRETARY_INSTANCE"] = str(root)

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("SECRETARY_INSTANCE", None)
        else:
            os.environ["SECRETARY_INSTANCE"] = self._old
        self.tmp.cleanup()

    def all_digests(self) -> Counter:
        c: Counter = Counter()
        files = [self.ledger, *sorted((self.mem / "acciones" / "archivo").glob("*.md"))]
        for f in files:
            _, blocks = acc.parse_ledger(f.read_text(encoding="utf-8"))
            c.update(b.digest for b in blocks)
        return c


class ParseTests(unittest.TestCase):
    def test_lossless_and_template_stays_in_preamble(self) -> None:
        pre, blocks = acc.parse_ledger(LEDGER)
        self.assertEqual(pre + "".join(b.raw for b in blocks), LEDGER)
        self.assertNotIn("acc-YYYYMMDD-NNN", [b.acc_id for b in blocks])
        self.assertEqual(len(blocks), 13)

    def test_fields(self) -> None:
        _, blocks = acc.parse_ledger(entry("acc-20260101-001", "hecha", "2026-06-16", wiki="true"))
        b = blocks[0]
        self.assertEqual(b.estado, "hecha")
        self.assertEqual(b.cerrado, date(2026, 6, 16))
        self.assertTrue(b.pendiente_wiki)


class PlanTests(unittest.TestCase):
    def test_plan(self) -> None:
        _, blocks = acc.parse_ledger(LEDGER)
        plan = acc.plan_archive(blocks, today=TODAY, retention_days=14)
        self.assertEqual(sorted(plan.moves), ["2026-06", "2026-08"])
        self.assertEqual([b.is_update for b in plan.moves["2026-06"]], [False, True, False])
        self.assertEqual(plan.moved_count, 4)
        self.assertEqual(plan.kept, 9)
        self.assertEqual(plan.skipped["encabezado-irregular"], ["acc-20260110-001 al 005"])
        self.assertEqual(plan.skipped["pendiente-wiki"], ["acc-20260106-001"])
        self.assertEqual(plan.skipped["sin-cerrado"], ["acc-20260107-001"])
        self.assertEqual(plan.skipped["id-duplicado"], ["acc-20260108-001"])
        self.assertEqual(plan.skipped["update-huerfano"], ["acc-20260109-001"])

    def test_retention_window(self) -> None:
        _, blocks = acc.parse_ledger(LEDGER)
        plan = acc.plan_archive(blocks, today=TODAY, retention_days=3)
        self.assertIn("2026-09", plan.moves)  # 2026-09-15 is now older than the window


class ArchiveTests(LedgerFixture):
    def test_plan_mode_writes_nothing(self) -> None:
        acc.archive_actions(apply=False, today=TODAY)
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), LEDGER)
        self.assertFalse((self.mem / "acciones").exists())

    def test_apply_is_lossless_and_idempotent(self) -> None:
        before = self.all_digests()
        plan, stats = acc.archive_actions(apply=True, today=TODAY)
        self.assertEqual(plan.moved_count, 4)
        self.assertLess(stats["bytes_after"], stats["bytes_before"])
        self.assertEqual(self.all_digests(), before)
        self.assertTrue((self.mem / "acciones" / "archivo" / "2026-06.md").is_file())
        plan2, _ = acc.archive_actions(apply=True, today=TODAY)
        self.assertEqual(plan2.moved_count, 0)
        self.assertEqual(self.all_digests(), before)

    def test_apply_merges_into_existing_archive(self) -> None:
        arch = self.mem / "acciones" / "archivo"
        arch.mkdir(parents=True)
        (arch / "2026-08.md").write_text(
            "# Acciones — archivo 2026-08\n\n" + entry("acc-20260801-001", "hecha", "2026-08-02"),
            encoding="utf-8",
        )
        before = self.all_digests()
        acc.archive_actions(apply=True, today=TODAY)
        self.assertEqual(self.all_digests(), before)
        ids = [b.acc_id for b in acc.parse_ledger((arch / "2026-08.md").read_text(encoding="utf-8"))[1]]
        self.assertEqual(ids, ["acc-20260801-001", "acc-20260102-001"])

    def test_conflicting_archive_aborts_without_touching_active(self) -> None:
        arch = self.mem / "acciones" / "archivo"
        arch.mkdir(parents=True)
        (arch / "2026-08.md").write_text(
            "# x\n\n" + entry("acc-20260102-001", "cancelada", "2026-08-30"), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            acc.archive_actions(apply=True, today=TODAY)
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), LEDGER)


class ShowFoldTests(LedgerFixture):
    def test_show_active_then_archive(self) -> None:
        acc.archive_actions(apply=True, today=TODAY)
        self.assertEqual(acc.show_action("acc-20260104-001")[0][0], "acciones.md")
        loc = acc.show_action("acc-20260102-001")[0][0]
        self.assertEqual(loc, "acciones/archivo/2026-08.md")
        with self.assertRaises(LookupError):
            acc.show_action("acc-19990101-001")

    def test_fold_on_archived_says_so(self) -> None:
        acc.archive_actions(apply=True, today=TODAY)
        with self.assertRaisesRegex(ValueError, "archivada"):
            acc.fold_action("acc-20260102-001", "manual:x")

    def test_fold_still_works_on_active(self) -> None:
        msg = acc.fold_action("acc-20260104-001", "manual:x", cerrado="2026-09-21")
        self.assertIn("hecha", msg)
        self.assertIn("- estado: hecha", self.ledger.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
