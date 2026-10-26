#!/usr/bin/env python3
"""Estado determinista del latido (sec-heartbeat, pieza 5 de n5).

Lo invoca `sec-heartbeat-state.sh`; no se usa suelto. Junta en un `latest.md`:

- inventario git/PR por repo (allowlist `dispatch.executor.repos` + repos Cowork de acc abiertas),
- tabla acc ↔ git con su validación (modelo `heartbeat-match-model.md`),
- delta contra el snapshot anterior (`state.json`),
- pendiente humano por deadline, calendario hoy ±1 d, brief abierto,
- frescura de extractoras copiada tal cual.

Deja la sección `## Lectura` vacía para las 3–5 líneas que escribe la sesión.
Escribe `latest.md` y `state.json` en `--out-dir` e imprime un resumen de una línea.
Solo lee: no hace git fetch/pull, no cierra acciones, no escribe fuera de `--out-dir`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secretary.acc import parse_ledger  # noqa: E402
from secretary.config import (  # noqa: E402
    dispatch_executor_repos,
    flatten_paths,
    instance_root,
    load_config,
)

ACC_RE = re.compile(r"acc-\d{8}-\d+")
LEDGER_KEY_RE = re.compile(r"^extractors\.[^.]+\.memory$")
LECTURA_PLACEHOLDER = "<!-- lectura: pendiente (3–5 líneas, las escribe la sesión) -->"

# Estados vigentes de los ledgers (spec 007 + variantes del ledger de WhatsApp).
OPEN_STATES = {
    "abierta": "○ abierta",
    "pendiente": "○ pendiente",
    "en-curso": "🔄 en-curso",
    "en": "🔄 en-curso",  # "en curso" con espacio: parse_ledger toma la primera palabra
    "en-progreso": "🔄 en-curso",
    "en_progreso": "🔄 en-curso",
    "parcial": "🔄 parcial",
    "bloqueada": "⏳ bloqueada",
    "reagendado": "○ reagendado",
}
# Filas loose-acc en la tabla: dueño mía/compartida y deadline en esta ventana.
LOOSE_ACC_PAST_DAYS = 14
LOOSE_ACC_NEXT_DAYS = 7
PENDING_NEXT_DAYS = 3
TITLE_MAX = 80
LEGEND = (
    "**Leyenda:** match — 🔗 linked · 📋 loose-acc · 🌿 loose-git · · informativo · "
    "estado — ○ abierta · 🔄 en-curso · ✅ hecha · ⏳ caducada"
)


def run(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def trunc(text: str, n: int = TITLE_MAX) -> str:
    text = " ".join((text or "").split()).replace("|", "/")
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def slug(repo: str) -> str:
    return repo.split("/", 1)[-1]


# ---------------------------------------------------------------- acciones


def load_open_actions(cfg: dict, inst: Path) -> tuple[dict[str, dict], dict[str, dict], list[str]]:
    """(open, closed, notes). Each value: fields + estado + ledger (path relativo)."""
    notes: list[str] = []
    latest: dict[str, dict] = {}
    keys = sorted(k for k in flatten_paths(cfg.get("paths") or {}) if LEDGER_KEY_RE.match(k))
    for key in keys:
        rel = flatten_paths(cfg["paths"])[key]
        ledger = (inst / rel / "acciones.md").resolve()
        if not ledger.is_file():
            continue
        try:
            _, blocks = parse_ledger(ledger.read_text(encoding="utf-8"))
        except OSError as exc:
            notes.append(f"no se pudo leer {ledger.relative_to(inst)}: {exc}")
            continue
        rel_ledger = str(ledger.relative_to(inst))
        for b in blocks:
            if b.irregular:
                continue
            entry = latest.setdefault(b.acc_id, {"ledger": rel_ledger, "fields": {}})
            if not b.is_update:
                entry["fields"].update(b.fields)
            elif "estado_nuevo" in b.fields:
                entry["fields"]["estado"] = b.fields["estado_nuevo"]
    open_, closed = {}, {}
    for acc_id, entry in latest.items():
        estado = (entry["fields"].get("estado") or "").split()
        estado = estado[0] if estado else ""
        entry["estado"] = estado
        (open_ if estado in OPEN_STATES else closed)[acc_id] = entry
    return open_, closed, notes


def parse_deadline(value: str | None) -> date | None:
    m = re.match(r"\d{4}-\d{2}-\d{2}", value or "")
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(0))
    except ValueError:
        return None


def acc_title(entry: dict) -> str:
    f = entry["fields"]
    return f.get("accion") or f.get("titulo") or "(sin accion)"


# ---------------------------------------------------------------- git / gh


def repo_list(cfg: dict, open_actions: dict[str, dict]) -> tuple[list[dict], list[str]]:
    notes: list[str] = []
    repos = dispatch_executor_repos(cfg)
    have = {slug(r["repo"]) for r in repos}
    cowork = Path(os.environ.get("SECRETARY_COWORK_ROOT", Path.home() / "Cowork"))
    workspaces = sorted({(e["fields"].get("workspace") or "").strip() for e in open_actions.values()} - {""})
    for ws in workspaces:
        if f"cowork-{ws}" in have:
            continue
        path = cowork / ws
        if not (path / ".git").exists():
            continue
        rc, out, _ = run(["git", "-C", str(path), "remote", "get-url", "origin"])
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", out) if rc == 0 else None
        if not m:
            notes.append(f"workspace {ws}: {path} sin remoto GitHub; fuera del inventario")
            continue
        repos.append({"repo": m.group(1), "path": str(path), "via": f"workspace {ws}"})
        have.add(slug(m.group(1)))
    return repos, notes


def inventory(entry: dict) -> dict:
    repo, path = entry["repo"], entry["path"]
    inv: dict = {"repo": repo, "path": path, "errors": [], "prs": [], "branches": []}
    if Path(path, ".git").exists():
        _, out, _ = run(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"])
        inv["rama"] = out.strip() or "?"
        rc, out, _ = run(["git", "-C", path, "status", "--porcelain"])
        lines = [ln for ln in out.splitlines() if ln.strip()] if rc == 0 else []
        inv["dirty"] = sum(1 for ln in lines if not ln.startswith("??"))
        inv["untracked"] = sum(1 for ln in lines if ln.startswith("??"))
        _, out, _ = run(["git", "-C", path, "worktree", "list", "--porcelain"])
        inv["worktrees"] = max(0, out.count("\nworktree ") + out.startswith("worktree ") - 1)
        rc, out, _ = run(["git", "-C", path, "rev-list", "--left-right", "--count", "@{u}...HEAD"])
        inv["behind_ahead"] = tuple(int(x) for x in out.split()) if rc == 0 and out.split() else None
        _, out, _ = run(["git", "-C", path, "for-each-ref", "refs/heads", "--format=%(refname:short)"])
        inv["branches"] = [b for b in out.splitlines() if b.strip()]
    else:
        inv["errors"].append(f"sin checkout local en {path}")
    rc, out, err = run(
        ["gh", "pr", "list", "-R", repo, "--state", "open", "--limit", "200",
         "--json", "number,title,headRefName,body,url,isDraft,updatedAt"],
        timeout=90,
    )
    if rc == 0:
        try:
            inv["prs"] = sorted(json.loads(out or "[]"), key=lambda p: p["number"])
        except json.JSONDecodeError:
            inv["errors"].append("gh pr list: JSON inválido")
    else:
        inv["errors"].append(f"gh pr list falló: {trunc(err, 120)}")
    return inv


# ---------------------------------------------------------------- match


def build_match(invs: list[dict], open_a: dict, closed_a: dict, today: date) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    linked_refs: dict[str, list[dict]] = {}
    for inv in invs:
        pr_heads = {p["headRefName"] for p in inv["prs"]}
        for pr in inv["prs"]:
            ids = set(ACC_RE.findall(" ".join([pr["headRefName"], pr["title"], pr.get("body") or ""])))
            ids_open = sorted(i for i in ids if i in open_a)
            ref = {"repo": inv["repo"], "kind": "pr", "number": pr["number"], "url": pr["url"],
                   "draft": pr.get("isDraft"), "text": " ".join([pr["headRefName"], pr["title"], pr.get("body") or ""]),
                   "title": pr["title"], "head": pr["headRefName"]}
            for i in ids_open:
                linked_refs.setdefault(i, []).append(ref)
            if not ids_open:
                closed_ids = sorted(i for i in ids if i in closed_a)
                nota = f"cita {', '.join(closed_ids)} (cerrada)" if closed_ids else "sin acc-id"
                rows.append({"acc": "—", "title": pr["title"], "repo": slug(inv["repo"]),
                             "ref": f"[PR #{pr['number']}]({pr['url']})" + (" draft" if pr.get("isDraft") else ""),
                             "estado": "—", "evidencia": f"gh pr list ({slug(inv['repo'])})",
                             "match": "🌿 loose-git", "nota": nota, "pr": f"{inv['repo']}#{pr['number']}"})
        for br in inv["branches"]:
            if br in pr_heads:
                continue
            for i in sorted(set(ACC_RE.findall(br))):
                if i in open_a:
                    linked_refs.setdefault(i, []).append(
                        {"repo": inv["repo"], "kind": "branch", "name": br, "text": br})

    validation: list[str] = []
    downgraded: list[str] = []
    acc_rows: list[dict] = []
    for acc_id in sorted(linked_refs):
        refs = [r for r in linked_refs[acc_id] if acc_id in r["text"]]  # validación literal
        entry = open_a[acc_id]
        if not refs:
            downgraded.append(acc_id)
            continue
        ref_txt = " · ".join(
            f"[PR #{r['number']}]({r['url']})" if r["kind"] == "pr" else f"rama `{r['name']}`" for r in refs)
        evid = entry["ledger"] + " + " + " + ".join(
            f"gh pr view ({r['repo']}#{r['number']})" if r["kind"] == "pr" else f"git branch ({slug(r['repo'])})"
            for r in refs)
        acc_rows.append({"acc": acc_id, "title": acc_title(entry),
                         "repo": ", ".join(sorted({slug(r["repo"]) for r in refs})), "ref": ref_txt,
                         "estado": OPEN_STATES[entry["estado"]], "evidencia": evid, "match": "🔗 linked",
                         "nota": deadline_note(entry, today)})
    linked_ids = {r["acc"] for r in acc_rows}

    lo, hi = today - timedelta(days=LOOSE_ACC_PAST_DAYS), today + timedelta(days=LOOSE_ACC_NEXT_DAYS)
    for acc_id in sorted(open_a):
        if acc_id in linked_ids:
            continue
        entry = open_a[acc_id]
        dueno = (entry["fields"].get("dueño") or "").strip().lower()
        dl = parse_deadline(entry["fields"].get("deadline"))
        if acc_id not in downgraded and not (dueno in {"mía", "mia", "compartida"} and dl and lo <= dl <= hi):
            continue
        nota = deadline_note(entry, today)
        if acc_id in downgraded:
            nota = "bajada desde linked: el acc-id no aparece literal en la ref"
        acc_rows.append({"acc": acc_id, "title": acc_title(entry), "repo": "—", "ref": "—",
                         "estado": OPEN_STATES[entry["estado"]], "evidencia": entry["ledger"],
                         "match": "📋 loose-acc", "nota": nota})

    ids = [r["acc"] for r in acc_rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    validation.append(
        f"acc en la tabla: {len(ids)} (linked {len(linked_ids)}, loose-acc {len(ids) - len(linked_ids)}); "
        f"duplicados: {', '.join(dup) if dup else 0}")
    validation.append(
        f"linked con acc-id literal en rama o PR: {len(linked_ids)}/{len(linked_ids) + len(downgraded)}"
        + (f"; bajadas a loose-acc: {', '.join(downgraded)}" if downgraded else ""))
    return acc_rows + rows, validation


def deadline_note(entry: dict, today: date) -> str:
    dl = parse_deadline(entry["fields"].get("deadline"))
    dueno = entry["fields"].get("dueño") or "?"
    if not dl:
        return f"dueño {dueno}; sin deadline"
    delta = (dl - today).days
    when = "vence hoy" if delta == 0 else (f"vencida hace {-delta} d" if delta < 0 else f"vence en {delta} d")
    return f"dueño {dueno}; deadline {dl.isoformat()} ({when})"


# ---------------------------------------------------------------- otras fuentes


def calendar(cfg: dict, today: date) -> tuple[list[str], list[str]]:
    accounts = cfg.get("accounts") or {}
    lines, notes = [], []
    if not accounts:
        return ["(sin cuentas en `accounts`)"], notes
    frm, to = (today - timedelta(days=1)).isoformat(), (today + timedelta(days=2)).isoformat()
    for alias in sorted(accounts):
        rc, out, err = run(["gog", "calendar", "events", f"--account={accounts[alias]}", "--from", frm,
                            "--to", to, "--plain", "--max", "50", "--no-input"], timeout=60)
        if rc != 0:
            notes.append(f"calendario {alias}: gog falló ({trunc(err, 100)})")
            continue
        rows = [ln for ln in out.splitlines()[1:] if ln.strip()]
        lines.append(f"- {alias}: {len(rows)} eventos ({frm} → {to})")
        # TSV de gog: id, inicio, fin, resumen; el id no aporta a la lectura.
        lines.extend(f"  - {trunc(' · '.join(ln.split(chr(9))[1:]), 140)}" for ln in rows)
    return lines, notes


def brief(cfg: dict) -> tuple[list[str], list[str]]:
    b = cfg.get("brief") or {}
    if not b.get("repo") or not b.get("label"):
        return ["(sin `brief.repo`/`brief.label` en config)"], []
    rc, out, err = run(["gh", "issue", "list", "-R", b["repo"], "--label", b["label"], "--state", "open",
                        "--limit", "1", "--json", "number,title,url,comments"])
    if rc != 0:
        return [], [f"brief: gh issue list falló ({trunc(err, 100)})"]
    issues = json.loads(out or "[]")
    if not issues:
        return ["(sin brief abierto)"], []
    i = issues[0]
    comments = i.get("comments") or []
    lines = [f"- [brief #{i['number']}]({i['url']}) — {trunc(i['title'])} · {len(comments)} comentarios"]
    for c in comments[-5:]:
        first = next((ln for ln in (c.get("body") or "").splitlines()
                      if ln.strip() and not ln.lstrip().startswith("<!--")), "")
        lines.append(f"  - {c.get('createdAt', '?')} {c.get('author', {}).get('login', '?')}: {trunc(first, 140)}")
    return lines, []


# ---------------------------------------------------------------- render


def table(rows: list[dict]) -> list[str]:
    out = ["| acc-id | título | repo | ref | estado | evidencia | match | nota |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| " + " | ".join([r["acc"], trunc(r["title"]), r["repo"], r["ref"], r["estado"],
                                       r["evidencia"], r["match"], trunc(r["nota"], 120)]) + " |")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--prev-state", default="")
    ap.add_argument("--freshness-file", required=True)
    ap.add_argument("--slot", required=True)
    ap.add_argument("--source", default="scheduled")
    args = ap.parse_args()

    cfg = load_config()
    inst = instance_root()
    tzname = cfg.get("timezone") or "UTC"
    now = datetime.now(ZoneInfo(tzname))
    today = now.date()
    notes: list[str] = []

    open_a, closed_a, n = load_open_actions(cfg, inst)
    notes += n
    repos, n = repo_list(cfg, open_a)
    notes += n
    invs = [inventory(r) for r in repos]
    for inv in invs:
        notes += [f"{slug(inv['repo'])}: {e}" for e in inv["errors"]]
    rows, validation = build_match(invs, open_a, closed_a, today)
    validation.insert(0, f"repos inventariados: {sum(1 for i in invs if not i['errors'])}/{len(repos)} sin error")

    # delta contra el snapshot anterior
    prs_now = sorted(f"{i['repo']}#{p['number']}" for i in invs for p in i["prs"])
    linked_now = sorted(r["acc"] for r in rows if r["match"] == "🔗 linked")
    state_now = {"timestamp": now.isoformat(timespec="minutes"), "prs": prs_now, "linked": linked_now,
                 "acc_estado": {k: v["estado"] for k, v in open_a.items()}}
    delta: list[str] = []
    prev = {}
    if args.prev_state and Path(args.prev_state).is_file():
        try:
            prev = json.loads(Path(args.prev_state).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            notes.append("state.json previo ilegible; delta como baseline")
    if prev:
        new_prs = sorted(set(prs_now) - set(prev.get("prs", [])))
        gone_prs = sorted(set(prev.get("prs", [])) - set(prs_now))
        prev_open = prev.get("acc_estado", {})
        closed_now = sorted(set(prev_open) - set(open_a))
        changed = sorted(k for k in open_a if k in prev_open and prev_open[k] != open_a[k]["estado"])
        new_acc = sorted(set(open_a) - set(prev_open))
        delta.append(f"- base: snapshot {prev.get('timestamp', '?')}")
        delta.append(f"- PRs nuevos ({len(new_prs)}): {', '.join(new_prs) or '—'}")
        delta.append(f"- PRs que ya no están abiertos ({len(gone_prs)}): {', '.join(gone_prs) or '—'}")
        delta.append(f"- acc nuevas abiertas ({len(new_acc)}): {', '.join(new_acc[:20]) or '—'}"
                     + (" …" if len(new_acc) > 20 else ""))
        delta.append(f"- acc cerradas o fuera del ledger ({len(closed_now)}): {', '.join(closed_now[:20]) or '—'}"
                     + (" …" if len(closed_now) > 20 else ""))
        delta.append("- cambios de estado: " + (", ".join(
            f"{k} {prev_open[k]}→{open_a[k]['estado']}" for k in changed) or "—"))
    else:
        delta.append("- baseline inicial (sin snapshot previo)")

    loose_acc = [r["acc"] for r in rows if r["match"] == "📋 loose-acc"]
    loose_git = [r for r in rows if r["match"] == "🌿 loose-git"]
    linked_all = set(linked_now)
    by_ws: dict[str, int] = {}
    for k, v in open_a.items():
        if k not in linked_all:
            ws = v["fields"].get("workspace") or "?"
            by_ws[ws] = by_ws.get(ws, 0) + 1

    pending = []
    horizon = today + timedelta(days=PENDING_NEXT_DAYS)
    for k, v in open_a.items():
        dl = parse_deadline(v["fields"].get("deadline"))
        dueno = (v["fields"].get("dueño") or "").strip().lower()
        if dueno in {"mía", "mia"} and dl and today - timedelta(days=LOOSE_ACC_PAST_DAYS) <= dl <= horizon:
            pending.append((dl, k, v))
    pending.sort()

    cal_lines, n = calendar(cfg, today)
    notes += n
    brief_lines, n = brief(cfg)
    notes += n
    freshness = Path(args.freshness_file).read_text(encoding="utf-8").rstrip()

    md: list[str] = [
        "# Heartbeat",
        f"- timestamp: {now:%Y-%m-%d %H:%M} ({tzname})",
        f"- slot: {args.slot}",
        f"- source: {args.source}",
        "- generator: sec-heartbeat-state.sh",
        "",
        "## Lectura",
        LECTURA_PLACEHOLDER,
        "",
        "## Match acc↔git",
        *table(rows),
        "",
        LEGEND,
        "",
        f"Filas loose-acc: acc abiertas con dueño mía/compartida y deadline entre hoy −{LOOSE_ACC_PAST_DAYS} d "
        f"y hoy +{LOOSE_ACC_NEXT_DAYS} d. El resto cuenta en Huérfanos.",
        "",
        "Doctrina: `canon/operational/routines/heartbeat-match-model.md`",
        "",
        "### Validación",
        *[f"- {v}" for v in validation],
        "",
        "## Delta vs previous beat",
        *delta,
        "",
        "## Orphans",
        f"- loose-acc en tabla ({len(loose_acc)}): {', '.join(loose_acc) or '—'}",
        f"- acc abiertas sin ref git, por workspace: "
        + (", ".join(f"{k} {v}" for k, v in sorted(by_ws.items())) or "—"),
        f"- loose-git ({len(loose_git)}): " + (", ".join(r["pr"] for r in loose_git) or "—"),
        "",
        "## Git por repo",
        "| repo | rama | ↓/↑ upstream | dirty | untracked | worktrees | PRs abiertos |",
        "|---|---|---|---|---|---|---|",
    ]
    for inv in invs:
        ba = inv.get("behind_ahead")
        md.append(f"| {slug(inv['repo'])} | {inv.get('rama', '—')} | "
                  f"{f'{ba[0]}/{ba[1]}' if ba else '—'} | {inv.get('dirty', '—')} | {inv.get('untracked', '—')} | "
                  f"{inv.get('worktrees', '—')} | {len(inv['prs'])} |")
    # Salida de extractor-freshness.sh tal cual; trae su propio encabezado.
    if not freshness.startswith("## Frescura extractoras"):
        freshness = "## Frescura extractoras\n" + freshness
    md += ["", freshness, "", "## Pending human"]
    md += [f"- {k} ({dl.isoformat()}): {trunc(acc_title(v))} — {v['ledger']}" for dl, k, v in pending] or [
        f"- sin acc mía con deadline entre hoy −{LOOSE_ACC_PAST_DAYS} d y hoy +{PENDING_NEXT_DAYS} d"]
    md += ["", "## Calendario (hoy ±1 d)", *cal_lines, "", "## Brief abierto", *brief_lines, "",
           "## Operational notes"]
    md += [f"- {n}" for n in notes] or ["- sin fallas de fuentes en el script"]
    md.append("")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.md").write_text("\n".join(md), encoding="utf-8")
    (out_dir / "state.json").write_text(json.dumps(state_now, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(
        f"[sec-heartbeat-state] {out_dir / 'latest.md'} · repos={len(invs)} prs={len(prs_now)} "
        f"linked={len(linked_now)} loose-acc={len(loose_acc)} loose-git={len(loose_git)} "
        f"pendiente={len(pending)} notas={len(notes)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
