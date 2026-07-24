"""Load instance config and resolve paths from `.secretary.yml`."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_INSTANCE = Path.home() / ".secretary"
DEFAULT_CORE = Path.home() / "Dev" / "secretary-core"


def expand_path(value: str | Path) -> Path:
    return Path(os.path.expanduser(str(value))).resolve()


def instance_root() -> Path:
    return expand_path(os.environ.get("SECRETARY_INSTANCE", DEFAULT_INSTANCE))


def core_root() -> Path:
    env = os.environ.get("SECRETARY_CORE")
    if env:
        return expand_path(env)
    cfg = instance_root() / ".secretary.yml"
    if cfg.is_file():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        if core := data.get("core_path"):
            return expand_path(core)
    return DEFAULT_CORE.resolve()


def load_config() -> dict[str, Any]:
    path = instance_root() / ".secretary.yml"
    if not path.is_file():
        raise FileNotFoundError(f"No existe {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def flatten_paths(node: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested `paths` dict to dotted keys → relative path strings."""
    out: dict[str, str] = {}
    for key, value in node.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten_paths(value, full))
        elif isinstance(value, str):
            out[full] = value
    return out


def resolve_path_key(key: str, config: dict[str, Any] | None = None) -> Path:
    """Resolve a dotted path key (e.g. `mail.memory`) to an absolute path."""
    cfg = config if config is not None else load_config()
    paths = cfg.get("paths")
    if not isinstance(paths, dict):
        raise KeyError("`.secretary.yml` no tiene sección `paths`")

    flat = flatten_paths(paths)
    if key not in flat:
        raise KeyError(f"Clave de path desconocida: {key!r}")

    return (instance_root() / flat[key]).resolve()


def all_resolved_paths(config: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = config if config is not None else load_config()
    paths = cfg.get("paths", {})
    if not isinstance(paths, dict):
        return {}
    return {k: (instance_root() / v).resolve() for k, v in flatten_paths(paths).items()}


def dispatch_executor_repos(config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """`dispatch.executor.repos` entries with `path` expanded to an absolute string."""
    cfg = config if config is not None else load_config()
    dispatch = cfg.get("dispatch") or {}
    executor = dispatch.get("executor") or {}
    repos = executor.get("repos") or []
    return [
        {"repo": entry["repo"], "path": str(expand_path(entry["path"]))}
        for entry in repos
        if entry.get("repo") and entry.get("path")
    ]


def locate_host(
    cwd: str | Path | None = None, config: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """Match `cwd` (default: process cwd) against `dispatch.executor.repos`.

    Returns every matching entry (`cwd` equal to or nested under `path`), most
    specific (deepest `path`) first — mirrors the old sec-drone bash loop but
    resolves ties deterministically instead of taking whatever `jq` iterated last.
    """
    target = expand_path(cwd) if cwd is not None else Path.cwd().resolve()
    matches = []
    for entry in dispatch_executor_repos(config):
        repo_path = Path(entry["path"])
        if target == repo_path or repo_path in target.parents:
            matches.append(entry)
    matches.sort(key=lambda e: len(e["path"]), reverse=True)
    return matches


def config_show_dict(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Subset of config relevant to CLI consumers."""
    cfg = config if config is not None else load_config()
    inst = instance_root()
    flat = flatten_paths(cfg.get("paths", {}))
    return {
        "instance": str(inst),
        "core": str(core_root()),
        "core_path": cfg.get("core_path"),
        "timezone": cfg.get("timezone", "UTC"),
        "brief": cfg.get("brief"),
        "accounts": cfg.get("accounts"),
        "account_usage": cfg.get("account_usage"),
        "paths": {k: str((inst / v).resolve()) for k, v in flat.items()},
        "dispatch": cfg.get("dispatch"),
    }
