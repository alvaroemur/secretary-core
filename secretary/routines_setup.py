"""Interactive setup wizard for secretary scheduled routines (api-cron only)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from secretary.config import instance_root

DEFAULT_API_BASE = "https://nano-gpt.com/api/v1"
DEFAULT_API_KEY_ENV = "SECRETARY_ROUTINES_API_KEY"
DEFAULT_MODEL = "minimax/minimax-m2.7"
EXECUTOR = "api-cron"


def _banner(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{text}{suffix}: ").strip()
        if raw:
            return raw
        if default:
            return default
        print("  (required)")


def _prompt_yes_no(text: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{text} ({hint}): ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Enter y or n.")


def _menu_choice(title: str, options: list[str], current: str | None = None) -> str:
    _banner(title)
    for i, opt in enumerate(options, 1):
        mark = " *" if opt == current else ""
        print(f"  {i}. {opt}{mark}")
    print()
    while True:
        raw = input(f"Choice [1-{len(options)}]: ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        print("  Invalid choice.")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _paths(instance: Path) -> dict[str, Path]:
    return {
        "config": instance / ".secretary.yml",
        "manifest": instance / ".cursor/routines/manifest.yaml",
        "env": instance / ".env",
        "env_example": instance / ".env.example",
        "install": instance / "scripts/routines/install-routine-schedule.sh",
    }


def _read_routines_config(instance: Path) -> dict[str, Any]:
    cfg = _load_yaml(_paths(instance)["config"])
    routines = (cfg.get("dispatch") or {}).get("routines") or {}
    api = routines.get("api") or {}
    disabled = routines.get("disabled") or []
    if not isinstance(disabled, list):
        disabled = []
    return {
        "executor": EXECUTOR,
        "model": routines.get("model", DEFAULT_MODEL),
        "api_base_url": api.get("base_url", DEFAULT_API_BASE),
        "api_key_env": api.get("api_key_env", DEFAULT_API_KEY_ENV),
        "disabled": [str(x) for x in disabled],
    }


def _parse_manifest_routines(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        return []
    text = manifest_path.read_text(encoding="utf-8")
    routines: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        m = re.match(r"\s*-\s+id:\s+(\S+)", line)
        if m:
            if current:
                routines.append(current)
            current = {"id": m.group(1), "enabled": True}
            continue
        if current is None:
            continue
        m = re.match(r'\s+name:\s+"([^"]+)"', line)
        if m:
            current["name"] = m.group(1)
            continue
        m = re.match(r'\s+cron:\s+"([^"]+)"', line)
        if m:
            current["cron"] = m.group(1)
            continue
        m = re.match(r"\s+enabled:\s+(true|false)", line, re.I)
        if m:
            current["enabled"] = m.group(1).lower() == "true"
    if current:
        routines.append(current)
    return routines


def _effective_enabled(routine: dict[str, Any], disabled_ids: list[str]) -> bool:
    if routine.get("enabled") is False:
        return False
    return routine["id"] not in disabled_ids


def _git_fetch_main(instance: Path) -> None:
    if not (instance / ".git").exists():
        print("  Not a git checkout — skipping fetch.")
        return
    print("  Running: git fetch origin main")
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=instance, check=False)
        print("  Fetch complete (merge/pull manually if you want updates on disk).")
    except OSError as exc:
        print(f"  WARN: git fetch failed: {exc}")


def _ensure_env_example(env_example: Path) -> None:
    content = """# General NanoGPT (Cursor, ad-hoc) — optional
# NANOGPT_API_KEY=

