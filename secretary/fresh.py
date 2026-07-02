"""Fresh-first Paso 0 — extractor freshness for sec-* skills."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from secretary.config import instance_root, load_config, resolve_path_key

TZ = ZoneInfo("America/Lima")
DEFAULT_REPO = "alvaroemur/cowork-secretary"
TACTIQ_ROOT = "1TE6Z1uhZo7YrwOnWvp83se3CCXHiCKt9"

MODULE_ALIASES = {"reuniones": "meeting"}

MODULE_PREFIX = {
    "mail": "correo",
    "meeting": "reuniones",
    "drive": "drive",
    "whatsapp": "whatsapp",
}

ALL_MODULES = ("mail", "meeting", "drive", "whatsapp")

# Dotted keys in `.secretary.yml` → paths (spec 012 / skills-contract).
_MODULE_MEMORY_KEY = {
    "mail": "mail.memory",
    "meeting": "meetings.memory",
    "drive": "drive.memory",
    "whatsapp": "whatsapp.memory",
}
_MODULE_STATE_KEY = {
    "mail": "mail.state",
    "drive": "drive.state",
    "whatsapp": "whatsapp.state",
}
_MEETINGS_SUMMARIES_KEY = "meetings.summaries"


def _rel_path(key: str) -> str:
    """Resolve a config path key to a repo-relative path string."""
    return resolve_path_key(key).relative_to(instance_root()).as_posix()


def _module_dir(module: str) -> str:
    """Repo-relative extractor module directory (trailing slash for git log)."""
    root = resolve_path_key(_MODULE_MEMORY_KEY[module]).parent
    return root.relative_to(instance_root()).as_posix() + "/"


def _procesados_jsonl(module: str) -> str:
    memory = Path(_rel_path(_MODULE_MEMORY_KEY[module]))
    return (memory / "_procesados.jsonl").as_posix()


@dataclass
class FreshReport:
    module: str
    main: dict[str, Any] = field(default_factory=dict)
    working: dict[str, Any] | None = None
    auto_pr: list[dict[str, Any]] = field(default_factory=list)
    fuente_viva: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _gh_repo() -> str:
    cfg = load_config()
    inst = str(instance_root())
    repos = (cfg.get("dispatch") or {}).get("executor", {}).get("repos", [])
    for entry in repos:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path", "")).replace("~", str(Path.home()))
        if Path(path).resolve() == instance_root():
            return entry.get("repo", DEFAULT_REPO)
    return DEFAULT_REPO


def _personal_account() -> str:
    accounts = load_config().get("accounts") or {}
    return accounts.get("personal", "alvaro.e.mur@gmail.com")


def git_fetch() -> None:
    inst = instance_root()
    _run(["git", "-C", str(inst), "fetch", "origin", "-q"])


def git_show_main(rel_path: str) -> str | None:
    inst = instance_root()
    r = _run(["git", "-C", str(inst), "show", f"origin/main:{rel_path}"])
    if r.returncode != 0:
        return None
    return r.stdout


def git_log_main(path: str) -> dict[str, str] | None:
    inst = instance_root()
    r = _run(
        [
            "git",
            "-C",
            str(inst),
            "log",
            "-1",
            "--format=%ci\t%s",
            "origin/main",
            "--",
            path,
        ]
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    ts, subj = r.stdout.strip().split("\t", 1)
    return {"timestamp": _format_git_ts(ts), "subject": subj}


def git_local_diff(rel_path: str) -> dict[str, Any] | None:
    inst = instance_root()
    local = inst / rel_path
    if not local.is_file():
        return {"status": "missing_local"}
    r = _run(["git", "-C", str(inst), "diff", "--name-only", f"origin/main:{rel_path}", rel_path])
    changed = bool(r.stdout.strip())
    main_blob = git_show_main(rel_path)
    local_text = local.read_text(encoding="utf-8", errors="replace")
    return {
        "status": "modified" if changed else "same",
        "local_mtime": datetime.fromtimestamp(local.stat().st_mtime, TZ).strftime("%Y-%m-%d %H:%M %Z"),
        "differs_from_main": changed or (main_blob is not None and main_blob != local_text),
    }


def _format_git_ts(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return raw
    for fmt in ("%Y-%m-%d %H:%M:%S %z",):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M Lima")
        except ValueError:
            pass
    return raw


def _parse_estado_date(text: str, label: str = "Última actualización:") -> str | None:
    for line in text.splitlines():
        if label in line:
            return line.split(":", 1)[-1].strip()
    return None


def list_auto_prs(prefix: str) -> list[dict[str, Any]]:
    repo = _gh_repo()
    if not shutil.which("gh"):
        return []
    r = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number,headRefName,title",
        ]
    )
    if r.returncode != 0:
        return []
    try:
        prs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []
    pat = re.compile(rf"^{re.escape(prefix)}/auto-")
    out: list[dict[str, Any]] = []
    inst = instance_root()
    for pr in prs:
        branch = pr.get("headRefName", "")
        if not pat.match(branch):
            continue
        files = _pr_extractor_files(branch)
        out.append(
            {
                "number": pr.get("number"),
                "branch": branch,
                "title": pr.get("title"),
                "files": files,
            }
        )
    return out


def _pr_extractor_files(branch: str) -> list[str]:
    inst = instance_root()
    r = _run(
        [
            "git",
            "-C",
            str(inst),
            "diff",
            "--name-only",
            f"origin/main...origin/{branch}",
        ]
    )
    if r.returncode != 0:
        return []
    return [ln for ln in r.stdout.splitlines() if ln.startswith("extractors/")]


def _gog_available() -> bool:
    return shutil.which("gog") is not None


def _mail_fuente_viva() -> dict[str, Any]:
    out: dict[str, Any] = {"gog_available": _gog_available()}
    state_path = _rel_path(_MODULE_STATE_KEY["mail"])
    main_text = git_show_main(state_path)
    if main_text:
        out["estado_md_date"] = _parse_estado_date(main_text)
    if not out["gog_available"]:
        out["note"] = "gog no disponible"
        return out
    acc = _personal_account()
    r = _run(
        [
            "gog",
            "gmail",
            "search",
            "newer_than:1d -in:chats",
            "--max",
            "1",
            "--plain",
            "--no-input",
            "--account",
            acc,
        ]
    )
    if r.returncode != 0:
        out["gog_error"] = (r.stderr or r.stdout or "error").strip()[:200]
        return out
    lines = [ln for ln in (r.stdout or "").strip().splitlines() if ln and not ln.startswith("#")]
    if not lines:
        return out
    # gog --plain: header ID\tDATE\tFROM\tSUBJECT… then data rows
    if lines[0].startswith("ID\t"):
        lines = lines[1:]
    if not lines:
        return out
    line = lines[0]
    out["latest_email"] = {"raw": line}
    parts = line.split("\t")
    if len(parts) >= 4:
        out["latest_email"] = {
            "id": parts[0].strip(),
            "date": parts[1].strip(),
            "from": parts[2].strip(),
            "subject": parts[3].strip(),
        }
    elif len(parts) >= 3:
        out["latest_email"] = {
            "date": parts[0].strip(),
            "from": parts[1].strip(),
            "subject": parts[2].strip(),
        }
    return out


def _meeting_fuente_viva() -> dict[str, Any]:
    out: dict[str, Any] = {"gog_available": _gog_available(), "tactiq_root": TACTIQ_ROOT}
    proc = git_show_main(_procesados_jsonl("meeting"))
    if proc:
        for line in reversed(proc.splitlines()):
            if '"_meta"' in line:
                try:
                    meta = json.loads(line)
                    out["last_procesados_meta"] = meta.get("ts")
                except json.JSONDecodeError:
                    pass
                break
    summaries = _latest_main_summary()
    if summaries:
        out["last_summary_main"] = summaries
    if not out["gog_available"]:
        out["note"] = "gog no disponible"
        return out
    acc = _personal_account()
    r = _run(
        [
            "gog",
            "drive",
            "ls",
            f"--parent={TACTIQ_ROOT}",
            "--json",
            "--account",
            acc,
            "--no-input",
        ]
    )
    if r.returncode != 0:
        out["gog_error"] = (r.stderr or r.stdout or "error").strip()[:200]
        return out
    try:
        data = json.loads(r.stdout or "{}")
        docs = [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "modifiedTime": f.get("modifiedTime"),
                "size": f.get("size"),
            }
            for f in data.get("files", [])
            if f.get("mimeType") == "application/vnd.google-apps.document"
        ]
        out["tactiq_pending_docs"] = docs[:10]
    except json.JSONDecodeError:
        out["tactiq_pending_docs"] = []
    return out


def _latest_main_summary() -> dict[str, str] | None:
    inst = instance_root()
    r = _run(
        [
            "git",
            "-C",
            str(inst),
            "ls-tree",
            "-r",
            "--name-only",
            "origin/main",
            _rel_path(_MEETINGS_SUMMARIES_KEY) + "/",
        ]
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    files = sorted(r.stdout.strip().splitlines())
    if not files:
        return None
    latest = files[-1]
    blob = git_show_main(latest)
    titulo = ""
    if blob:
        for line in blob.splitlines():
            if line.startswith("titulo:"):
                titulo = line.split(":", 1)[-1].strip()
                break
    return {"path": latest, "titulo": titulo}


def _drive_fuente_viva() -> dict[str, Any]:
    state_path = _rel_path(_MODULE_STATE_KEY["drive"])
    main_text = git_show_main(state_path)
    out: dict[str, Any] = {}
    if main_text:
        fecha = _parse_estado_date(main_text, "Fecha:")
        out["estado_md"] = {"fecha": fecha, "excerpt": main_text.splitlines()[:5]}
    else:
        out["estado_md"] = None
    return out


def _whatsapp_fuente_viva() -> dict[str, Any]:
    state_path = _rel_path(_MODULE_STATE_KEY["whatsapp"])
    main_text = git_show_main(state_path)
    out: dict[str, Any] = {}
    if main_text:
        out["estado_md_date"] = _parse_estado_date(main_text) or _parse_estado_date(main_text, "fecha:")
        out["estado_excerpt"] = main_text.splitlines()[:8]
    proc = git_show_main(_procesados_jsonl("whatsapp"))
    if proc:
        for line in reversed(proc.splitlines()):
            if '"_routine_run"' in line:
                try:
                    out["last_routine_run"] = json.loads(line)
                except json.JSONDecodeError:
                    pass
                break
    return out


def _main_block(module: str) -> dict[str, Any]:
    block: dict[str, Any] = {}
    if module == "mail":
        rel = _rel_path(_MODULE_STATE_KEY["mail"])
        text = git_show_main(rel)
        block["estado_md"] = {
            "path": rel,
            "updated": _parse_estado_date(text) if text else None,
        }
        block["last_merge"] = git_log_main(_module_dir("mail"))
    elif module == "meeting":
        block["last_merge"] = git_log_main(_module_dir("meeting"))
        block["_procesados_jsonl"] = git_log_main(_procesados_jsonl("meeting"))
    elif module == "drive":
        rel = _rel_path(_MODULE_STATE_KEY["drive"])
        text = git_show_main(rel)
        block["estado_md"] = {"path": rel, "fecha": _parse_estado_date(text, "Fecha:") if text else None}
        block["last_merge"] = git_log_main(_module_dir("drive"))
    elif module == "whatsapp":
        rel = _rel_path(_MODULE_STATE_KEY["whatsapp"])
        text = git_show_main(rel)
        block["estado_md"] = {
            "path": rel,
            "updated": (_parse_estado_date(text) or _parse_estado_date(text, "fecha:")) if text else None,
        }
        block["last_merge"] = git_log_main(_module_dir("whatsapp"))
    return block


def _working_block(module: str) -> dict[str, Any]:
    paths = {
        "mail": [_rel_path(_MODULE_STATE_KEY["mail"])],
        "meeting": [_procesados_jsonl("meeting")],
        "drive": [_rel_path(_MODULE_STATE_KEY["drive"])],
        "whatsapp": [_rel_path(_MODULE_STATE_KEY["whatsapp"])],
    }
    return {p: git_local_diff(p) for p in paths.get(module, [])}


def fresh_module(module: str, *, local: bool = False) -> FreshReport:
    module = MODULE_ALIASES.get(module, module)
    if module not in MODULE_PREFIX:
        raise ValueError(f"Módulo desconocido: {module}")
    prefix = MODULE_PREFIX[module]
    fuente_fn = {
        "mail": _mail_fuente_viva,
        "meeting": _meeting_fuente_viva,
        "drive": _drive_fuente_viva,
        "whatsapp": _whatsapp_fuente_viva,
    }[module]
    return FreshReport(
        module=module,
        main=_main_block(module),
        working=_working_block(module) if local else None,
        auto_pr=list_auto_prs(prefix),
        fuente_viva=fuente_fn(),
    )


def fresh_all(*, local: bool = False) -> dict[str, Any]:
    return {
        "generated_at": _now_iso(),
        "base": "origin/main",
        "repo": _gh_repo(),
        "modules": {m: fresh_module(m, local=local).to_dict() for m in ALL_MODULES},
    }


def format_json_report(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_markdown_heartbeat(data: dict[str, Any]) -> str:
    """Markdown block for sec-heartbeat ## Frescura extractoras."""
    lines = [
        "## Frescura extractoras",
        f"> `secretary fresh all` · {data.get('generated_at', _now_iso())} · base `{data.get('base', 'origin/main')}`",
        "",
    ]
    order = ["meeting", "mail", "drive", "whatsapp"]
    labels = {"meeting": "reuniones", "mail": "correo", "drive": "drive", "whatsapp": "whatsapp"}
    modules = data.get("modules", {})
    for key in order:
        mod = modules.get(key, {})
        label = labels[key]
        parts: list[str] = []
        main = mod.get("main") or {}
        if main.get("last_merge"):
            lm = main["last_merge"]
            subj = lm.get("subject", "")[:72]
            parts.append(f"main: última merge `{lm.get('timestamp', '—')}` ({subj})")
        ed = main.get("estado_md") or {}
        if ed.get("updated") or ed.get("fecha"):
            parts.append(f"main `state.md` → `{ed.get('updated') or ed.get('fecha')}`")
        for pr in mod.get("auto_pr") or []:
            n = len(pr.get("files") or [])
            parts.append(f"PR #{pr.get('number')} `{pr.get('branch')}` ({n} arch)")
        fv = mod.get("fuente_viva") or {}
        if key == "mail" and fv.get("latest_email"):
            le = fv["latest_email"]
            parts.append(f"vivo: último correo {le.get('date', '—')}")
        if key == "meeting":
            docs = fv.get("tactiq_pending_docs") or []
            if docs:
                parts.append(f"vivo: {len(docs)} doc(s) Tactiq en raíz")
        body = "; ".join(parts) if parts else "sin evidencia reciente"
        lines.append(f"- **{label}** — {body}")
    lines.append("- **wiki** — (ver `secretary fresh` fase 2)")
    return "\n".join(lines) + "\n"
