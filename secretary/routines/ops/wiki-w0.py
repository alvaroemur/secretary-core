#!/usr/bin/env python3
"""W0 de wiki-update sin LLM (D15.8, n5 pieza 1).

Lista los PRs abiertos de rutinas automáticas, aplica la regla de encadenadas,
revisa comentarios sin resolver y mergea con merge commit los PRs limpios.
El LLM solo atiende `needs_llm`.

  wiki-w0.py [--repo <path>] [--prov-out <tsv>] [--dry-run]

stdout: JSON con merged[], closed_superseded[], needs_llm[] y failed[].
--dry-run: no mergea ni cierra; informa qué haría (mismas claves).
--prov-out: escribe el TSV de procedencia (`archivo<TAB>## header<TAB>PR#N`) de
los PRs mergeados (en --dry-run, de los que mergearía). Es un archivo de reporte,
no un efecto sobre GitHub ni git.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AUTO_RE = re.compile(r"^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$")
CHAINED = ("job-search", "drive")
AGENT_MARKS = ("agent-generated", "claude-generated")
SIGNATURE_CONTEXT = "wiki-update"

PR_QUERY = """
query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
  mergeable
  commits(last:1){nodes{commit{committedDate}}}
  reviewThreads(first:100){nodes{isResolved comments(first:20){nodes{
    path line body createdAt url author{login __typename}}}}}
  comments(last:100){nodes{body createdAt url author{login __typename}}}
  reviews(last:50){nodes{body state createdAt url author{login __typename}}}
}}}
"""


class GhError(RuntimeError):
    pass


def gh(repo: Path, *args: str) -> str:
    out = subprocess.run(["gh", *args], cwd=repo, capture_output=True, text=True)
    if out.returncode != 0:
        raise GhError((out.stderr or out.stdout).strip() or f"gh {args[0]} falló")
    return out.stdout


def is_agent(node: dict[str, Any]) -> bool:
    author = node.get("author") or {}
    if author.get("__typename") == "Bot" or str(author.get("login", "")).endswith("[bot]"):
        return True
    body = node.get("body") or ""
    if any(mark in body for mark in AGENT_MARKS):
        return True
    lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]
    if lines and lines[0].startswith("> 🤖"):
        return True
    return any(ln.startswith("🤖 _") for ln in lines)


def comment(kind: str, node: dict[str, Any]) -> dict[str, Any]:
    out = {
        "kind": kind,
        "author": (node.get("author") or {}).get("login", ""),
        "created_at": node.get("createdAt", ""),
        "url": node.get("url", ""),
        "body": node.get("body", ""),
    }
    if kind == "inline":
        out["path"] = node.get("path")
        out["line"] = node.get("line")
    return out


def pr_state(repo: Path, owner: str, name: str, number: int) -> dict[str, Any]:
    raw = gh(repo, "api", "graphql", "-f", f"query={PR_QUERY}", "-F", f"o={owner}", "-F", f"r={name}",
             "-F", f"n={number}")
    return json.loads(raw)["data"]["repository"]["pullRequest"]


def unresolved_comments(pr: dict[str, Any]) -> list[dict[str, Any]]:
    """Threads inline sin resolver + comentarios generales humanos posteriores al último commit."""
    found: list[dict[str, Any]] = []
    for thread in pr["reviewThreads"]["nodes"]:
        if not thread["isResolved"]:
            found += [comment("inline", c) for c in thread["comments"]["nodes"]]
    commits = pr["commits"]["nodes"]
    last_commit = commits[-1]["commit"]["committedDate"] if commits else ""
    for c in pr["comments"]["nodes"]:
        if c.get("createdAt", "") > last_commit and not is_agent(c):
            found.append(comment("general", c))
    for r in pr["reviews"]["nodes"]:
        if (r.get("body") or "").strip() and r.get("createdAt", "") > last_commit and not is_agent(r):
            found.append(comment("review", r))
    return found


def mergeable(repo: Path, owner: str, name: str, number: int, pr: dict[str, Any]) -> str:
    state = pr.get("mergeable") or "UNKNOWN"
    for _ in range(2):
        if state != "UNKNOWN":
            break
        time.sleep(3)
        state = pr_state(repo, owner, name, number).get("mergeable") or "UNKNOWN"
    return state


def signed(text: str) -> str:
    helper = os.environ.get("SECRETARY_SIGNATURE") or str(Path.home() / ".claude/scripts/sec-signature.sh")

    def part(flag: str) -> str:
        if not os.access(helper, os.X_OK):
            return ""
        out = subprocess.run([helper, SIGNATURE_CONTEXT, flag], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else ""

    mark, footer = part("--mark"), part("--footer")
    body = f"> 🤖 **wiki-update**\n\n{text}"
    if mark:
        body = f"{mark}\n{body}"
    if footer:
        body = f"{body}\n\n---\n{footer}"
    return body


def merge(repo: Path, owner: str, name: str, number: int, title: str) -> None:
    try:
        gh(repo, "pr", "merge", str(number), "--merge")
    except GhError:
        # Fallback documentado en W0 (499, worktree de main): merge por API.
        gh(repo, "api", "-X", "PUT", f"repos/{owner}/{name}/pulls/{number}/merge",
           "-f", "merge_method=merge", "-f", f"commit_title={title} (#{number})")


def provenance(repo: Path, number: int) -> list[str]:
    rows: list[str] = []
    current = ""
    for line in gh(repo, "pr", "diff", str(number)).splitlines():
        if line.startswith("+++ b/"):
            current = line[len("+++ b/"):]
        elif re.match(r"^\+#{2,3} ", line) and "memory/" in current:
            rows.append(f"{current}\t{line[1:]}\tPR#{number}")
    return rows


def run(repo: Path, dry: bool, prov_out: Path | None) -> dict[str, Any]:
    repo_id = json.loads(gh(repo, "repo", "view", "--json", "owner,name"))
    owner, name = repo_id["owner"]["login"], repo_id["name"]
    prs = json.loads(gh(repo, "pr", "list", "--state", "open", "--limit", "200",
                        "--json", "number,headRefName,title"))
    auto = sorted((p for p in prs if AUTO_RE.match(p["headRefName"])), key=lambda p: p["headRefName"])
    result: dict[str, Any] = {"repo": f"{owner}/{name}", "dry_run": dry, "open_prs": len(prs),
                              "candidates": len(auto), "merged": [], "closed_superseded": [],
                              "needs_llm": [], "failed": []}

    def entry(p: dict[str, Any], **extra: Any) -> dict[str, Any]:
        return {"number": p["number"], "branch": p["headRefName"], "title": p["title"], **extra}

    # Encadenadas: solo el más reciente de cada prefijo es candidato; los viejos se cierran.
    superseded: dict[int, int] = {}
    for prefix in CHAINED:
        group = [p for p in auto if p["headRefName"].startswith(prefix + "/")]
        for old in group[:-1]:
            superseded[old["number"]] = group[-1]["number"]

    prov_rows: list[str] = []
    for p in auto:
        n = p["number"]
        try:
            pr = pr_state(repo, owner, name, n)
            pending = unresolved_comments(pr)
            if n in superseded:
                newest = superseded[n]
                if pending:
                    result["needs_llm"].append(entry(p, reason="superado-con-comentarios",
                                                     superseded_by=newest, comments=pending))
                    continue
                if not dry:
                    gh(repo, "pr", "close", str(n), "--comment",
                       signed(f"Superado por #{newest}; cierro para evitar conflicto."))
                result["closed_superseded"].append(entry(p, superseded_by=newest))
                continue
            if pending:
                result["needs_llm"].append(entry(p, reason="comentarios", comments=pending))
                continue
            state = mergeable(repo, owner, name, n, pr)
            if state == "CONFLICTING":
                result["needs_llm"].append(entry(p, reason="conflicto", comments=[]))
                continue
            if not dry:
                try:
                    merge(repo, owner, name, n, p["title"])
                except GhError as exc:
                    if pr_state(repo, owner, name, n).get("mergeable") == "CONFLICTING":
                        result["needs_llm"].append(entry(p, reason="conflicto", comments=[]))
                    else:
                        result["failed"].append(entry(p, error=str(exc)[:500]))
                    continue
            result["merged"].append(entry(p, mergeable=state))
            if prov_out is not None:
                prov_rows += provenance(repo, n)
        except GhError as exc:
            result["failed"].append(entry(p, error=str(exc)[:500]))
    if prov_out is not None:
        prov_out.write_text("".join(row + "\n" for row in prov_rows))
        result["prov_rows"] = len(prov_rows)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.environ.get("SECRETARY_INSTANCE") or str(Path.home() / ".secretary"))
    ap.add_argument("--prov-out", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        result = run(Path(args.repo), args.dry_run, args.prov_out)
    except GhError as exc:
        print(f"wiki-w0: {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