# Cron/routines only (api-cron LaunchAgents)
SECRETARY_ROUTINES_API_KEY=
"""
    if not env_example.is_file():
        env_example.write_text(content, encoding="utf-8")
        print(f"  Created {env_example}")


def _env_has_key(env_path: Path, var_name: str) -> bool:
    if not env_path.is_file():
        return False
    prefix = f"{var_name}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith(prefix):
            val = line[len(prefix) :].strip().strip("'\"")
            return bool(val)
    return False


def _preview_dispatch_block(state: dict[str, Any]) -> str:
    block: dict[str, Any] = {
        "executor": EXECUTOR,
        "model": state["model"],
        "api": {
            "base_url": state["api_base_url"],
            "api_key_env": state["api_key_env"],
        },
    }
    disabled = state.get("disabled") or []
    if disabled:
        block["disabled"] = sorted(disabled)
    return yaml.safe_dump({"dispatch": {"routines": block}}, allow_unicode=True, sort_keys=False)


def _merge_write_config(instance: Path, state: dict[str, Any]) -> None:
    config_path = _paths(instance)["config"]
    cfg = _load_yaml(config_path)
    dispatch = cfg.setdefault("dispatch", {})
    routines = dispatch.setdefault("routines", {})

    routines["executor"] = EXECUTOR
    routines["model"] = state["model"]
    routines["api"] = {
        "base_url": state["api_base_url"],
        "api_key_env": state["api_key_env"],
    }

    disabled = state.get("disabled") or []
    if disabled:
        routines["disabled"] = sorted(disabled)
    else:
        routines.pop("disabled", None)

    config_path.write_text(_dump_yaml(cfg), encoding="utf-8")
    print(f"  Wrote {config_path}")


def _run_installer(instance: Path) -> int:
    install = _paths(instance)["install"]
    if not install.is_file():
        print(f"  ERROR: missing {install}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["SECRETARY_INSTANCE"] = str(instance)
    print(f"  Running {install}")
    return subprocess.run(["bash", str(install)], cwd=instance, env=env).returncode


def _reload_launchagents(instance: Path, routine_ids: list[str]) -> None:
    launchd_dir = Path.home() / "Library/LaunchAgents"
    uid = os.getuid()
    domain = f"gui/{uid}"
    for rid in routine_ids:
        label = f"com.alvaromur.secretary.routine.{rid}"
        plist = launchd_dir / f"{label}.plist"
        if not plist.is_file():
            print(f"  skip {rid}: no plist")
            continue
        subprocess.run(["launchctl", "bootout", domain, label], capture_output=True)
        rc = subprocess.run(["launchctl", "bootstrap", domain, str(plist)]).returncode
        status = "ok" if rc == 0 else f"exit {rc}"
        print(f"  {label}: bootstrap {status}")


def _run_verify(instance: Path) -> None:
    for name in ("validate_ordenamiento.py", "contract_health.py"):
        script = instance / "scripts/ci" / name
        if not script.is_file():
            continue
        print(f"  Running {name}...")
        subprocess.run([sys.executable, str(script)], cwd=instance, check=False)


def _step_api(state: dict[str, Any], paths: dict[str, Path]) -> None:
    print("\n  Executor: api-cron (LaunchAgents → HTTP chat completions)")
    state["api_base_url"] = _prompt("API base URL", state.get("api_base_url", DEFAULT_API_BASE))
    state["model"] = _prompt("Model id", state.get("model", DEFAULT_MODEL))
    key_env = state.get("api_key_env", DEFAULT_API_KEY_ENV)
    print(f"\n  API key env var: {key_env} (value never shown)")
    _ensure_env_example(paths["env_example"])
    if not _env_has_key(paths["env"], key_env):
        print(f"\n  WARN: {key_env} is not set in {paths['env']}")
        print(f"  Edit {paths['env']} and add {key_env}=<your-key>")
        print(f"  Copy from {paths['env_example']} if needed.")
        _prompt_yes_no("Continue setup anyway?", default=True)
    else:
        print(f"  OK: {key_env} is set in .env (value not displayed).")


def _step_routines(state: dict[str, Any], manifest_path: Path) -> None:
    routines = _parse_manifest_routines(manifest_path)
    if not routines:
        print(f"  WARN: no routines in {manifest_path}")
        return

    disabled = set(state.get("disabled") or [])
    enabled_map = {r["id"]: _effective_enabled(r, list(disabled)) for r in routines}

    _banner("Routines (from manifest.yaml)")
    for i, r in enumerate(routines, 1):
        cron = r.get("cron", "—")
        en = "on" if enabled_map[r["id"]] else "off"
        name = r.get("name", r["id"])
        print(f"  {i:2}. [{en:3}] {r['id']}")
        print(f"      {name}")
        print(f"      cron: {cron}")

    print()
    action = _menu_choice(
        "Routine enablement",
        [
            "Keep current enabled/disabled",
            "Toggle each routine (y/n)",
            "Enable all",
            "Disable all",
        ],
        current="Keep current enabled/disabled",
    )
    if action == "Toggle each routine (y/n)":
        for r in routines:
            rid = r["id"]
            enabled_map[rid] = _prompt_yes_no(f"Enable {rid}?", default=enabled_map[rid])
    elif action == "Enable all":
        for rid in enabled_map:
            enabled_map[rid] = True
    elif action == "Disable all":
        for rid in enabled_map:
            enabled_map[rid] = False

    state["disabled"] = sorted(rid for rid, on in enabled_map.items() if not on)


def run_setup() -> int:
    """Interactive TUI wizard for api-cron routines setup."""
    instance = instance_root()
    paths = _paths(instance)

    print("Secretary routines setup")
    print(f"  Instance: {instance}")
    print("  Executor: api-cron (only supported mode)")

    if not paths["config"].is_file():
        print(f"  ERROR: missing {paths['config']}", file=sys.stderr)
        return 1

    current = _read_routines_config(instance)
    state: dict[str, Any] = dict(current)

    mode = _menu_choice("Setup mode", ["New setup", "Update existing"])
    if mode == "Update existing" and _prompt_yes_no("Git fetch origin main?", default=False):
        _git_fetch_main(instance)

    _step_api(state, paths)
    _step_routines(state, paths["manifest"])

    _banner("Preview — dispatch.routines")
    print(_preview_dispatch_block(state))

    if not _prompt_yes_no("\nApply these changes?", default=True):
        print("Aborted.")
        return 0

    _merge_write_config(instance, state)
    _ensure_env_example(paths["env_example"])

    rc = _run_installer(instance)
    if rc != 0:
        print(f"  Installer exited {rc}", file=sys.stderr)
        return rc

    routines = _parse_manifest_routines(paths["manifest"])
    active_ids = [
        r["id"]
        for r in routines
        if r.get("cron") and r["id"] not in (state.get("disabled") or [])
    ]

    if _prompt_yes_no("Reload LaunchAgents (bootout + bootstrap)?", default=True):
        _reload_launchagents(instance, active_ids)

    print("\n  Note: disable Claude Code scheduled-tasks if still enabled (avoid duplicate runs).")

    if _prompt_yes_no("\nRun validators (validate_ordenamiento / contract_health)?", default=True):
        _run_verify(instance)

    print("\nDone. Smoke test:")
    print(f"  SECRETARY_INSTANCE={instance} {instance}/scripts/routines/run-routine.sh sec-heartbeat")
    return 0
