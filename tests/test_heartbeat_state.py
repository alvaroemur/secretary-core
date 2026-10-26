"""heartbeat_state.build_match: correspondencia acc ↔ git del latido, sin red ni git."""

from __future__ import annotations

import importlib.util
import re
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

_PATH = Path(__file__).resolve().parents[1] / "secretary" / "routines" / "ops" / "heartbeat_state.py"
_spec = importlib.util.spec_from_file_location("heartbeat_state", _PATH)
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)

# Fecha fija en una zona horaria que no es la local de ninguna instancia de prueba.
TODAY = datetime(2030, 1, 15, 9, 0, tzinfo=ZoneInfo("Pacific/Auckland")).date()
LEDGER = "extractors/meetings/memory/acciones.md"


def acc(estado: str = "abierta", dueno: str = "mía", deadline: str | None = None, workspace: str = "demo") -> dict:
    fields = {"accion": "Acción de prueba", "dueño": dueno, "workspace": workspace}
    if deadline:
        fields["deadline"] = deadline
    return {"ledger": LEDGER, "estado": estado, "fields": fields}


def pr(number: int, head: str = "feat/x", title: str = "Cambio", body: str = "") -> dict:
    return {"number": number, "headRefName": head, "title": title, "body": body,
            "url": f"https://example.invalid/pull/{number}", "isDraft": False}


def inv(prs: list[dict] | None = None, branches: list[str] | None = None) -> dict:
    return {"repo": "owner/demo-repo", "prs": prs or [], "branches": branches or []}


def rows_by(rows: list[dict], match: str) -> list[dict]:
    return [r for r in rows if r["match"] == match]


def iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


class LinkedTest(unittest.TestCase):
    def test_linked_with_literal_id_in_branch(self) -> None:
        open_a = {"acc-20300101-001": acc()}
        rows, _ = hs.build_match([inv(branches=["feat/acc-20300101-001-ajuste"])], open_a, {}, TODAY)
        linked = rows_by(rows, "🔗 linked")
        self.assertEqual([r["acc"] for r in linked], ["acc-20300101-001"])
        self.assertIn("rama `feat/acc-20300101-001-ajuste`", linked[0]["ref"])

    def test_linked_with_literal_id_in_pr_body(self) -> None:
        open_a = {"acc-20300101-002": acc()}
        rows, _ = hs.build_match([inv([pr(7, body="Cierra acc-20300101-002.")])], open_a, {}, TODAY)
        self.assertEqual([r["acc"] for r in rows_by(rows, "🔗 linked")], ["acc-20300101-002"])
        self.assertEqual(rows_by(rows, "🌿 loose-git"), [])

    def test_non_literal_mention_is_not_linked(self) -> None:
        # Mención sin el acc-id literal (formato distinto o solo el workspace): no hay linked.
        open_a = {"acc-20300101-003": acc(deadline=iso(1))}
        rows, _ = hs.build_match(
            [inv([pr(8, head="demo/ajuste", body="Relacionado con acc 20300101-003")])], open_a, {}, TODAY)
        self.assertEqual(rows_by(rows, "🔗 linked"), [])
        self.assertEqual([r["acc"] for r in rows_by(rows, "📋 loose-acc")], ["acc-20300101-003"])
        self.assertEqual([r["pr"] for r in rows_by(rows, "🌿 loose-git")], ["owner/demo-repo#8"])

    def test_pr_citing_closed_acc_is_loose_git(self) -> None:
        rows, _ = hs.build_match([inv([pr(9, body="acc-20300101-004")])], {}, {"acc-20300101-004": acc("hecha")}, TODAY)
        (row,) = rows_by(rows, "🌿 loose-git")
        self.assertIn("acc-20300101-004 (cerrada)", row["nota"])

    def test_downgrade_to_loose_acc_when_ref_lacks_literal_id(self) -> None:
        # Red de seguridad: si la extracción devuelve un id que no está literal en la ref,
        # la fila baja a loose-acc y la validación lo reporta.
        class LooseRe:
            def findall(self, text: str) -> list[str]:
                return ["acc-20300101-005"] if "ticket-5" in text else []

        open_a = {"acc-20300101-005": acc()}
        with mock.patch.object(hs, "ACC_RE", LooseRe()):
            rows, validation = hs.build_match([inv([pr(10, head="fix/ticket-5")])], open_a, {}, TODAY)
        self.assertEqual(rows_by(rows, "🔗 linked"), [])
        (row,) = rows_by(rows, "📋 loose-acc")
        self.assertEqual(row["acc"], "acc-20300101-005")
        self.assertIn("bajada desde linked", row["nota"])
        self.assertTrue(any("bajadas a loose-acc: acc-20300101-005" in v for v in validation))
        self.assertTrue(any("0/1" in v for v in validation))


class DuplicatesTest(unittest.TestCase):
    def test_acc_in_several_refs_yields_one_row(self) -> None:
        open_a = {"acc-20300101-006": acc(deadline=iso(0))}
        invs = [inv([pr(11, body="acc-20300101-006"), pr(12, title="acc-20300101-006 parte 2")],
                    branches=["wip/acc-20300101-006"])]
        rows, validation = hs.build_match(invs, open_a, {}, TODAY)
        ids = [r["acc"] for r in rows if r["acc"] != "—"]
        self.assertEqual(ids, ["acc-20300101-006"])
        self.assertIn("PR #11", rows[0]["ref"])
        self.assertIn("PR #12", rows[0]["ref"])
        self.assertTrue(any(re.search(r"duplicados: 0$", v) for v in validation))

    def test_duplicate_rows_are_reported(self) -> None:
        open_a = {"acc-20300101-007": acc()}
        real_sorted = sorted

        def twice(it, *a, **k):  # fuerza dos entradas del mismo acc en linked_refs
            out = real_sorted(it, *a, **k)
            return out + out if out == ["acc-20300101-007"] else out

        with mock.patch.object(hs, "sorted", twice, create=True):
            _, validation = hs.build_match([inv(branches=["x/acc-20300101-007"])], open_a, {}, TODAY)
        self.assertTrue(any("duplicados: acc-20300101-007" in v for v in validation))


class LooseAccWindowTest(unittest.TestCase):
    def test_window_minus_14_plus_7(self) -> None:
        open_a = {
            "acc-20300101-010": acc(deadline=iso(-14)),  # borde inferior: entra
            "acc-20300101-011": acc(deadline=iso(-15)),  # fuera
            "acc-20300101-012": acc(deadline=iso(7)),    # borde superior: entra
            "acc-20300101-013": acc(deadline=iso(8)),    # fuera
            "acc-20300101-014": acc(dueno="compartida", deadline=iso(2)),  # entra
            "acc-20300101-015": acc(dueno="tercero", deadline=iso(2)),     # dueño ajeno: fuera
            "acc-20300101-016": acc(),                                     # sin deadline: fuera
        }
        rows, _ = hs.build_match([inv()], open_a, {}, TODAY)
        self.assertEqual(
            sorted(r["acc"] for r in rows_by(rows, "📋 loose-acc")),
            ["acc-20300101-010", "acc-20300101-012", "acc-20300101-014"],
        )


if __name__ == "__main__":
    unittest.main()
