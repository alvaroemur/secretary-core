"""Deterministic context collector and assembler for agent sessions."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from secretary.config import core_root, instance_root, load_config


@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    user_invocable: bool = True
    trigger_cues: list[str] = field(default_factory=list)


@dataclass
class RoutineInfo:
    id: str
    name: str
    cron: str
    description: str
    opens_pr: bool = True
    status: str = "active"


@dataclass
class CursorRuleInfo:
    name: str
    description: str
    path: str
    globs: list[str] = field(default_factory=list)
    always_apply: bool = False
    content: str = ""


@dataclass
class ClaudeMemoryInfo:
    project_slug: str
    memory_path: str
    bullets: list[str] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class SisterRepoInfo:
    repo: str
    path: str
    branch: Optional[str] = None
    is_clean: Optional[bool] = None
    wip_summary: Optional[str] = None


@dataclass
class HostRepoContext:
    path: str
    plane: str
    repo_slug: Optional[str] = None
    branch: Optional[str] = None
    is_clean: Optional[bool] = None
    local_rules_path: Optional[str] = None
    local_rules_content: Optional[str] = None
    cursor_rules: list[CursorRuleInfo] = field(default_factory=list)
    claude_memory: Optional[ClaudeMemoryInfo] = None
    spec_memory_files: list[dict[str, str]] = field(default_factory=list)


def _safe_read_text(path: Path) -> str:
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def _parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and remaining body from markdown."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_fm = parts[1].strip()
            body = parts[2].strip()
            try:
                fm = yaml.safe_load(raw_fm) or {}
                if isinstance(fm, dict):
                    return fm, body
            except Exception:
                # Robust regex fallback for invalid YAML (e.g. unquoted colons)
                fm = {}
                name_m = re.search(r"^name:\s*(.+)$", raw_fm, re.MULTILINE)
                if name_m:
                    fm["name"] = name_m.group(1).strip().strip('"\'')
                desc_m = re.search(r"^description:\s*(?:>-\s*)?([\s\S]+?)(?=\n[a-z0-9_-]+:|$)", raw_fm, re.MULTILINE)
                if desc_m:
                    fm["description"] = " ".join(desc_m.group(1).split()).strip().strip('"\'')
                invoc_m = re.search(r"^user-invocable:\s*(true|false)", raw_fm, re.MULTILINE | re.IGNORECASE)
                if invoc_m:
                    fm["user-invocable"] = invoc_m.group(1).lower() == "true"
                always_m = re.search(r"^alwaysApply:\s*(true|false)", raw_fm, re.MULTILINE | re.IGNORECASE)
                if always_m:
                    fm["alwaysApply"] = always_m.group(1).lower() == "true"
                globs_m = re.search(r"^globs:\s*(.+)$", raw_fm, re.MULTILINE)
                if globs_m:
                    fm["globs"] = [g.strip().strip('"\'') for g in globs_m.group(1).split(",") if g.strip()]
                return fm, body
    return {}, content.strip()


def collect_user_doctrine(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect global user rules, identity, language, and tone doctrine."""
    cfg = config if config is not None else (load_config() if (instance_root() / ".secretary.yml").is_file() else {})

    sources_to_try: list[Path] = [
        Path.home() / ".claude" / "CLAUDE.md",
        Path.home() / ".gemini" / "config" / "AGENTS.md",
        Path.home() / ".cursorrules",
        instance_root() / "canon" / "rules" / "session" / "estilo-voz.md",
    ]

    custom_sources = cfg.get("context", {}).get("rules_sources", {}).get("user", [])
    if isinstance(custom_sources, list):
        for s in custom_sources:
            sources_to_try.insert(0, Path(os.path.expanduser(str(s))).resolve())

    found_sources: list[str] = []
    raw_texts: list[str] = []

    for src in sources_to_try:
        if src.is_file() and str(src) not in found_sources:
            content = _safe_read_text(src)
            if content.strip():
                found_sources.append(str(src))
                raw_texts.append(content)

    return {
        "identity": {
            "name": "Álvaro Mur",
            "email": cfg.get("accounts", {}).get("personal", "alvaro.e.mur@gmail.com"),
            "location": "Lima, Perú",
            "timezone": cfg.get("timezone", "America/Lima"),
            "github": "alvaroemur",
            "handle": "cigmas",
        },
        "language": {
            "primary": "Castellano neutro con tuteo estricto",
            "voseo_prohibited": True,
            "rules": [
                "Nunca voseo rioplatense/argentino (vos, tenés, querés, podés, hacé, poné, mirá).",
                "Usar tuteo estándar: tú, tienes, quieres, puedes, haz, pon, mira, agrega, copia, empieza, fíjate, piensa, delega.",
                "Léxico: preferir 'aquí' / 'allí' sobre 'acá' / 'allá' cuando aplique.",
                "Cuidado con copy largo o creativo de producto donde el registro tiende a derivar.",
            ],
        },
        "discipline": {
            "no_slop": "Cero sinónimos rotados, cero hedging, cero adjetivos de marketing, oraciones cortas y voz activa.",
            "intellectual_honesty": [
                "No ser adulador (no sycophantic).",
                "No dar la razón por defecto; corregir premisas flojas antes de ejecutar.",
                "Proponer alternativas con tradeoffs claros.",
                "Señalar inconsistencias o errores de inmediato.",
            ],
        },
        "google_workspace": {
            "cli": "gog (gogcli en PATH)",
            "default_account": cfg.get("accounts", {}).get("personal", "alvaro.e.mur@gmail.com"),
            "mcp_policy": "Google Drive MCP es SOLO LECTURA. Nunca asumir imposibilidad de edición por limitación del MCP.",
            "write_flow": [
                "1. Sincronizar vía skill drive-sync (.drivesync.yaml)",
                "2. Edición en vivo en navegador con supervisión",
                "3. Escritura directa puntual con gog (gog sheets update/append/format)",
            ],
        },
        "transit_folders": {
            "paths": ["~/Desktop", "~/Downloads", "~/Documents"],
            "policy": "Zonas de tránsito, no de almacenamiento. Archivar a su home tras su uso; alertar si hay credenciales sueltas.",
        },
        "sources": found_sources,
    }


