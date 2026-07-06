"""Typer entrypoint for the secretary CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from secretary import __version__
from secretary.acc import fold_action
from secretary.build_root import run_wiki_build
from secretary.config import all_resolved_paths, config_show_dict, resolve_path_key
from secretary.fresh import (
    MODULE_ALIASES,
    format_json_report,
    format_markdown_heartbeat,
    fresh_all,
    fresh_module,
)
from secretary.recall import format_json, format_table, search
from secretary.status import post_status
from secretary.modules import (
    health_for_module,
    health_rows,
    list_modules,
    load_contract,
    merge_contract,
)
from secretary.validate import VALIDATORS, run_all, run_validator

console = Console()
app = typer.Typer(
    name="secretary",
    help="Atomic operations for secretary — config, status, validate, recall, wiki.",
    no_args_is_help=True,
)

config_app = typer.Typer(help="Instance config and path resolution.")
wiki_app = typer.Typer(help="Wiki build and related ops.")
acc_app = typer.Typer(help="Action ledger operations.")
routines_app = typer.Typer(help="Scheduled routines router and LaunchAgent setup.")
modules_app = typer.Typer(help="Module contracts and health (spec 015).")
contract_app = typer.Typer(help="Read or update module contract.yaml.")
dream_app = typer.Typer(help="sec-dream deterministic collection (spec 020).")
app.add_typer(config_app, name="config")
app.add_typer(wiki_app, name="wiki")
app.add_typer(acc_app, name="acc")
app.add_typer(routines_app, name="routines")
app.add_typer(modules_app, name="modules")
app.add_typer(dream_app, name="dream")
modules_app.add_typer(contract_app, name="contract")


class OutputFormat(str, Enum):
    table = "table"
    json = "json"


class FreshFormat(str, Enum):
    table = "table"
    json = "json"
    markdown = "markdown"


FRESH_MODULES = ("mail", "meeting", "reuniones", "drive", "whatsapp", "all")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", help="Show version and exit."),
    ] = None,
) -> None:
    if version:
        console.print(f"secretary {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@config_app.command("show")
def config_show(
    yaml_out: Annotated[
        bool,
        typer.Option("--yaml", help="Emit raw YAML instead of JSON."),
    ] = False,
) -> None:
    """Dump resolved instance config (paths absolute)."""
    data = config_show_dict()
    if yaml_out:
        console.print(yaml.dump(data, allow_unicode=True, default_flow_style=False))
    else:
        console.print(json.dumps(data, ensure_ascii=False, indent=2))


@config_app.command("path")
def config_path(
    key: Annotated[str, typer.Argument(help="Dotted path key, e.g. mail.memory")],
) -> None:
    """Resolve a path key to an absolute filesystem path."""
    try:
        path = resolve_path_key(key)
    except KeyError as exc:
        console.print(f"[red]Error:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    console.print(str(path))


@app.command("paths")
def paths_list() -> None:
    """List all configured extractor/wiki paths (resolved)."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("key", style="cyan")
    table.add_column("path")
    table.add_column("", justify="center", width=3)
    for key, path in sorted(all_resolved_paths().items()):
        mark = "✓" if path.exists() else "·"
        table.add_row(key, str(path), mark)
    console.print(table)


