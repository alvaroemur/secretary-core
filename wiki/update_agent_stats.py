#!/usr/bin/env python3
"""update_agent_stats.py — Retroalimenta la wiki con PRs de desarrollo, heartbeat y métricas de rutinas.

Lee:
  - PRs de desarrollo de los repos de trabajo (vía GitHub CLI)
  - Métricas de ejecución en subsystem/routines/ (meta.json + metrics.jsonl)
  - Estado del heartbeat en subsystem/heartbeat/latest.md

Actualiza:
  - Artículos de temas relevantes con sus PRs de desarrollo (<!-- auto:desarrollo-git -->)
  - Perfil de Álvaro (personas/alvaro-mur.md) con la línea de tiempo de desarrollo Git (<!-- auto:actividad-desarrollo-git -->)
  - Artículos de módulos con métricas de corrida y acumulado mensual (<!-- auto:execution-metrics -->)
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_REPOS = [
    "alvaroemur/cowork-secretary",
    "alvaroemur/cowork-ennui",
    "alvaroemur/cowork-inspiro",
    "alvaroemur/doc2struct",
    "alvaroemur/secretary-core",
]

ROUTINE_TO_MODULE = {
    "wiki-update": "modulos/wiki-update.md",
    "sec-heartbeat": "modulos/sec-heartbeat.md",
    "dispatch-executor": "modulos/dispatch-executor.md",
    "housekeeping": "modulos/housekeeping.md",
    "tidy-up": "modulos/housekeeping.md",
    "revision-correo": "modulos/correo.md",
    "reuniones-update": "modulos/reuniones.md",
    "drive-crawler": "modulos/drive.md",
    "job-search-crawler": "modulos/job-search.md",
}

AUTO_BRANCH_PATTERNS = [
    r"^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-\d{8}-\d{4}$",
    r"^tidy-up-\d{8}-\d{4}$",
    r"^subsystem/.+/auto-\d{8}-\d{4}$",
]


def is_auto_pr(head_branch: str) -> bool:
    if not head_branch:
        return False
    return any(re.match(pattern, head_branch) for pattern in AUTO_BRANCH_PATTERNS)


def get_repos_from_config(instance_path: Path) -> list[str]:
    cfg_file = instance_path / ".secretary.yml"
    if not cfg_file.is_file():
        return DEFAULT_REPOS
    try:
        content = cfg_file.read_text(encoding="utf-8")
        # Parse simple YAML for dispatch.executor.repos
        repos = []
        in_executor_repos = False
        for line in content.splitlines():
            if "executor:" in line:
                in_executor_repos = True
                continue
            if in_executor_repos:
                if line.strip().startswith("- repo:"):
                    repo = line.split("- repo:")[1].strip().strip('"').strip("'")
                    if repo:
                        repos.append(repo)
                elif line and not line.startswith(" ") and not line.startswith("\t"):
                    in_executor_repos = False
        return repos or DEFAULT_REPOS
    except Exception:
        return DEFAULT_REPOS


def fetch_prs_for_repo(repo_slug: str) -> list[dict]:
    try:
        cmd = [
            "gh", "pr", "list",
            "--repo", repo_slug,
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,headRefName,state,url,mergedAt,createdAt,updatedAt"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        print(f"Advertencia: No se pudieron obtener PRs de {repo_slug}: {e}", file=sys.stderr)
        return []


def map_pr_to_topic(repo_slug: str, title: str, branch: str) -> str | None:
    text = f"{repo_slug} {title} {branch}".lower()
    
    if "doc2struct" in repo_slug or "doc2struct" in text:
        return "temas/doc2struct.md"
    
    if "cowork-ennui" in repo_slug:
        if any(k in text for k in ["clab-erp", "clab_erp", "erp-clab", "clab_presupuesto", "presupuesto", "conciliacion"]):
            return "temas/erp-clab.md"
        if any(k in text for k in ["alma", "plan-v", "plan_v"]):
            return "temas/plan-v.md"
        if any(k in text for k in ["aliantza", "optamine", "milagros"]):
            return "temas/inspiro-agents.md"
        if any(k in text for k in ["comuna-nacion", "nativas"]):
            return "temas/comuna-nacion.md"
        return "temas/ennui-dev.md"
    
    if "cowork-inspiro" in repo_slug:
        if any(k in text for k in ["aliantza", "optamine", "milagros"]):
            return "temas/inspiro-agents.md"
        if any(k in text for k in ["norte-compartido", "norte"]):
            return "temas/norte-compartido.md"
        return "temas/inspiro-agents.md"
    
    if "secretary-core" in repo_slug or "cowork-secretary" in repo_slug:
        return "temas/secretary.md"
    
    return None


def replace_or_insert_section(content: str, marker_name: str, new_block: str, fallback_header: str | None = None) -> str:
    start_tag = f"<!-- auto:{marker_name} start -->"
    end_tag = f"<!-- auto:{marker_name} end -->"
    pattern = re.compile(rf"{re.escape(start_tag)}.*?{re.escape(end_tag)}", re.DOTALL)
    
    wrapped = f"{start_tag}\n{new_block.strip()}\n{end_tag}"
    
    if pattern.search(content):
        return pattern.sub(wrapped, content)
    
    if fallback_header and fallback_header in content:
        parts = content.split(fallback_header, 1)
        return f"{parts[0]}{fallback_header}\n\n{wrapped}\n{parts[1]}"
    
    # Si no hay marcador ni header fallback, agregar antes de ## Véase también o al final
    if "\n## Véase también" in content:
        parts = content.split("\n## Véase también", 1)
        return f"{parts[0]}\n\n{wrapped}\n\n## Véase también{parts[1]}"
    
    return f"{content.rstrip()}\n\n{wrapped}\n"


def load_metrics_for_routine(instance_path: Path, routine_id: str, current_month: str) -> dict:
    meta_paths = [
        instance_path / "subsystem" / "routines" / "latest" / f"latest-{routine_id}.meta.json",
        instance_path / "subsystem" / "routines" / f"latest-{routine_id}.meta.json",
    ]
    latest_meta = None
    for p in meta_paths:
        if p.is_file():
            try:
                latest_meta = json.loads(p.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    metrics_paths = [
        instance_path / "subsystem" / "routines" / "metrics" / "metrics.jsonl",
        instance_path / "subsystem" / "routines" / "metrics.jsonl",
    ]
    
    monthly_runs = 0
    success_runs = 0
    total_cost = 0.0

    for mp in metrics_paths:
        if mp.is_file():
            try:
                for line in mp.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("routine_id") == routine_id:
                            started = record.get("started_at", "")
                            if started.startswith(current_month):
                                monthly_runs += 1
                                if record.get("status") == "success" or record.get("exit_code") == 0:
                                    success_runs += 1
                                cost = record.get("cost", {}).get("estimated_usd", 0.0)
                                if isinstance(cost, (int, float)):
                                    total_cost += cost
                    except Exception:
                        continue
                if monthly_runs > 0:
                    break
            except Exception:
                pass

    return {
        "latest": latest_meta,
        "monthly_runs": monthly_runs,
        "success_runs": success_runs,
        "total_cost": total_cost,
    }


def format_duration(ms: int | float | None) -> str:
    if ms is None:
        return "—"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60.0
    return f"{minutes:.1f} min"


def format_metrics_block(metrics: dict, current_month: str) -> str:
    lines = ["## Historial de Ejecución y Métricas"]
    latest = metrics.get("latest")
    if latest:
        started = latest.get("started_at", "")
        # Formato legible: YYYY-MM-DD HH:MM
        started_clean = started.replace("T", " ")[:16] if started else "desconocido"
        status = latest.get("status", "unknown")
        status_icon = "✅" if status == "success" or latest.get("exit_code") == 0 else "❌"
        duration_str = format_duration(latest.get("duration_ms"))
        cost = latest.get("cost", {}).get("estimated_usd")
        cost_str = f"${cost:.3f}" if isinstance(cost, (int, float)) else "$0.00"
        lines.append(f"- **Última corrida**: {started_clean} (Estado: {status_icon} `{status}`, Duración: {duration_str}, Costo: {cost_str})")
    else:
        lines.append("- **Última corrida**: Sin registro reciente")
        
    monthly_runs = metrics.get("monthly_runs", 0)
    if monthly_runs > 0:
        success_runs = metrics.get("success_runs", 0)
        success_rate = (success_runs / monthly_runs) * 100.0
        total_cost = metrics.get("total_cost", 0.0)
        lines.append(f"- **Acumulado del mes ({current_month})**: {monthly_runs} corridas (Tasa de éxito: {success_rate:.1f}%, Costo estimado: ${total_cost:.2f})")
    else:
        lines.append(f"- **Acumulado del mes ({current_month})**: 0 corridas registradas")
        
    return "\n".join(lines)


def format_topic_prs_block(prs: list[dict]) -> str:
    lines = ["## Desarrollos y Cambios Recientes (Git)"]
    open_prs = [p for p in prs if p.get("state") == "OPEN"]
    merged_prs = [p for p in prs if p.get("state") == "MERGED"]
    
    if open_prs:
        lines.append("### PRs Abiertos")
        for p in open_prs:
            num = p.get("number")
            title = p.get("title", "")
            url = p.get("url", "")
            branch = p.get("headRefName", "")
            lines.append(f"- [#{num}]({url}) — `{title}` (rama: `{branch}`)")
            
    if merged_prs:
        lines.append("### Últimos PRs Fusionados")
        # Mostrar los últimos 5 mergeados
        for p in merged_prs[:5]:
            num = p.get("number")
            title = p.get("title", "")
            url = p.get("url", "")
            merged_at = p.get("mergedAt", "")[:10]
            lines.append(f"- **{merged_at}** — [#{num}]({url}) `{title}`")
            
    if not open_prs and not merged_prs:
        lines.append("- Sin actividad de PRs reciente.")
        
    return "\n".join(lines)


def format_alvaro_dev_timeline(dev_prs: list[dict]) -> str:
    lines = ["## Actividad de Desarrollo (Git)", ""]
    def get_date(p: dict) -> str:
        return (p.get("mergedAt") or p.get("createdAt") or "")[:10]
        
    sorted_prs = sorted(dev_prs, key=get_date, reverse=True)
    
    for p in sorted_prs[:15]:
        date_str = get_date(p)
        repo = p.get("repo_slug", "").split("/")[-1]
        num = p.get("number")
        title = p.get("title", "")
        url = p.get("url", "")
        state = p.get("state", "").lower()
        state_label = "fusionado" if state == "merged" else "abierto"
        lines.append(f"- **{date_str}** — **{repo}** ([#{num}]({url}), {state_label}): {title}")
        
    return "\n".join(lines)


def main() -> None:
    instance_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SECRETARY_INSTANCE", str(Path.home() / ".secretary"))
    instance_path = Path(instance_arg).expanduser().resolve()
    articles_dir = instance_path / "knowledge" / "wiki" / "articulos"
    
    if not articles_dir.is_dir():
        print(f"Error: No se encontró el directorio de artículos en {articles_dir}", file=sys.stderr)
        sys.exit(1)
        
    current_month = datetime.date.today().strftime("%Y-%m")
    
    print(f"Actualizando estadísticas y PRs de desarrollo en {instance_path} (mes: {current_month})...")
    
    # 1. Actualizar métricas de módulos
    for routine_id, rel_article in ROUTINE_TO_MODULE.items():
        article_path = articles_dir / rel_article
        if not article_path.is_file():
            continue
        metrics = load_metrics_for_routine(instance_path, routine_id, current_month)
        metrics_block = format_metrics_block(metrics, current_month)
        
        content = article_path.read_text(encoding="utf-8")
        new_content = replace_or_insert_section(content, "execution-metrics", metrics_block)
        if new_content != content:
            article_path.write_text(new_content, encoding="utf-8")
            print(f"  ✓ Actualizado módulo: {rel_article}")

    # 2. Recolectar PRs de repositorios
    repos = get_repos_from_config(instance_path)
    topic_prs: dict[str, list[dict]] = defaultdict(list)
    all_dev_prs: list[dict] = []
    
    for repo_slug in repos:
        prs = fetch_prs_for_repo(repo_slug)
        for p in prs:
            head_branch = p.get("headRefName", "")
            if is_auto_pr(head_branch):
                continue
            
            p["repo_slug"] = repo_slug
            all_dev_prs.append(p)
            
            topic = map_pr_to_topic(repo_slug, p.get("title", ""), head_branch)
            if topic:
                topic_prs[topic].append(p)

    # 3. Actualizar temas con PRs de desarrollo
    for rel_topic, prs_list in topic_prs.items():
        topic_path = articles_dir / rel_topic
        if not topic_path.is_file():
            continue
        
        prs_block = format_topic_prs_block(prs_list)
        content = topic_path.read_text(encoding="utf-8")
        new_content = replace_or_insert_section(content, "desarrollo-git", prs_block)
        if new_content != content:
            topic_path.write_text(new_content, encoding="utf-8")
            print(f"  ✓ Actualizado tema con PRs: {rel_topic}")

    # 4. Actualizar alvaro-mur.md con la actividad de desarrollo
    alvaro_article = articles_dir / "personas" / "alvaro-mur.md"
    if alvaro_article.is_file() and all_dev_prs:
        alvaro_content = alvaro_article.read_text(encoding="utf-8")
        timeline_block = format_alvaro_dev_timeline(all_dev_prs)
        new_alvaro_content = replace_or_insert_section(
            alvaro_content,
            "actividad-desarrollo-git",
            timeline_block,
            fallback_header="## Actividad reciente"
        )
        if new_alvaro_content != alvaro_content:
            alvaro_article.write_text(new_alvaro_content, encoding="utf-8")
            print(f"  ✓ Actualizado perfil de Álvaro con actividad de desarrollo Git.")

    print("Completado.")


if __name__ == "__main__":
    main()