def collect_system_taxonomy(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect canonical system taxonomy, planes, and folder layouts."""
    cfg = config if config is not None else (load_config() if (instance_root() / ".secretary.yml").is_file() else {})

    dispatch_repos = []
    for r in cfg.get("dispatch", {}).get("executor", {}).get("repos", []):
        if isinstance(r, dict):
            dispatch_repos.append({"repo": r.get("repo"), "path": r.get("path")})

    return {
        "planes": {
            "Cowork": {
                "root": "~/Cowork/",
                "purpose": "Gestión operativa, propuestas, clientes y proyectos externos.",
                "workspaces": ["ennui", "inspiro", "studio", "_inbox", "_referencias"],
                "project_skeleton": [
                    "01-admin/ (venta y gestión)",
                    "02-insumos/ (fuentes y recursos)",
                    "03-ejecucion/ (fases EDT, análisis, implementación)",
                    "04-comunicaciones/ (borradores y enviados)",
                    "05-entregables/ (entregables finales al cliente)",
                    "06-bitacora/ (conocimiento vivo del servicio)",
                ],
            },
            "Dev": {
                "root": "~/Dev/",
                "purpose": "Repositorios de código fuente, herramientas y automatizaciones técnicas.",
                "examples": ["secretary-core", "doc2struct", "workwatch"],
            },
            "Secretary": {
                "root": "~/.secretary/",
                "purpose": "Subsistema personal de captura, memoria durable, wiki y rutinas.",
                "rule": "No editar salvo instrucción explícita del usuario.",
            },
            "Drive": {
                "purpose": "Entregables nativos (Docs, Sheets, Slides) y archivo durable.",
                "access": "Lectura vía gog/MCP, escritura coordinada con el usuario.",
            },
        },
        "domain_gate": {
            "principle": "Si la salida de una tarea pertenece a otro repositorio o plano, señalarlo antes de producir y sugerir dispatch.",
            "dispatch_allowlist": dispatch_repos,
        },
    }


def collect_skills(config: dict[str, Any] | None = None) -> list[SkillInfo]:
    """Scan and list all active skills across known directories."""
    skill_dirs: list[Path] = [
        Path.home() / ".claude" / "skills",
        Path.home() / ".gemini" / "config" / "skills",
        Path.home() / ".cursor" / "skills-cursor",
        core_root() / "skills",
    ]

    seen_names: set[str] = set()
    skills: list[SkillInfo] = []

    for sdir in skill_dirs:
        if not sdir.is_dir():
            continue
        try:
            entries = sorted(sdir.iterdir())
        except Exception:
            continue

        for entry in entries:
            skill_md = entry / "SKILL.md" if entry.is_dir() else (entry if entry.name == "SKILL.md" else None)
            if not skill_md or not skill_md.is_file():
                continue

            name = entry.name if entry.is_dir() else entry.parent.name
            if name in seen_names:
                continue

            content = _safe_read_text(skill_md)
            fm, body = _parse_yaml_frontmatter(content)

            skill_name = fm.get("name") or name
            description = fm.get("description") or ""
            user_invocable = fm.get("user-invocable", True)

            if not description and body:
                lines = [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]
                if lines:
                    description = lines[0]

            triggers: list[str] = []
            trigger_match = re.search(r"Triggers?:\s*([^\.\n]+)", description, re.IGNORECASE)
            if trigger_match:
                raw_triggers = trigger_match.group(1)
                triggers = [t.strip().strip('"\'`') for t in re.split(r"[,·;]", raw_triggers) if t.strip()]

            skills.append(
                SkillInfo(
                    name=skill_name,
                    description=description.strip(),
                    path=str(skill_md),
                    user_invocable=bool(user_invocable),
                    trigger_cues=triggers,
                )
            )
            seen_names.add(name)

    skills.sort(key=lambda s: s.name)
    return skills


def collect_routines(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect scheduled routines and active automation manifest."""
    cfg = config if config is not None else (load_config() if (instance_root() / ".secretary.yml").is_file() else {})
    inst = instance_root()

    manifest_path = inst / ".cursor" / "routines" / "manifest.yaml"
    manifest_data: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:
            manifest_data = {}

    routines_cfg = cfg.get("dispatch", {}).get("routines", {})
    executor = routines_cfg.get("executor", "cursor-cron")
    disabled_list = set(routines_cfg.get("disabled", []))

    routines_list: list[RoutineInfo] = []
    for r in manifest_data.get("routines", []):
        if not isinstance(r, dict):
            continue
        rid = r.get("id", "")
        status = "disabled" if rid in disabled_list else "active"
        routines_list.append(
            RoutineInfo(
                id=rid,
                name=r.get("name", rid),
                cron=r.get("cron", ""),
                description=r.get("description", ""),
                opens_pr=r.get("opens_pr", True),
                status=status,
            )
        )

    return {
        "executor": executor,
        "timezone": manifest_data.get("timezone", cfg.get("timezone", "America/Lima")),
        "routines": [asdict(r) for r in routines_list],
    }


def collect_git_policy(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect git commit, branch, and signature conventions."""
    return {
        "commit_convention": "Conventional Commits estricto en castellano: <tipo>(<scope>): <descripción breve>",
        "types": ["feat", "fix", "docs", "refactor", "chore", "ci", "test", "style", "perf"],
        "branch_naming": "Una rama por PR: <scope>/<descripcion-corta> (no reusar ramas para otros hilos)",
        "worktree_discipline": "~/.secretary checkout principal permanece en main; ramas de trabajo en worktrees",
        "references": "Solo citar #N cuando corresponde a un issue/PR real de GitHub (nunca placeholders como #00 o #TBD)",
        "signatures": {
            "generator": "~/.claude/scripts/sec-signature.sh <contexto>",
            "mark": "<!-- agent-generated:<contexto> runtime=<runtime> -->",
            "footer": "🤖 _Generado por <runtime> — <contexto> · <fecha>_",
        },
    }


def _find_cursor_rules(target_dir: Path) -> list[CursorRuleInfo]:
    """Find Cursor .mdc rules in target_dir or parent workspace directories."""
    rules: list[CursorRuleInfo] = []
    searched_dirs: list[Path] = [target_dir]
    
    # Check parent directory if within Cowork/Dev
    if target_dir.parent != Path.home() and target_dir.parent.is_dir():
        searched_dirs.append(target_dir.parent)

    seen_paths: set[str] = set()
    for sdir in searched_dirs:
        rules_dir = sdir / ".cursor" / "rules"
        if not rules_dir.is_dir():
            continue
        for rfile in sorted(rules_dir.glob("*.mdc")):
            if str(rfile) in seen_paths:
                continue
            seen_paths.add(str(rfile))
            content = _safe_read_text(rfile)
            fm, body = _parse_yaml_frontmatter(content)
            rules.append(
                CursorRuleInfo(
                    name=rfile.stem,
                    description=fm.get("description", rfile.stem),
                    path=str(rfile),
                    globs=fm.get("globs", []),
                    always_apply=bool(fm.get("alwaysApply", False)),
                    content=body.strip(),
                )
            )
    return rules


def _find_claude_project_memory(target_dir: Path) -> Optional[ClaudeMemoryInfo]:
    """Find Claude Code persistent project memory for the given workspace path."""
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.is_dir():
        return None

    target_str = str(target_dir.resolve())
    slug = target_str.replace("/", "-")

    candidate_dirs: list[Path] = [
        claude_projects / slug,
    ]

    # Also search by repo base name if in a worktree or subfolder
    if not (claude_projects / slug).is_dir():
        for pdir in claude_projects.iterdir():
            if pdir.is_dir() and (slug.startswith(pdir.name) or pdir.name.startswith(slug)):
                candidate_dirs.append(pdir)

    for cdir in candidate_dirs:
        mem_file = cdir / "memory" / "MEMORY.md"
        if mem_file.is_file():
            raw = _safe_read_text(mem_file)
            bullets = [l.strip() for l in raw.splitlines() if l.strip().startswith("- ")]
            return ClaudeMemoryInfo(
                project_slug=cdir.name,
                memory_path=str(mem_file),
                bullets=bullets,
                raw_content=raw.strip(),
            )
    return None


def collect_host_context(cwd: Path | None = None) -> HostRepoContext:
    """Collect context for current working directory (repo, branch, plane, local rules, cursor rules, claude memory)."""
    target_dir = (cwd or Path.cwd()).resolve()

    home = Path.home()
    plane = "other"
    if str(target_dir).startswith(str(home / "Cowork")):
        plane = "Cowork"
    elif str(target_dir).startswith(str(home / "Dev")):
        plane = "Dev"
    elif str(target_dir).startswith(str(home / ".secretary")):
        plane = "Secretary"

    repo_slug: Optional[str] = None
    branch: Optional[str] = None
    is_clean: Optional[bool] = None

    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=target_dir,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out == "true":
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=target_dir,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            status_out = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=target_dir,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            is_clean = len(status_out) == 0

            try:
                repo_view = subprocess.check_output(
                    ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                    cwd=target_dir,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                if repo_view:
                    repo_slug = repo_view
            except Exception:
                pass
    except Exception:
        pass

    local_rules_path: Optional[str] = None
    local_rules_content: Optional[str] = None
    for cand in [target_dir / "AGENTS.md", target_dir / "CLAUDE.md", target_dir / ".cursorrules"]:
        if cand.is_file():
            local_rules_path = str(cand)
            local_rules_content = _safe_read_text(cand)
            break

    cursor_rules = _find_cursor_rules(target_dir)
    claude_memory = _find_claude_project_memory(target_dir)

    spec_files: list[dict[str, str]] = []
    for spec_cand in [
        target_dir / "_diseño" / ".specify" / "memory" / "constitucion-operativa.md",
        target_dir / ".specify" / "memory" / "constitucion-operativa.md",
        target_dir / "MEMORY.md",
    ]:
        if spec_cand.is_file():
            spec_files.append({"path": str(spec_cand), "content": _safe_read_text(spec_cand)})

    return HostRepoContext(
        path=str(target_dir),
        plane=plane,
        repo_slug=repo_slug,
        branch=branch,
        is_clean=is_clean,
        local_rules_path=local_rules_path,
        local_rules_content=local_rules_content,
        cursor_rules=cursor_rules,
        claude_memory=claude_memory,
        spec_memory_files=spec_files,
    )


def collect_cross_repo_wip(config: dict[str, Any] | None = None) -> list[SisterRepoInfo]:
    """Collect active status and WIP summaries across sister repositories."""
    cfg = config if config is not None else (load_config() if (instance_root() / ".secretary.yml").is_file() else {})
    inst = instance_root()
    wip_dir = inst / "subsystem" / "wip"

    repos: list[SisterRepoInfo] = []
    for r in cfg.get("dispatch", {}).get("executor", {}).get("repos", []):
        if not isinstance(r, dict):
            continue
        slug = r.get("repo", "")
        raw_path = r.get("path", "")
        p = Path(os.path.expanduser(raw_path)).resolve()
        
        branch = None
        is_clean = None
        if p.is_dir() and (p / ".git").exists():
            try:
                branch = subprocess.check_output(
                    ["git", "branch", "--show-current"],
                    cwd=p,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                status_out = subprocess.check_output(
                    ["git", "status", "--porcelain"],
                    cwd=p,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                is_clean = len(status_out) == 0
            except Exception:
                pass

        # Look for WIP file
        wip_summary = None
        short_name = p.name
        if wip_dir.is_dir():
            for wcand in [wip_dir / f"{short_name}.md", wip_dir / f"{slug.replace('/', '-')}.md"]:
                if wcand.is_file():
                    wip_text = _safe_read_text(wcand)
                    wip_lines = [l.strip() for l in wip_text.splitlines() if l.strip() and not l.startswith("#")]
                    if wip_lines:
                        wip_summary = " ".join(wip_lines[:2])
                    break

        repos.append(
            SisterRepoInfo(
                repo=slug,
                path=str(p),
                branch=branch,
                is_clean=is_clean,
                wip_summary=wip_summary,
            )
        )
    return repos


def collect_latest_heartbeat() -> Optional[str]:
    """Collect latest consolidated heartbeat text."""
    hb_file = instance_root() / "subsystem" / "heartbeat" / "latest.md"
    if hb_file.is_file():
        return _safe_read_text(hb_file).strip()
    return None


def assemble_context_dict(
    config: dict[str, Any] | None = None,
    cwd: Path | None = None,
    is_max: bool = False,
) -> dict[str, Any]:
    """Assemble all deterministic context components into a structured dict."""
    cfg = config if config is not None else (load_config() if (instance_root() / ".secretary.yml").is_file() else {})
    host_ctx = collect_host_context(cwd)

    data: dict[str, Any] = {
        "user_doctrine": collect_user_doctrine(cfg),
        "system_taxonomy": collect_system_taxonomy(cfg),
        "skills": [asdict(s) for s in collect_skills(cfg)],
        "routines": collect_routines(cfg),
        "git_policy": collect_git_policy(cfg),
        "host_context": asdict(host_ctx),
    }

    if is_max:
        data["cross_repo_wip"] = [asdict(s) for s in collect_cross_repo_wip(cfg)]
        data["latest_heartbeat"] = collect_latest_heartbeat()

    return data


def format_markdown(
    context_data: dict[str, Any],
    sections: list[str] | None = None,
    is_max: bool = False,
) -> str:
    """Format assembled context into high-density, agent-ready Markdown."""
    sel = set(sections or ["all"])
    show_all = "all" in sel

    out: list[str] = ["# Contexto de Sesión Determinístico (Secretary Engine)", ""]

    # 1. Host Context
    if show_all or "host" in sel:
        host = context_data.get("host_context", {})
        out.append("## 📍 Contexto del Workspace Anfitrión")
        out.append(f"- **Ruta activa:** `{host.get('path')}` (Plano: **{host.get('plane')}**)")
        if host.get("repo_slug"):
            out.append(f"- **Repositorio GitHub:** `{host.get('repo_slug')}`")
        if host.get("branch"):
            clean_str = "limpio" if host.get("is_clean") else "con cambios sin commitear"
            out.append(f"- **Rama Git:** `{host.get('branch')}` ({clean_str})")
        if host.get("local_rules_path"):
            out.append(f"- **Reglas locales cargadas:** `{host.get('local_rules_path')}`")

        # Cursor .mdc semantic rules
        cursor_rules = host.get("cursor_rules", [])
        if cursor_rules:
            out.append(f"- **Reglas semánticas de Cursor (`.cursor/rules/*.mdc`, {len(cursor_rules)} encontradas):**")
            for cr in cursor_rules:
                always_str = " [Always Apply]" if cr.get("always_apply") else ""
                globs_str = f" (globs: {', '.join(cr.get('globs', []))})" if cr.get("globs") else ""
                out.append(f"  - `{cr.get('name')}`: {cr.get('description')}{always_str}{globs_str}")
                if is_max and cr.get("content"):
                    out.append(f"    > {cr.get('content')[:200]}...")

        # Claude Code Project Memory
        claude_mem = host.get("claude_memory")
        if claude_mem:
            bullets = claude_mem.get("bullets", [])
            out.append(f"- **Memoria persistente de Claude Code (`MEMORY.md`, {len(bullets)} entradas acumuladas):**")
            limit = len(bullets) if is_max else min(6, len(bullets))
            for b in bullets[:limit]:
                out.append(f"  {b}")
            if not is_max and len(bullets) > limit:
                out.append(f"  ... y {len(bullets) - limit} entradas más (usa `--max` para ver todo)")

        out.append("")

    # 2. User Doctrine
    if show_all or "doctrine" in sel or "user" in sel or "rules" in sel:
        user = context_data.get("user_doctrine", {})
        ident = user.get("identity", {})
        out.append("## 👤 Doctrina del Usuario")
        out.append(f"- **Usuario:** {ident.get('name')} (`{ident.get('email')}`) | GitHub: `{ident.get('github')}` | Zona: `{ident.get('timezone')}`")
        out.append(f"- **Idioma & Registro:** {user.get('language', {}).get('primary')}")
        for r in user.get("language", {}).get("rules", []):
            out.append(f"  - {r}")
        out.append(f"- **Disciplina Anti-Slop:** {user.get('discipline', {}).get('no_slop')}")
        out.append("- **Honestidad Intelectual:**")
        for h in user.get("discipline", {}).get("intellectual_honesty", []):
            out.append(f"  - {h}")
        out.append(f"- **Google Workspace:** CLI `{user.get('google_workspace', {}).get('cli')}` ({user.get('google_workspace', {}).get('default_account')}). {user.get('google_workspace', {}).get('mcp_policy')}")
        out.append(f"- **Carpetas de Tránsito:** {', '.join(user.get('transit_folders', {}).get('paths', []))} → {user.get('transit_folders', {}).get('policy')}")
        out.append("")

    # 3. System Taxonomy
    if show_all or "taxonomy" in sel:
        tax = context_data.get("system_taxonomy", {})
        out.append("## 🗺️ Mapa del Sistema y Taxonomía")
        for plane_name, plane_info in tax.get("planes", {}).items():
            root_str = f" (`{plane_info.get('root')}`)" if "root" in plane_info else ""
            out.append(f"### Plano {plane_name}{root_str}")
            out.append(f"{plane_info.get('purpose', '')}")
            if "project_skeleton" in plane_info:
                out.append("- **Esqueleto canónico de proyecto:**")
                for sk in plane_info.get("project_skeleton", []):
                    out.append(f"  - `{sk}`")
        out.append("### Compuerta de Dominio")
        out.append(f"- {tax.get('domain_gate', {}).get('principle')}")
        allowlist = tax.get("domain_gate", {}).get("dispatch_allowlist", [])
        if allowlist:
            repos_str = ", ".join([f"`{r.get('repo')}`" for r in allowlist])
            out.append(f"- **Repos con ejecutor autónomo (`dispatch:execute`):** {repos_str}")
        out.append("")

    # 4. Git Policy
    if show_all or "git" in sel:
        git_p = context_data.get("git_policy", {})
        out.append("## 🌿 Convenciones de Git y Entregas")
        out.append(f"- **Commits:** `{git_p.get('commit_convention')}`")
        out.append(f"- **Ramas:** {git_p.get('branch_naming')}")
        out.append(f"- **Worktrees:** {git_p.get('worktree_discipline')}")
        out.append(f"- **Referencias:** {git_p.get('references')}")
        out.append(f"- **Firmas de Agente:** `{git_p.get('signatures', {}).get('generator')}`")
        out.append("")

    # 5. Active Skills
    if show_all or "skills" in sel:
        skills = context_data.get("skills", [])
        out.append(f"## ⚡ Skills Disponibles ({len(skills)} registrados)")
        out.append("| Skill | Descripción / Triggers | Invocable |")
        out.append("|-------|------------------------|-----------|")
        for s in skills:
            desc = s.get("description", "").replace("\n", " ")
            if len(desc) > 90:
                desc = desc[:87] + "..."
            inv = "✓" if s.get("user_invocable") else "·"
            out.append(f"| `{s.get('name')}` | {desc} | {inv} |")
        out.append("")

    # 6. Routines
    if show_all or "routines" in sel:
        routines_info = context_data.get("routines", {})
        routines = routines_info.get("routines", [])
        out.append(f"## ⏰ Rutinas Programadas (Executor: `{routines_info.get('executor')}`)")
        out.append("| ID | Cron | Estado | Descripción | PR |")
        out.append("|----|------|--------|-------------|----|")
        for r in routines:
            status_emoji = "🟢" if r.get("status") == "active" else "⏸️"
            opens_pr_str = "Sí" if r.get("opens_pr") else "No"
            out.append(f"| `{r.get('id')}` | `{r.get('cron')}` | {status_emoji} {r.get('status')} | {r.get('description')} | {opens_pr_str} |")
        out.append("")

    # 7. Extended Context (--max)
    if is_max:
        out.append("## 🌐 Estado Cruzado del Sistema (--max)")
        sister_repos = context_data.get("cross_repo_wip", [])
        if sister_repos:
            out.append("### Repositorios Hermano y Fichas WIP")
            out.append("| Repositorio | Rama | Estado | Ficha WIP |")
            out.append("|-------------|------|--------|-----------|")
            for sr in sister_repos:
                branch = sr.get("branch") or "—"
                clean_str = "✓ limpio" if sr.get("is_clean") else "· sucio"
                wip = sr.get("wip_summary") or "—"
                if len(wip) > 60:
                    wip = wip[:57] + "..."
                out.append(f"| `{sr.get('repo')}` | `{branch}` | {clean_str} | {wip} |")
            out.append("")

        hb = context_data.get("latest_heartbeat")
        if hb:
            out.append("### Último Latido del Subsistema (`heartbeat/latest.md`)")
            hb_excerpt = "\n".join(hb.splitlines()[:20])
            out.append(f"```markdown\n{hb_excerpt}\n```")
            out.append("")

    return "\n".join(out).strip() + "\n"


def format_compact(context_data: dict[str, Any]) -> str:
    """Format assembled context into a concise summary."""
    host = context_data.get("host_context", {})
    user = context_data.get("user_doctrine", {})
    skills_count = len(context_data.get("skills", []))
    routines_count = len(context_data.get("routines", {}).get("routines", []))
    cursor_rules_count = len(host.get("cursor_rules", []))
    claude_mem = host.get("claude_memory")
    mem_str = f" | Claude Memory: {len(claude_mem.get('bullets', []))} bullets" if claude_mem else ""
    cr_str = f" | Cursor Rules: {cursor_rules_count}" if cursor_rules_count else ""

    lines = [
        f"Secretary Context [Plane: {host.get('plane')}, Branch: {host.get('branch', 'none')}]{cr_str}{mem_str}",
        f"User: {user.get('identity', {}).get('name')} | Language: {user.get('language', {}).get('primary')}",
        f"Active Skills: {skills_count} | Scheduled Routines: {routines_count}",
        f"Git: Conventional Commits (Spanish) | Workspace: {host.get('path')}",
    ]
    return "\n".join(lines)
