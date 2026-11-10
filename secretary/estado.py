"""Live per-repo status of agent sessions, metadata only.

Collects sessions from Claude (desktop app + CLI), Codex and Cursor local files,
reconciles them with git worktrees and `docs/plans` Nodes tables, and returns a
JSON-serializable report.

Privacy contract: only metadata is read. Every adapter reads a fixed key
whitelist (or only file names and mtimes) and the report is built exclusively
from the `*_KEYS` constants below. Transcript bodies, permission and MCP
settings, and prompts are never read or emitted.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

SCHEMA_VERSION = 1

# --- Output whitelists (the only keys that may appear in the report) ----------
SESSION_KEYS = frozenset({
    "id", "title", "harness", "repo", "branch", "worktree", "pr",
    "status", "time", "plan", "node",
})
PR_KEYS = frozenset({"state", "number", "url"})
REPO_KEYS = frozenset({"name", "path", "worktrees", "plans"})
WORKTREE_KEYS = frozenset({"path", "branch"})
PLAN_KEYS = frozenset({"id", "goal", "status", "path", "nodes"})
NODE_KEYS = frozenset({"id", "mode", "status", "note", "session", "harness", "branch", "pr"})
REPORT_KEYS = frozenset({"schema", "generated_at", "repos", "sessions", "warnings"})

# --- Input whitelists ----------------------------------------------------------
CLAUDE_DESKTOP_READ_KEYS = (
    "sessionId", "cliSessionId", "title", "cwd", "originCwd",
    "createdAt", "lastActivityAt", "isArchived", "model", "scheduledTaskId",
)
CODEX_READ_KEYS = ("id", "cwd", "git", "timestamp")

ACTIVE_SECONDS = 15 * 60
IDLE_SECONDS = 24 * 3600
PR_CACHE_SECONDS = 60
MAX_FIRST_LINE = 4_000_000  # Codex first line can be large; read, keep 4 keys, drop the rest.
NOTE_MAX = 200


@dataclass
class Sources:
    claude_desktop: Path = field(
        default_factory=lambda: Path.home() / "Library/Application Support/Claude/claude-code-sessions"
    )
    claude_projects: Path = field(default_factory=lambda: Path.home() / ".claude/projects")
    codex_sessions: Path = field(default_factory=lambda: Path.home() / ".codex/sessions")
    cursor_projects: Path = field(default_factory=lambda: Path.home() / ".cursor/projects")
    cache_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "secretary"
    )


@dataclass
class RawSession:
    id: str
    harness: str
    time: float  # epoch seconds, last activity
    title: str | None = None
    cwd: str | None = None
    branch: str | None = None
    archived: bool = False
    alt_ids: tuple[str, ...] = ()


# --- Generic helpers -----------------------------------------------------------

def _git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _to_epoch(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def decode_project_dir(name: str) -> str | None:
    """Recover a cwd from an encoded project folder name (`/` and `.` become `-`).

    Walks the real filesystem, matching directory entries by their encoded form,
    so no file content is needed. Returns None when the path no longer exists.
    """
    rest = name.lstrip("-")

    def walk(base: Path, rest: str) -> Path | None:
        if not rest:
            return base
        try:
            entries = sorted(os.listdir(base), key=len, reverse=True)
        except OSError:
            return None
        for entry in entries:
            enc = re.sub(r"[^A-Za-z0-9]", "-", entry)
            if rest == enc:
                return base / entry
            if rest.startswith(enc + "-") and (base / entry).is_dir():
                found = walk(base / entry, rest[len(enc) + 1:])
                if found:
                    return found
        return None

    found = walk(Path("/"), rest)
    return str(found) if found else None


# --- Adapters ---------------------------------------------------------------------

def read_claude_desktop(root: Path, since: float) -> list[RawSession]:
    out: list[RawSession] = []
    if not root.is_dir():
        return out
    for path in root.glob("*/*/local_*.json"):
        mtime = _mtime(path)
        if mtime is None or mtime < since:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        meta = {k: data.get(k) for k in CLAUDE_DESKTOP_READ_KEYS}
        sid = _str(meta["sessionId"]) or path.stem
        cli = _str(meta["cliSessionId"])
        out.append(RawSession(
            id=sid,
            harness="claude-desktop",
            time=_to_epoch(meta["lastActivityAt"]) or mtime,
            title=_str(meta["title"]),
            cwd=_str(meta["cwd"]) or _str(meta["originCwd"]),
            archived=meta["isArchived"] is True,
            alt_ids=(cli,) if cli else (),
        ))
    return out


def read_claude_cli(root: Path, since: float, skip_ids: set[str]) -> list[RawSession]:
    """Transcript file names and mtimes only; bodies are never opened."""
    out: list[RawSession] = []
    if not root.is_dir():
        return out
    for proj in root.iterdir():
        if not proj.is_dir():
            continue
        files = []
        for f in proj.glob("*.jsonl"):
            mtime = _mtime(f)
            if mtime is not None and mtime >= since and f.stem not in skip_ids:
                files.append((f, mtime))
        if not files:
            continue
        cwd = decode_project_dir(proj.name)
        for f, mtime in files:
            out.append(RawSession(id=f.stem, harness="claude-cli", time=mtime, cwd=cwd))
    return out


def read_codex(root: Path, since: float) -> list[RawSession]:
    out: list[RawSession] = []
    if not root.is_dir():
        return out
    for path in root.glob("*/*/*/rollout-*.jsonl"):
        mtime = _mtime(path)
        if mtime is None or mtime < since:
            continue
        meta: dict[str, Any] = {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                first = json.loads(fh.readline(MAX_FIRST_LINE))  # first line only
            payload = first.get("payload") if isinstance(first, dict) else None
            if isinstance(first, dict) and first.get("type") == "session_meta" and isinstance(payload, dict):
                meta = {k: payload.get(k) for k in CODEX_READ_KEYS}
        except (OSError, ValueError):
            pass
        git = meta.get("git") if isinstance(meta.get("git"), dict) else {}
        out.append(RawSession(
            id=_str(meta.get("id")) or path.stem,
            harness="codex",
            time=mtime,
            cwd=_str(meta.get("cwd")),
            branch=_str(git.get("branch")),
        ))
    return out


def read_cursor(root: Path, since: float) -> list[RawSession]:
    """Degraded: workspace from the folder name, time from mtimes. No content."""
    out: list[RawSession] = []
    if not root.is_dir():
        return out
    for ws in root.iterdir():
        transcripts = ws / "agent-transcripts"
        if not transcripts.is_dir():
            continue
        cwd: str | None = None
        decoded = False
        for chat in transcripts.iterdir():
            if not chat.is_dir():
                continue
            times = [t for t in [_mtime(chat), *(_mtime(c) for c in chat.iterdir())] if t]
            if not times or max(times) < since:
                continue
            if not decoded:
                cwd, decoded = decode_project_dir(ws.name), True
            out.append(RawSession(id=chat.name, harness="cursor", time=max(times), cwd=cwd))
    return out


# --- Repo / worktree resolution -----------------------------------------------------

class GitCache:
    def __init__(self) -> None:
        self._cwd: dict[str, dict[str, str | None]] = {}
        self._worktrees: dict[str, list[dict[str, str | None]]] = {}

    def resolve(self, cwd: str) -> dict[str, str | None]:
        """Return {root, worktree, branch}; best effort when the path is gone."""
        if cwd in self._cwd:
            return self._cwd[cwd]
        info: dict[str, str | None] = {"root": None, "worktree": None, "branch": None}
        path = Path(cwd)
        if path.is_dir():
            out = _git(["rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"], path)
            if out and len(out.splitlines()) == 2:
                top, common = out.splitlines()
                root = str(Path(common).parent) if Path(common).name == ".git" else top
                info = {"root": root, "worktree": top, "branch": _git(["symbolic-ref", "--short", "-q", "HEAD"], path)}
        else:
            for marker in ("/.claude/worktrees/", "/.wt/"):
                if marker in cwd:
                    root = cwd.split(marker)[0]
                    if Path(root, ".git").exists():
                        info = {"root": root, "worktree": cwd, "branch": None}
                    break
        self._cwd[cwd] = info
        return info

    def worktrees(self, root: str) -> list[dict[str, str | None]]:
        if root in self._worktrees:
            return self._worktrees[root]
        result: list[dict[str, str | None]] = []
        out = _git(["worktree", "list", "--porcelain"], Path(root))
        if out:
            cur: dict[str, str | None] = {}
            for line in out.splitlines() + [""]:
                if line.startswith("worktree "):
                    cur = {"path": line[9:], "branch": None}
                elif line.startswith("branch ") and cur:
                    cur["branch"] = line[7:].removeprefix("refs/heads/")
                elif not line and cur:
                    result.append(cur)
                    cur = {}
        self._worktrees[root] = result
        return result


# --- Plan reader ---------------------------------------------------------------------

def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_plan(text: str, rel_path: str) -> dict[str, Any] | None:
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            try:
                loaded = yaml.safe_load(parts[1])
                meta = loaded if isinstance(loaded, dict) else {}
            except yaml.YAMLError:
                meta = {}
            body = parts[2]
    nodes: list[dict[str, Any]] = []
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Nodes\s*$", line):
            header: list[str] | None = None
            for row in lines[i + 1:]:
                if row.startswith("#"):
                    break
                if not row.strip().startswith("|"):
                    if header:
                        break
                    continue
                cells = _split_row(row)
                if header is None:
                    header = [c.lower() for c in cells]
                    continue
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    continue
                rec = dict(zip(header, cells))
                if not rec.get("id"):
                    continue
                node = {k: (rec.get(k) or None) for k in NODE_KEYS}
                node["id"] = rec["id"]
                if node["note"]:
                    node["note"] = node["note"][:NOTE_MAX]
                nodes.append(node)
            break
    if not meta.get("id") and not nodes:
        return None
    return {
        "id": str(meta.get("id") or Path(rel_path).stem),
        "goal": _str(meta.get("goal")),
        "status": _str(meta.get("status")),
        "path": rel_path,
        "nodes": nodes,
    }


def read_plans(root: str, worktrees: list[dict[str, str | None]]) -> list[dict[str, Any]]:
    """Plans from the main checkout and every worktree; newest file wins per id."""
    best: dict[str, tuple[float, dict[str, Any]]] = {}
    bases = [root] + [w["path"] for w in worktrees if w["path"] and w["path"] != root]
    for base in bases:
        for f in sorted(Path(base, "docs", "plans").glob("*.md")):
            try:
                plan = parse_plan(f.read_text(encoding="utf-8"), f"docs/plans/{f.name}")
            except OSError:
                continue
            if not plan:
                continue
            mt = _mtime(f) or 0
            if plan["id"] not in best or mt > best[plan["id"]][0]:
                best[plan["id"]] = (mt, plan)
    return [p for _, p in sorted(best.values(), key=lambda t: t[1]["id"])]


# --- PRs ------------------------------------------------------------------------------

def _pr_lookup(root: str, cache_dir: Path, now: float) -> dict[str, dict[str, Any]] | None:
    """Map branch -> PR via `gh`, cached for 60 s. None when unavailable."""
    cache_file = cache_dir / "estado-prs.json"
    cache: dict[str, Any] = {}
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    hit = cache.get(root)
    if isinstance(hit, dict) and now - hit.get("at", 0) < PR_CACHE_SECONDS:
        return hit.get("prs")
    prs: dict[str, dict[str, Any]] | None = None
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--state", "all", "--limit", "100",
             "--json", "number,headRefName,state,url"],
            cwd=root, capture_output=True, text=True, timeout=20,
        )
        if out.returncode == 0:
            prs = {}
            for item in sorted(json.loads(out.stdout), key=lambda x: x["number"]):
                prs[item["headRefName"]] = {
                    "state": str(item["state"]).lower(), "number": item["number"], "url": item["url"],
                }
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        prs = None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache[root] = {"at": now, "prs": prs}
        cache_file.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass
    return prs


# --- Reconciliation -------------------------------------------------------------------

MAIN_BRANCHES = {"main", "master"}


def _match_node(sess: dict[str, Any], aliases: Iterable[str], plans: list[dict[str, Any]],
                worktrees: list[dict[str, str | None]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    pairs = [(p, n) for p in plans for n in p["nodes"]]
    ids = {a for a in aliases if a}
    # 1. session id
    for p, n in pairs:
        if n["session"] and any(n["session"] == a or (len(n["session"]) >= 8 and a.startswith(n["session"])) for a in ids):
            return p, n
    # 2. branch (unique, non-main, non-done)
    branch = sess["branch"]
    if branch and branch not in MAIN_BRANCHES:
        hits = [(p, n) for p, n in pairs if n["branch"] == branch and n["status"] != "done"]
        if len(hits) == 1:
            return hits[0]
    # 3. path: session worktree -> its branch -> node
    wt = sess["worktree"]
    if wt:
        wt_branch = next((w["branch"] for w in worktrees if w["path"] == wt), None)
        if wt_branch and wt_branch not in MAIN_BRANCHES:
            hits = [(p, n) for p, n in pairs if n["branch"] == wt_branch and n["status"] != "done"]
            if len(hits) == 1:
                return hits[0]
    return None


def _status(raw: RawSession, now: float) -> str:
    if raw.archived:
        return "archived"
    age = now - raw.time
    return "active" if age <= ACTIVE_SECONDS else "idle" if age <= IDLE_SECONDS else "stale"


def _pr_from_ref(ref: str | None) -> dict[str, Any]:
    m = re.search(r"(\d+)", ref or "")
    return {"state": "unknown", "number": int(m.group(1)) if m else None, "url": None}


def _excluded(root: str, exclude: list[str]) -> bool:
    name = Path(root).name
    for e in exclude:
        ep = os.path.expanduser(e)
        if e == name or root == ep or root.startswith(ep.rstrip("/") + "/"):
            return True
    return False


def collect(
    sources: Sources | None = None,
    *,
    days: int = 7,
    with_prs: bool = False,
    exclude: list[str] | None = None,
    scan_roots: list[str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    src = sources or Sources()
    now = now if now is not None else time.time()
    since = now - days * 86400
    exclude = exclude or []
    warnings: list[str] = []

    desktop = read_claude_desktop(src.claude_desktop, since)
    skip = {a for r in desktop for a in r.alt_ids}
    raws = desktop + read_claude_cli(src.claude_projects, since, skip) \
        + read_codex(src.codex_sessions, since) + read_cursor(src.cursor_projects, since)

    git = GitCache()
    sessions: list[dict[str, Any]] = []
    aliases: list[tuple[str, ...]] = []
    roots: dict[str, None] = {}
    for raw in raws:
        info = git.resolve(raw.cwd) if raw.cwd else {"root": None, "worktree": None, "branch": None}
        root = info["root"]
        if root and _excluded(root, exclude):
            continue
        if root:
            roots.setdefault(root)
        sessions.append({
            "id": raw.id, "title": raw.title, "harness": raw.harness,
            "repo": Path(root).name if root else None,
            "branch": info["branch"] or raw.branch,
            "worktree": info["worktree"], "pr": {"state": "unknown", "number": None, "url": None},
            "status": _status(raw, now), "time": _iso(raw.time), "plan": None, "node": None,
            "_root": root,
        })
        aliases.append((raw.id, *raw.alt_ids))

    for base in scan_roots if scan_roots is not None else ["~/Dev"]:
        b = Path(os.path.expanduser(base))
        if not b.is_dir():
            continue
        for child in sorted(b.iterdir()):
            if (child / ".git").exists() and (child / "docs" / "plans").is_dir():
                top = git.resolve(str(child))["root"]
                if top and not _excluded(top, exclude):
                    roots.setdefault(top)

    repos: list[dict[str, Any]] = []
    plans_by_root: dict[str, list[dict[str, Any]]] = {}
    prs_by_root: dict[str, dict[str, dict[str, Any]] | None] = {}
    for root in roots:
        wts = git.worktrees(root)
        plans = read_plans(root, wts)
        plans_by_root[root] = plans
        if with_prs:
            prs_by_root[root] = _pr_lookup(root, src.cache_dir, now)
            if prs_by_root[root] is None:
                warnings.append(f"PR lookup unavailable for {Path(root).name}")
        repos.append({
            "name": Path(root).name, "path": root,
            "worktrees": [{"path": w["path"], "branch": w["branch"]} for w in wts],
            "plans": plans,
        })

    for sess, ids in zip(sessions, aliases):
        root = sess["_root"]
        if not root:
            continue
        match = _match_node(sess, ids, plans_by_root.get(root, []), git.worktrees(root))
        if match:
            plan, node = match
            sess["plan"], sess["node"] = plan["id"], node["id"]
            if node["pr"]:
                sess["pr"] = _pr_from_ref(node["pr"])
        if with_prs and prs_by_root.get(root) is not None:
            pr = prs_by_root[root].get(sess["branch"] or "")
            sess["pr"] = pr if pr else {"state": "none", "number": None, "url": None}

    for s in sessions:
        del s["_root"]
    sessions.sort(key=lambda s: s["time"], reverse=True)
    repos.sort(key=lambda r: r["name"])
    return {
        "schema": SCHEMA_VERSION, "generated_at": _iso(now),
        "repos": repos, "sessions": sessions, "warnings": warnings,
    }


def assert_whitelist(report: dict[str, Any]) -> None:
    """Raise AssertionError if the report carries any key outside the whitelists."""
    def check(obj: dict[str, Any], allowed: frozenset[str], where: str) -> None:
        extra = set(obj) - allowed
        assert not extra, f"non-whitelisted keys in {where}: {sorted(extra)}"

    check(report, REPORT_KEYS, "report")
    for s in report["sessions"]:
        check(s, SESSION_KEYS, "session")
        check(s["pr"], PR_KEYS, "session.pr")
    for r in report["repos"]:
        check(r, REPO_KEYS, "repo")
        for w in r["worktrees"]:
            check(w, WORKTREE_KEYS, "worktree")
        for p in r["plans"]:
            check(p, PLAN_KEYS, "plan")
            for n in p["nodes"]:
                check(n, NODE_KEYS, "node")


def fingerprint(sources: Sources | None = None) -> str:
    """Cheap change signal for mtime polling (used by a future `serve`)."""
    src = sources or Sources()
    newest, count = 0.0, 0
    for root, pattern in [
        (src.claude_desktop, "*/*/local_*.json"), (src.claude_projects, "*/*.jsonl"),
        (src.codex_sessions, "*/*/*/rollout-*.jsonl"), (src.cursor_projects, "*/agent-transcripts/*"),
    ]:
        if root.is_dir():
            for f in root.glob(pattern):
                count += 1
                newest = max(newest, _mtime(f) or 0)
    return f"{count}:{newest}"
