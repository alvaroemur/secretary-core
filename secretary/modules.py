"""Module contract registry and health — spec 015 phase 3."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from secretary.config import instance_root

EXTRACTOR_MODULES = ("mail", "whatsapp", "meetings", "drive")
LOOP_MODULES = ("job-search",)


def _contract_health_script() -> Path:
    return instance_root() / "scripts" / "ci" / "contract_health.py"


def module_contract_path(module_id: str) -> Path | None:
    """Resolve contract.yaml for an extractor or loop module id."""
    inst = instance_root()
    for plane, names in (("extractors", EXTRACTOR_MODULES), ("loops", LOOP_MODULES)):
        if module_id in names:
            return inst / plane / module_id / "contract.yaml"
    return None


def list_modules() -> list[dict[str, Any]]:
    """List extractors and loops with merged contract.yaml metadata."""
    out: list[dict[str, Any]] = []
    inst = instance_root()
    for plane, names in (("extractors", EXTRACTOR_MODULES), ("loops", LOOP_MODULES)):
        for name in names:
            path = inst / plane / name / "contract.yaml"
            entry: dict[str, Any] = {
                "id": name,
                "plane": plane.rstrip("s"),
                "path": str(path.relative_to(inst)),
            }
            if path.is_file():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if isinstance(data, dict):
                    entry["kind"] = data.get("kind")
                    entry["routine"] = data.get("routine")
                    if plane == "loops":
                        goal = data.get("goal") or {}
                        if isinstance(goal, dict):
                            entry["goal_title"] = goal.get("title")
                        entry["objective_ref"] = data.get("objective_ref")
            else:
                entry["missing_contract"] = True
            out.append(entry)
    return out


def load_contract(module_id: str) -> dict[str, Any]:
    path = module_contract_path(module_id)
    if path is None:
        raise KeyError(f"Módulo desconocido: {module_id!r}")
    if not path.is_file():
        raise FileNotFoundError(f"No existe {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"contract.yaml inválido: {path}")
    return data


def save_contract(module_id: str, contract: dict[str, Any]) -> Path:
    path = module_contract_path(module_id)
    if path is None:
        raise KeyError(f"Módulo desconocido: {module_id!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(contract, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return path


def merge_contract(module_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge patch into existing contract (admin PUT)."""
    current = load_contract(module_id)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(current.get(key), dict):
            merged = dict(current[key])
            merged.update(value)
            current[key] = merged
        else:
            current[key] = value
    save_contract(module_id, current)
    return current


def health_rows(module_id: str | None = None) -> list[dict[str, Any]]:
    """Delegate to instance contract_health.py for computed health."""
    script = _contract_health_script()
    if not script.is_file():
        raise FileNotFoundError(f"No existe {script}")
    proc = subprocess.run(
        [sys.executable, str(script), "--format", "json"],
        cwd=str(instance_root()),
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr.strip() or "contract_health falló")
    rows = json.loads(proc.stdout)
    if module_id:
        rows = [r for r in rows if r.get("module") == module_id]
    return rows


def health_for_module(module_id: str) -> dict[str, Any]:
    rows = health_rows(module_id)
    if not rows:
        raise KeyError(f"Sin filas de salud para {module_id!r}")
    order = ("ok", "warn", "paused", "behind", "stale", "unknown")

    def rank(health: str) -> int:
        return order.index(health) if health in order else len(order) - 1

    worst = max((str(r.get("health") or "unknown") for r in rows), key=rank)
    criteria = [
        {
            "id": r.get("module"),
            "kind": r.get("kind"),
            "health": r.get("health"),
            "gap": r.get("gap"),
            "ok": r.get("health") == "ok",
        }
        for r in rows
    ]
    return {
        "module": module_id,
        "freshness_ok": worst in ("ok", "warn", "paused"),
        "health": worst,
        "criteria": criteria,
    }
