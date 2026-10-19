"""Tests de `secretary acc fold` (idempotencia y guardas de estado)."""

from __future__ import annotations

import pytest

from secretary.acc import fold_action

ACC = "acc-20260101-001"

ENTRADA = """# Acciones

## {acc}
- descripcion: algo por hacer
- estado: {estado}
"""


@pytest.fixture
def instancia(tmp_path, monkeypatch):
    (tmp_path / ".secretary.yml").write_text(
        "paths:\n  meetings:\n    memory: extractors/meetings/memory\n",
        encoding="utf-8",
    )
    mem = tmp_path / "extractors" / "meetings" / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setenv("SECRETARY_INSTANCE", str(tmp_path))
    monkeypatch.delenv("SEC_ACC_ESTADO", raising=False)

    def crear(estado: str):
        f = mem / "acciones.md"
        f.write_text(ENTRADA.format(acc=ACC, estado=estado), encoding="utf-8")
        return f

    return crear


def test_primera_llamada_aplica(instancia):
    f = instancia("abierta")
    msg = fold_action(ACC, "pr:o/r#1", cerrado="2026-02-01")
    texto = f.read_text(encoding="utf-8")
    assert msg.startswith(f"✓ {ACC} → hecha")
    assert "- estado: hecha" in texto
    assert "- cerrado: 2026-02-01" in texto
    assert texto.count("[update]") == 1


def test_segunda_llamada_no_duplica(instancia):
    f = instancia("abierta")
    fold_action(ACC, "pr:o/r#1", cerrado="2026-02-01")
    antes = f.read_text(encoding="utf-8")
    msg = fold_action(ACC, "pr:o/r#2", cerrado="2026-03-01")
    assert msg == f"= {ACC} ya estaba en hecha (sin cambios)"
    assert f.read_text(encoding="utf-8") == antes
    assert antes.count("[update]") == 1


def test_cierre_con_otro_estado_falla(instancia, monkeypatch):
    f = instancia("caducada")
    antes = f.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="ya está cerrada como caducada"):
        fold_action(ACC, "pr:o/r#1")
    assert f.read_text(encoding="utf-8") == antes


@pytest.mark.parametrize("estado", ["abierta", "en-curso", "pendiente"])
def test_abierta_se_cierra(instancia, monkeypatch, estado):
    f = instancia(estado)
    monkeypatch.setenv("SEC_ACC_ESTADO", "cancelada")
    fold_action(ACC, "nota", cerrado="2026-02-01")
    texto = f.read_text(encoding="utf-8")
    assert "- estado: cancelada" in texto
    assert texto.count("[update]") == 1