@app.command("status")
def status_cmd(
    emoji: Annotated[str, typer.Argument(help="✅ 🔄 ⏳ 🚫")],
    ref: Annotated[str, typer.Argument(help="#N del brief o acc-id (vacío si no aplica)")],
    note: Annotated[str, typer.Argument(help="Nota del avance")],
) -> None:
    """Persist progress on today's brief (atomic sec-status)."""
    try:
        _, summary = post_status(emoji, ref, note)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        console.print(f"[red]secretary status:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    console.print(summary)


@app.command("validate")
def validate_cmd(
    target: str = typer.Argument(
        "",
        help=f"Validator: {', '.join(VALIDATORS)} — omit for all.",
    ),
) -> None:
    """Run instance CI validators from scripts/ci/."""
    if target == "":
        rc = run_all()
    elif target not in VALIDATORS:
        console.print(
            f"[red]Error:[/red] validador desconocido {target!r}. "
            f"Opciones: {', '.join(VALIDATORS)}",
            stderr=True,
        )
        raise typer.Exit(2)
    else:
        rc = run_validator(target)
    raise typer.Exit(rc)


@wiki_app.command("build")
def wiki_build() -> None:
    """Build wiki HTML via engine build.py (staged instance layout)."""
    try:
        rc = run_wiki_build()
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    raise typer.Exit(rc)


@app.command("fresh")
def fresh_cmd(
    module: Annotated[
        str,
        typer.Argument(help="mail | meeting | reuniones | drive | whatsapp | all"),
    ],
    out_fmt: FreshFormat = typer.Option(
        FreshFormat.table, "--format", "-f", help="Output format."
    ),
    local: Annotated[
        bool,
        typer.Option("--local", help="Include working-tree diff vs origin/main."),
    ] = False,
) -> None:
    """Paso 0 fresh-first — main, auto-pr, fuente viva por extractor."""
    mod = module.lower()
    if mod not in FRESH_MODULES:
        console.print(
            f"[red]Error:[/red] módulo desconocido {module!r}. "
            f"Opciones: {', '.join(FRESH_MODULES)}",
            stderr=True,
        )
        raise typer.Exit(2)
    try:
        from secretary.fresh import _gh_repo, _now_iso, git_fetch

        git_fetch()
        if mod == "all":
            data = fresh_all(local=local)
        else:
            canonical = MODULE_ALIASES.get(mod, mod)
            report = fresh_module(canonical, local=local)
            data = {
                "generated_at": _now_iso(),
                "base": "origin/main",
                "repo": _gh_repo(),
                **report.to_dict(),
            }
    except ValueError as exc:
        console.print(f"[red]secretary fresh:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc

    if out_fmt == FreshFormat.json:
        console.print(format_json_report(data))
    elif out_fmt == FreshFormat.markdown:
        if mod != "all":
            data = fresh_all(local=local)
        console.print(format_markdown_heartbeat(data), end="")
    else:
        format_table_report(data)


def format_table_report(data: dict) -> None:
    """Render human-readable freshness table."""
    from secretary.fresh import _now_iso

    modules = data.get("modules")
    if modules is None and "module" in data:
        modules = {data["module"]: data}
    console.print(
        f"[dim]base[/dim] {data.get('base', 'origin/main')} · "
        f"[dim]at[/dim] {data.get('generated_at', _now_iso())}"
    )
    for name, mod in (modules or {}).items():
        if not isinstance(mod, dict):
            continue
        console.print(f"\n[bold cyan]{name}[/bold cyan]")
        main = mod.get("main") or {}
        if main.get("estado_md"):
            ed = main["estado_md"]
            console.print(
                f"  [green]main[/green] estado → {ed.get('updated') or ed.get('fecha') or '—'}"
            )
        if main.get("last_merge"):
            lm = main["last_merge"]
            console.print(f"  [green]main[/green] merge → {lm.get('timestamp', '—')}")
        for pr in mod.get("auto_pr") or []:
            nfiles = len(pr.get("files") or [])
            console.print(
                f"  [yellow]auto-pr[/yellow] #{pr.get('number')} "
                f"{pr.get('branch')} ({nfiles} arch extractores)"
            )
        fv = mod.get("fuente_viva") or {}
        if name == "mail" and fv.get("latest_email"):
            le = fv["latest_email"]
            console.print(
                f"  [blue]fuente-viva[/blue] último correo → "
                f"{le.get('date', le.get('raw', '—'))}"
            )
        elif name == "meeting":
            docs = fv.get("tactiq_pending_docs") or []
            console.print(f"  [blue]fuente-viva[/blue] Tactiq docs en raíz → {len(docs)}")
            if fv.get("last_summary_main"):
                ls = fv["last_summary_main"]
                console.print(
                    f"  [blue]fuente-viva[/blue] último resumen main → {ls.get('path', '—')}"
                )
        elif name in ("drive", "whatsapp"):
            date = fv.get("estado_md_date")
            if not date and fv.get("estado_md"):
                date = (fv["estado_md"] or {}).get("fecha")
            if date:
                console.print(f"  [blue]fuente-viva[/blue] estado.md → {date}")
        if mod.get("working"):
            console.print(f"  [magenta]working[/magenta] {mod['working']}")


@app.command("recall")
def recall_cmd(
    query: Annotated[str, typer.Argument(help="Search term or phrase")],
    out_fmt: OutputFormat = typer.Option(
        OutputFormat.table, "--format", "-f", help="Output format."
    ),
    limit: Annotated[int, typer.Option("--limit", help="Max hits.")] = 40,
) -> None:
    """Deterministic memory search (sec-recall step 0)."""
    hits = search(query, limit=limit)
    if out_fmt == OutputFormat.json:
        console.print(format_json(hits))
    else:
        if not hits:
            console.print(f"[dim]Sin coincidencias para[/dim] {query!r}")
            raise typer.Exit(0)
        console.print(format_table(hits))


@acc_app.command("fold")
def acc_fold(
    acc_id: Annotated[str, typer.Argument(help="acc-YYYYMMDD-NNN")],
    evidencia: Annotated[str, typer.Argument(help="ej. pr:owner/repo#N")],
    cerrado: Annotated[
        Optional[str],
        typer.Argument(help="YYYY-MM-DD (default: hoy)"),
    ] = None,
) -> None:
    """Fold canonical action closure into acciones.md."""
    try:
        msg = fold_action(acc_id, evidencia, cerrado=cerrado)
    except (FileNotFoundError, LookupError, ValueError) as exc:
        console.print(f"[red]secretary acc fold:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    console.print(msg)


@routines_app.command("setup")
def routines_setup() -> None:
    """Interactive wizard: router (claude-scheduled | cursor-cron | api-cron), schedule, LaunchAgents."""
    from secretary.routines.setup import run_setup

    raise typer.Exit(run_setup())


@dream_app.command("collect")
def dream_collect(
    write_collect: Annotated[
        bool, typer.Option("--write-collect", help="Also write a collect/ snapshot (gitignored).")
    ] = False,
) -> None:
    """Run the instance's deterministic sec-dream Phase 1 gather (scripts/dream/collect.py)."""
    from secretary.dream import run_collect

    raise typer.Exit(run_collect(write_collect=write_collect))


@modules_app.command("list")
def modules_list(
    out_fmt: OutputFormat = typer.Option(
        OutputFormat.table, "--format", "-f", help="Output format."
    ),
) -> None:
    """List extractors and loops with contract metadata."""
    items = list_modules()
    if out_fmt == OutputFormat.json:
        console.print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    table = Table(title="Modules")
    table.add_column("id")
    table.add_column("plane")
    table.add_column("kind")
    table.add_column("routine")
    for item in items:
        table.add_row(
            item["id"],
            item.get("plane", "—"),
            str(item.get("kind") or ("missing" if item.get("missing_contract") else "—")),
            str(item.get("routine") or "—"),
        )
    console.print(table)


@modules_app.command("health")
def modules_health(
    module: Annotated[
        Optional[str],
        typer.Option("--module", "-m", help="Filter to one module id."),
    ] = None,
    out_fmt: OutputFormat = typer.Option(
        OutputFormat.table, "--format", "-f", help="Output format."
    ),
) -> None:
    """Audit contract freshness and loop success criteria."""
    try:
        if module:
            data = health_for_module(module)
            rows = data.get("criteria") or []
        else:
            rows = health_rows()
            data = None
    except (FileNotFoundError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        console.print(f"[red]secretary modules health:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc

    if out_fmt == OutputFormat.json:
        if module:
            console.print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            console.print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    table = Table(title="Module health")
    table.add_column("module")
    table.add_column("kind")
    table.add_column("health")
    table.add_column("gap")
    for r in rows:
        table.add_row(
            str(r.get("module") or r.get("id") or "—"),
            str(r.get("kind") or "—"),
            str(r.get("health") or "—"),
            str(r.get("gap") or "—"),
        )
    console.print(table)


@contract_app.command("get")
def modules_contract_get(
    module_id: Annotated[str, typer.Argument(help="Module id, e.g. mail or job-search")],
    out_fmt: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Return full contract.yaml for a module."""
    try:
        contract = load_contract(module_id)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        console.print(f"[red]secretary modules contract get:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    if out_fmt == OutputFormat.json:
        console.print(json.dumps(contract, ensure_ascii=False, indent=2))
    else:
        console.print(yaml.dump(contract, allow_unicode=True, default_flow_style=False))


@contract_app.command("put")
def modules_contract_put(
    module_id: Annotated[str, typer.Argument(help="Module id")],
    patch_file: Annotated[
        Optional[Path],
        typer.Option("--file", help="YAML/JSON patch file (shallow merge)."),
    ] = None,
) -> None:
    """Admin update — shallow-merge patch into contract.yaml (human gate)."""
    if patch_file is None:
        console.print("[red]Error:[/red] --file required", stderr=True)
        raise typer.Exit(2)
    text = patch_file.read_text(encoding="utf-8")
    try:
        patch = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        console.print(f"[red]YAML inválido:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    if not isinstance(patch, dict):
        console.print("[red]Error:[/red] patch debe ser un objeto YAML/JSON", stderr=True)
        raise typer.Exit(1)
    try:
        merged = merge_contract(module_id, patch)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        console.print(f"[red]secretary modules contract put:[/red] {exc}", stderr=True)
        raise typer.Exit(1) from exc
    console.print(json.dumps({"ok": True, "module": module_id, "contract": merged}, ensure_ascii=False))


def run() -> None:
    app()


if __name__ == "__main__":
    run()
