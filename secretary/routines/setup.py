"""Interactive wizard for secretary routines router and LaunchAgent schedule."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from secretary.config import instance_root

EXECUTORS = ("claude-scheduled", "cursor-cron", "api-cron")
DEFAULT_API_BASE = "https://nano-gpt.com/api/v1"
DEFAULT_API_KEY_ENV = "SECRETARY_ROUTINES_API_KEY"
DEFAULT_MODEL_API = "minimax/minimax-m2.7"
DEFAULT_MODEL_CURSOR = "auto"


def _paths() -> dict[str, Path]:
    inst = instance_root()
    return {
        "instance": inst,
        "config": inst / ".secretary.yml",
        "manifest": inst / ".cursor/routines/manifest.yaml",
        "env": inst / ".env",
        "env_example": inst / ".env.example",
        "install_script": inst / "scripts/routines/install-routine-schedule.sh",
        "launchd_dir": Path.home() / "Library/LaunchAgents",
    }


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


def _read_routines_config(config_path: Path) -> dict[str, Any]:
    cfg = _load_yaml(config_path)
    routines = (cfg.get("dispatch") or {}).get("routines") or {}
    api = routines.get("api") or {}
    disabled = routines.get("disabled") or []
    if not isinstance(disabled, list):
        disabled = []
    return {
        "executor": routines.get("executor", "cursor-cron"),
        "model": routines.get("model", DEFAULT_MODEL_CURSOR),
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


def _ensure_env_example(env_example_path: Path) -> None:
    content = """# General NanoGPT (Cursor, ad-hoc) — optional
# NANOGPT_API_KEY=

# Cron/routines only (api-cron LaunchAgents)
SECRETARY_ROUTINES_API_KEY=
"""
    if not env_example_path.is_file():
        env_example_path.write_text(content, encoding="utf-8")
        print(f"  Created {env_example_path}")


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
        "executor": state["executor"],
        "model": state["model"],
    }
    if state["executor"] == "api-cron":
        block["api"] = {
            "base_url": state["api_base_url"],
            "api_key_env": state["api_key_env"],
        }
    disabled = state.get("disabled") or []
    if disabled:
        block["disabled"] = sorted(disabled)
    return yaml.safe_dump({"dispatch": {"routines": block}}, allow_unicode=True, sort_keys=False)


def _merge_write_config(config_path: Path, state: dict[str, Any]) -> None:
    cfg = _load_yaml(config_path)
    dispatch = cfg.setdefault("dispatch", {})
    routines = dispatch.setdefault("routines", {})

    routines["executor"] = state["executor"]
    routines["model"] = state["model"]

    if state["executor"] == "api-cron":
        routines["api"] = {
            "base_url": state["api_base_url"],
            "api_key_env": state["api_key_env"],
        }
    else:
        routines.pop("api", None)

    disabled = state.get("disabled") or []
    if disabled:
        routines["disabled"] = sorted(disabled)
    else:
        routines.pop("disabled", None)

    config_path.write_text(_dump_yaml(cfg), encoding="utf-8")
    print(f"  Wrote {config_path}")


def _run_installer(install_script: Path, instance: Path) -> int:
    if not install_script.is_file():
        print(f"  ERROR: missing {install_script}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["SECRETARY_INSTANCE"] = str(instance)
    print(f"  Running {install_script}")
    result = subprocess.run(["bash", str(install_script)], cwd=instance, env=env)
    return result.returncode


def _reload_launchagents(
    routine_ids: list[str], executor: str, launchd_dir: Path
) -> None:
    if executor == "claude-scheduled":
        print("  claude-scheduled — no LaunchAgents to reload.")
        return
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
    validators = [
        instance / "scripts/ci/validate_ordenamiento.py",
        instance / "scripts/ci/contract_health.py",
    ]
    for script in validators:
        if not script.is_file():
            continue
        print(f"  Running {script.name}...")
        subprocess.run([sys.executable, str(script)], cwd=instance, check=False)


def _step_mode() -> str:
    return _menu_choice("Setup mode", ["New setup", "Update existing"])


def _step_fetch(mode: str, instance: Path) -> None:
    if mode == "Update existing" and _prompt_yes_no("Git fetch origin main?", default=False):
        _git_fetch_main(instance)


def _step_executor(current: dict[str, Any]) -> str:
    cur = current["executor"]
    print(f"\n  Current executor: {cur}")
    return _menu_choice("Routines executor (router)", list(EXECUTORS), current=cur)


def _step_executor_options(state: dict[str, Any], paths: dict[str, Path]) -> None:
    executor = state["executor"]
    if executor == "api-cron":
        state["api_base_url"] = _prompt(
            "API base URL", state.get("api_base_url", DEFAULT_API_BASE)
        )
        state["model"] = _prompt("Model id", state.get("model", DEFAULT_MODEL_API))
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
    elif executor == "cursor-cron":
        state["model"] = _prompt(
            "Model for Cursor agent", state.get("model", DEFAULT_MODEL_CURSOR)
        )
    elif executor == "claude-scheduled":
        print("\n  claude-scheduled uses Claude Code MCP scheduled-tasks (cloud).")
        print("  Disable local LaunchAgents and other routers to avoid duplicate runs.")
        print("  Enable each routine playbook in Claude Code scheduled-tasks UI / MCP.")


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


def _mcp_note(executor: str) -> None:
    if executor == "claude-scheduled":
        print("\n  MCP: Enable Claude Code scheduled-tasks for each routine playbook.")
        print("  Disable LaunchAgents / other routers to avoid duplicate runs.")
    else:
        print("\n  MCP: Disable Claude Code scheduled-tasks (UI / MCP list)")
        print("  to avoid duplicate PRs while using local LaunchAgents.")


def run_setup() -> int:
    """Run the interactive routines setup wizard."""
    paths = _paths()
    instance = paths["instance"]
    config_path = paths["config"]

    print("Secretary routines setup")
    print(f"  Instance: {instance}")

    if not config_path.is_file():
        print(f"  ERROR: missing {config_path}", file=sys.stderr)
        return 1

    current = _read_routines_config(config_path)
    state: dict[str, Any] = dict(current)

    mode = _step_mode()
    _step_fetch(mode, instance)

    state["executor"] = _step_executor(current)
    _step_executor_options(state, paths)
    _step_routines(state, paths["manifest"])

    _banner("Preview — dispatch.routines")
    print(_preview_dispatch_block(state))

    if not _prompt_yes_no("\nApply these changes?", default=True):
        print("Aborted.")
        return 0

    _merge_write_config(config_path, state)
    _ensure_env_example(paths["env_example"])

    rc = _run_installer(paths["install_script"], instance)
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
        _reload_launchagents(active_ids, state["executor"], paths["launchd_dir"])

    _mcp_note(state["executor"])

    if _prompt_yes_no("\nRun validators (validate_ordenamiento / contract_health)?", default=True):
        _run_verify(instance)

    print("\nDone. Smoke test:")
    print(f"  SECRETARY_INSTANCE={instance} {instance}/scripts/routines/run-routine.sh sec-heartbeat")
    return 0
