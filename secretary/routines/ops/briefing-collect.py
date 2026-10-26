#!/usr/bin/env python3
"""briefing-collect.py — recolector de entradas para secretary-briefing.

Junta en un JSON lo que el briefing consultaba con llamadas sueltas: config,
briefs recientes, decisiones pendientes, señales, conversaciones, PR por repo
habilitado, heartbeat, frescura de extractores, corridas de rutinas, loops,
commits recientes de la instancia y agenda del día.

Solo lee. Nunca crea, edita ni cierra issues, ni envía correo. Si una fuente
falla, la registra en `sources.<nombre>` con `status: error` y sigue.

Uso:
  briefing-collect.py                  # escribe el JSON en un directorio temporal e imprime la ruta
  briefing-collect.py --out-dir DIR    # escribe DIR/briefing-input.json
  briefing-collect.py --stdout         # imprime el JSON
  briefing-collect.py --dry-run        # igual que el modo por defecto (sin efectos)

Biblioteca estándar más `secretary`, `secretary-desk`, `gh`, `git` y `gog` por subprocess.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
BODY_CHARS = 600
BRIEF_BODY_CHARS = 8000
COMMENT_CHARS = 800
HEARTBEAT_LINES = 150
SIGNALS_PER_SOURCE = 12
SIGNAL_CHARS = 300


class SourceError(RuntimeError):
    """Fallo de una fuente; se registra en el JSON en vez de abortar."""


def run(args: list[str], timeout: int = 90, cwd: Path | None = None) -> str:
    # COLUMNS amplio: el CLI `secretary` imprime con rich, que parte líneas largas
    # a 80 columnas sin TTY y rompe la salida JSON.
    env = {**os.environ, "COLUMNS": "100000"}
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              cwd=str(cwd) if cwd else None, env=env)
    except FileNotFoundError as exc:
        raise SourceError(f"comando no disponible: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceError(f"timeout {timeout}s: {' '.join(args[:3])}") from exc
    if proc.returncode:
        msg = (proc.stderr or proc.stdout).strip().splitlines()
        raise SourceError(f"exit {proc.returncode}: {msg[-1][:300] if msg else args[0]}")
    return proc.stdout


def run_json(args: list[str], timeout: int = 90) -> Any:
    out = run(args, timeout=timeout)
    try:
        return json.loads(out, strict=False)
    except json.JSONDecodeError as exc:
        raise SourceError(f"salida no es JSON: {' '.join(args[:3])}") from exc


def clip(text: str | None, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + f"… [+{len(text) - limit} chars]"


def secretary_python() -> str:
    """Intérprete del CLI `secretary` instalado (para `-m secretary.conversations`)."""
    exe = shutil.which("secretary")
    if exe:
        try:
            first = Path(exe).read_text(errors="replace").splitlines()[0]
            if first.startswith("#!"):
                interp = first[2:].strip().split()[0]
                if Path(interp).is_file():
                    return interp
        except (OSError, IndexError):
            pass
    return sys.executable


# --- fuentes ---------------------------------------------------------------

class Collector:
    def __init__(self, config: dict[str, Any], now: datetime, since_hours: int) -> None:
        self.config = config
        self.now = now
        self.today = now.date().isoformat()
        self.since = now - timedelta(hours=since_hours)
        self.instance = Path(config.get("instance") or os.environ.get("SECRETARY_INSTANCE", "~/.secretary")).expanduser()
        brief = config.get("brief") or {}
        self.brief_repo = brief.get("repo") or ""
        self.brief_label = brief.get("label") or ""
        repos = ((config.get("dispatch") or {}).get("executor") or {}).get("repos") or []
        self.repos = [r for r in repos if isinstance(r, dict) and r.get("repo")]
        self.paths = config.get("paths") or {}

    def path_key(self, dotted: str) -> Path | None:
        node: Any = self.paths
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return Path(node).expanduser() if isinstance(node, str) else None

    def config_section(self) -> dict[str, Any]:
        def get(key: str) -> Any:
            try:
                value = run(["secretary", "config", "get", key], timeout=20).strip()
            except SourceError:
                return None
            return {"True": True, "true": True, "False": False, "false": False}.get(value, value)

        return {
            "instance": str(self.instance),
            "timezone": self.config.get("timezone"),
            "brief_repo": self.brief_repo,
            "brief_label": self.brief_label,
            "repos_enabled": [r["repo"] for r in self.repos],
            "routines_disabled": ((self.config.get("dispatch") or {}).get("routines") or {}).get("disabled") or [],
            "brief_email_enabled": get("desk.notifications.brief_email") is True,
            "conversations_enabled": get("desk.conversations.enabled") is True,
            "brief_refresh_issue": os.environ.get("BRIEF_REFRESH_ISSUE") or None,
        }

    def briefs(self) -> dict[str, Any]:
        if not (self.brief_repo and self.brief_label):
            raise SourceError("brief.repo o brief.label ausentes en config")
        rows = run_json(["gh", "issue", "list", "--repo", self.brief_repo, "--label", self.brief_label,
                         "--state", "all", "--limit", "6", "--json", "number,title,state,createdAt,url"])
        rows.sort(key=lambda r: r.get("createdAt") or "", reverse=True)
        today_issue = next((r for r in rows if self.today in (r.get("title") or "")), None)
        previous = next((r for r in rows if r.get("state") == "OPEN" and r is not today_issue), None)
        return {
            "recent": rows,
            "today_issue": self._issue_detail(today_issue["number"]) if today_issue else None,
            "previous_open": self._issue_detail(previous["number"]) if previous else None,
        }

    def _issue_detail(self, number: int) -> dict[str, Any]:
        view = run_json(["gh", "issue", "view", str(number), "--repo", self.brief_repo,
                         "--json", "number,title,url,state,labels,body,comments"])
        return {
            "number": view.get("number"), "title": view.get("title"), "url": view.get("url"),
            "state": view.get("state"),
            "labels": [lb.get("name") for lb in view.get("labels") or [] if isinstance(lb, dict)],
            "body": clip(view.get("body"), BRIEF_BODY_CHARS),
            "comments": [{"createdAt": c.get("createdAt"), "author": (c.get("author") or {}).get("login"),
                          "body": clip(c.get("body"), COMMENT_CHARS)} for c in view.get("comments") or []],
        }

    def decisions(self) -> dict[str, Any]:
        data = run_json(["secretary-desk", "decisions"], timeout=180)
        items = []
        for row in data.get("items") or []:
            body = row.get("body") or ""
            fp = re.search(r"<!--\s*desk:fingerprint\s+(\S+)\s*-->", body)
            items.append({
                "repo": row.get("repo"), "number": row.get("number"), "title": row.get("title"),
                "url": row.get("url"), "updatedAt": row.get("updatedAt"),
                "labels": [lb.get("name") for lb in row.get("labels") or [] if isinstance(lb, dict)],
                "fingerprint": fp.group(1) if fp else None,
                "proposal": row.get("proposal") or None,
                "body_head": clip(re.sub(r"<!--.*?-->", "", body, flags=re.S).strip(), BODY_CHARS),
            })
        items.sort(key=lambda r: r.get("updatedAt") or "", reverse=True)
        return {"count": len(items), "items": items, "errors": data.get("errors") or []}

    def signals(self) -> dict[str, Any]:
        data = run_json(["secretary-desk", "signals"], timeout=120)
        sources = []
        for src in data.get("sources") or []:
            hits = src.get("candidate_signals") or []
            sources.append({
                "path": src.get("path"), "modified_at": src.get("modified_at"),
                "requires_reconciliation": src.get("requires_reconciliation"),
                "signals_total": len(hits),
                "candidate_signals": [{"line": h.get("line"), "text": clip(h.get("text"), SIGNAL_CHARS)}
                                      for h in hits[-SIGNALS_PER_SOURCE:]],
            })
        return {"sources": sources}

    def conversations(self) -> dict[str, Any]:
        py = secretary_python()
        out: dict[str, Any] = {}
        for action in ("questions", "pending"):
            try:
                out[action] = run_json([py, "-m", "secretary.conversations", action], timeout=60)
            except SourceError as exc:
                out[action] = {"state": "error", "reason": str(exc)}
        return out

    def repo_prs(self, repo: str) -> dict[str, Any]:
        opened = run_json(["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "50", "--json",
                           "number,title,url,headRefName,isDraft,createdAt,updatedAt,labels"])
        merged = run_json(["gh", "pr", "list", "--repo", repo, "--state", "merged", "--limit", "20", "--json",
                           "number,title,url,headRefName,mergedAt"])
        cutoff = self.since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for pr in opened:
            pr["labels"] = [lb.get("name") for lb in pr.get("labels") or [] if isinstance(lb, dict)]
        return {
            "open": opened,
            "merged_recent": [pr for pr in merged if (pr.get("mergedAt") or "") >= cutoff],
        }

    def heartbeat(self) -> dict[str, Any]:
        root = self.path_key("subsystem.heartbeat") or self.path_key("operations.heartbeat") \
            or self.instance / "subsystem/heartbeat"
        latest = root / "latest.md"
        if not latest.is_file():
            raise SourceError(f"no existe {latest}")
        mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
        lines = latest.read_text(errors="replace").splitlines()
        stamp = next((ln.split(":", 1)[1].strip() for ln in lines[:40]
                      if re.match(r"^-?\s*(timestamp|fecha|generated)", ln, re.I) and ":" in ln), None)
        return {
            "path": str(latest), "modified_at": mtime.astimezone(self.now.tzinfo).isoformat(),
            "age_hours": round((self.now - mtime).total_seconds() / 3600, 1),
            "declared_timestamp": stamp, "total_lines": len(lines),
            "text": "\n".join(lines[:HEARTBEAT_LINES]),
        }

    def freshness(self) -> Any:
        return run_json(["secretary", "fresh", "all", "--format", "json"], timeout=180)

    def routine_runs(self) -> dict[str, Any]:
        root = self.path_key("subsystem.routines") or self.instance / "subsystem/routines"
        runs_dir = root / "runs"
        if not runs_dir.is_dir():
            raise SourceError(f"no existe {runs_dir}")
        days = {(self.now - timedelta(days=d)).date().isoformat() for d in range(3)}
        rows = []
        for day in sorted(days):
            for meta in sorted((runs_dir / day).glob("*.meta.json")) if (runs_dir / day).is_dir() else []:
                try:
                    m = json.loads(meta.read_text())
                except (OSError, json.JSONDecodeError):
                    rows.append({"file": meta.name, "status": "unreadable"})
                    continue
                started = m.get("started_at") or ""
                try:
                    if datetime.fromisoformat(started) < self.since:
                        continue
                except ValueError:
                    pass
                tokens = m.get("tokens") or {}
                rows.append({
                    "routine": m.get("routine_id"), "started_at": started, "status": m.get("status"),
                    "exit_code": m.get("exit_code"), "trigger": m.get("trigger"),
                    "duration_s": round((m.get("duration_ms") or 0) / 1000),
                    "tokens_total": tokens.get("total"), "errors": (m.get("errors") or [])[:3],
                })
        by_routine: dict[str, dict[str, Any]] = {}
        for r in rows:
            key = r.get("routine") or "?"
            agg = by_routine.setdefault(key, {"runs": 0, "failed": 0, "last_started": None, "last_status": None})
            agg["runs"] += 1
            if r.get("status") not in ("success", None) or (r.get("exit_code") not in (0, None)):
                agg["failed"] += 1
            if (r.get("started_at") or "") >= (agg["last_started"] or ""):
                agg["last_started"], agg["last_status"] = r.get("started_at"), r.get("status")
        return {"since": self.since.isoformat(), "count": len(rows), "by_routine": by_routine, "runs": rows}

    def loops(self) -> dict[str, Any]:
        root = self.instance / "loops"
        if not root.is_dir():
            raise SourceError(f"no existe {root}")
        out: dict[str, Any] = {}
        for loop in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            entry: dict[str, Any] = {}
            state = loop / "state.md"
            if state.is_file():
                entry["state_path"] = str(state)
                entry["state_modified_at"] = datetime.fromtimestamp(state.stat().st_mtime).astimezone().isoformat()
                entry["state_head"] = clip("\n".join(state.read_text(errors="replace").splitlines()[:30]), 2500)
            reports = loop / "reports"
            if reports.is_dir():
                latest = sorted(reports.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:2]
                entry["latest_reports"] = [{
                    "path": str(p),
                    "modified_at": datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(),
                    "tail": clip("\n".join(p.read_text(errors="replace").splitlines()[-25:]), 2500),
                } for p in latest]
            if entry:
                out[loop.name] = entry
        return out

    def instance_git(self) -> dict[str, Any]:
        since = self.since.strftime("%Y-%m-%d %H:%M")
        log = run(["git", "-C", str(self.instance), "log", "origin/main", f"--since={since}",
                   "--format=%h%x09%ad%x09%s", "--date=format:%Y-%m-%d %H:%M"], timeout=30)
        commits = [dict(zip(("sha", "date", "subject"), ln.split("\t", 2))) for ln in log.splitlines() if ln]
        return {"since": since, "count": len(commits), "commits": commits[:40]}

    def calendar(self) -> dict[str, Any]:
        account = (self.config.get("accounts") or {}).get("personal")
        if not account:
            raise SourceError("accounts.personal ausente en config")
        data = run_json(["gog", "calendar", "events", "--account", account, "--today", "--json"], timeout=60)
        keep = ("summary", "start", "end", "location", "status", "htmlLink")
        events = [{k: ev.get(k) for k in keep if k in ev} for ev in data.get("events") or []]
        return {"scope": "personal", "count": len(events), "events": events,
                "note": "Solo el calendario de la cuenta personal; otras cuentas no se consultan."}


def load_config() -> dict[str, Any]:
    return run_json(["secretary", "config", "show"], timeout=30)


def timed(fn: Callable[[], Any]) -> tuple[str, Any, str | None, float]:
    start = time.monotonic()
    try:
        return "ok", fn(), None, time.monotonic() - start
    except SourceError as exc:
        return "error", None, str(exc), time.monotonic() - start
    except Exception as exc:  # noqa: BLE001 — una fuente rota no aborta el recolector
        return "error", None, f"{type(exc).__name__}: {exc}", time.monotonic() - start


def collect(since_hours: int = 36, now: datetime | None = None,
            config_loader: Callable[[], dict[str, Any]] = load_config,
            collector_cls: type[Collector] = Collector) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    status, config, error, secs = timed(config_loader)
    sources["config"] = {"status": status, "seconds": round(secs, 1), **({"error": error} if error else {})}
    config = config or {}
    tz_name = config.get("timezone") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    now = (now or datetime.now(tz)).astimezone(tz)
    col = collector_cls(config, now, since_hours)

    jobs: dict[str, Callable[[], Any]] = {
        "config_relevant": col.config_section,
        "briefs": col.briefs,
        "decisions": col.decisions,
        "signals": col.signals,
        "conversations": col.conversations,
        "heartbeat": col.heartbeat,
        "freshness": col.freshness,
        "routine_runs": col.routine_runs,
        "loops": col.loops,
        "instance_git": col.instance_git,
        "calendar": col.calendar,
    }
    for repo in col.repos:
        jobs[f"repo:{repo['repo']}"] = (lambda name=repo["repo"]: col.repo_prs(name))

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {name: pool.submit(timed, fn) for name, fn in jobs.items()}
        for name, fut in futures.items():
            status, data, error, secs = fut.result()
            sources[name] = {"status": status, "seconds": round(secs, 1), **({"error": error} if error else {})}
            results[name] = data

    repos = {name.split(":", 1)[1]: results.pop(name) for name in list(results) if name.startswith("repo:")}
    failed = sorted(name for name, s in sources.items() if s["status"] != "ok")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(timespec="seconds"),
        "today": now.date().isoformat(),
        "weekday": now.strftime("%A"),
        "timezone": tz_name,
        "since": col.since.isoformat(timespec="seconds"),
        "config": results.get("config_relevant"),
        "briefs": results.get("briefs"),
        "decisions": results.get("decisions"),
        "signals": results.get("signals"),
        "conversations": results.get("conversations"),
        "repos": repos,
        "heartbeat": results.get("heartbeat"),
        "freshness": results.get("freshness"),
        "routine_runs": results.get("routine_runs"),
        "loops": results.get("loops"),
        "instance_git": results.get("instance_git"),
        "calendar": results.get("calendar"),
        "sources": sources,
        "failed_sources": failed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recolector de entradas para secretary-briefing (solo lectura).")
    parser.add_argument("--out-dir", type=Path, help="Directorio de salida (por defecto, uno temporal nuevo).")
    parser.add_argument("--stdout", action="store_true", help="Imprime el JSON en vez de escribir un archivo.")
    parser.add_argument("--dry-run", action="store_true", help="Sin efectos (es el único modo; se acepta por contrato N6).")
    parser.add_argument("--since-hours", type=int, default=36, help="Ventana para merges, commits y corridas (default 36).")
    args = parser.parse_args(argv)

    data = collect(since_hours=args.since_hours)
    text = json.dumps(data, ensure_ascii=False, indent=1, default=str)
    if args.stdout:
        print(text)
    else:
        out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="briefing-collect-"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "briefing-input.json"
        out.write_text(text + "\n", encoding="utf-8")
        print(out)
    ok = sum(1 for s in data["sources"].values() if s["status"] == "ok")
    print(f"[briefing-collect] fuentes ok {ok}/{len(data['sources'])}; fallidas: "
          f"{', '.join(data['failed_sources']) or 'ninguna'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
