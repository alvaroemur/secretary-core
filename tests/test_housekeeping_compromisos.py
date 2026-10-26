"""Tests de `playbooks/housekeeping/compromisos.py` (A-reglas y CMP-3)."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "compromisos", Path(__file__).resolve().parents[1] / "playbooks/housekeeping/compromisos.py"
)
compromisos = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(compromisos)

HOY = date(2026, 10, 26)


def bloque(acc, proyecto, deadline, detectado, tipo="compromiso", dueño="mía", estado="abierta",
           origen="extractors/meetings/summaries/2026-01-01-x.md"):
    return f"""## {acc}
- titulo: algo
- tipo: {tipo}
- dueño: {dueño}
- estado: {estado}
- proyecto: {proyecto}
- deadline: {deadline}
- origen: {origen}
- detectado: {detectado}

"""


@pytest.fixture
def summaries(tmp_path):
    d = tmp_path / "summaries"
    d.mkdir()
    (d / "2026-10-20-reunion-activo.md").write_text("x", encoding="utf-8")
    (d / "2026-09-01-reunion-vieja.md").write_text("x", encoding="utf-8")
    return d


def ids(rows):
    return [r["acc"] for r in rows]


def test_caduca_vencida_y_quieta_sin_reunion(summaries):
    text = bloque("acc-20260601-001", "quieto", "2026-06-10", "2026-06-01")
    out = compromisos.clasificar(text, summaries, HOY, set())
    assert ids(out["aplicar"]) == ["acc-20260601-001"]
    assert out["aplicar"][0]["evidencia"] == "manual:housekeeping-caducidad-30d"


def test_sin_ventana_de_detectado(summaries):
    # Antes solo entraban los últimos 45 días de `detectado`; ahora entra todo el ledger.
    text = bloque("acc-20250101-001", "quieto", "2025-01-10", "2025-01-01")
    out = compromisos.clasificar(text, summaries, HOY, set())
    assert ids(out["aplicar"]) == ["acc-20250101-001"]


def test_proyecto_con_reunion_reciente_solo_propone(summaries):
    text = bloque("acc-20260601-001", "activo", "2026-06-10", "2026-06-01") + bloque(
        "acc-20261020-001", "activo", "2026-11-30", "2026-10-20",
        origen="extractors/meetings/summaries/2026-10-20-reunion-activo.md",
    )
    out = compromisos.clasificar(text, summaries, HOY, set())
    assert out["aplicar"] == []
    assert ids(out["proponer"]) == ["acc-20260601-001"]
    assert out["proyectos_con_reunion"] == {"activo": "2026-10-20"}


def test_reunion_vieja_no_protege(summaries):
    text = bloque("acc-20260601-001", "viejo", "2026-06-10", "2026-06-01") + bloque(
        "acc-20260901-001", "viejo", "2026-11-30", "2026-09-01",
        origen="extractors/meetings/summaries/2026-09-01-reunion-vieja.md",
    )
    out = compromisos.clasificar(text, summaries, HOY, set())
    assert ids(out["aplicar"]) == ["acc-20260601-001"]


def test_movimiento_reciente_no_caduca(summaries):
    text = bloque("acc-20260601-001", "quieto", "2026-06-10", "2026-06-01") + """## acc-20260601-001 [update]
- estado_nuevo: en-curso
- detectado: 2026-10-10

"""
    out = compromisos.clasificar(text, summaries, HOY, set())
    assert out["aplicar"] == []
    assert out["proponer"][0]["regla"] == "vencida-14d"


def test_proyecto_terminado_cancela(summaries):
    text = bloque("acc-20261020-002", "cerrado", "2026-12-01", "2026-10-20")
    out = compromisos.clasificar(text, summaries, HOY, {"cerrado"})
    assert out["aplicar"][0]["estado"] == "cancelada"


def test_ignora_cerradas_y_de_terceros(summaries):
    text = bloque("acc-20260601-001", "q", "2026-06-10", "2026-06-01", estado="hecha") + bloque(
        "acc-20260601-002", "q", "2026-06-10", "2026-06-01", dueño="tercero"
    ) + bloque("acc-20260601-003", "q", "2026-06-10", "2026-06-01") + """## acc-20260601-003 [update]
- estado_nuevo: cancelada
- detectado: 2026-06-20

"""
    out = compromisos.clasificar(text, summaries, HOY, set())
    assert out["aplicar"] == [] and out["proponer"] == []
