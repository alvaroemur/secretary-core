#!/usr/bin/env python3
"""Generador estático Markdown → HTML estilo Wikipedia.

Sin dependencias externas. Lee `articulos/**/*.md`, parsea frontmatter
YAML (subset), renderiza Markdown (subset) con wikilinks `[[slug]]` y
produce `output/` con una portada e índices por categoría.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# SECRETARY = directorio raíz de la instance (datos: correo/, reuniones/,
# whatsapp/, ...). Cuando build.py vive en secretary-core (engine) vía
# symlink, ROOT.parent resuelve al engine en vez de a los datos. Tomar el
# path NO resuelto para respetar la ruta de invocación; permitir override
# vía env var para rutinas/CI.
SECRETARY = Path(os.environ.get("SECRETARY_DATA") or Path(__file__).absolute().parent.parent.parent)
# ARTICULOS cuelga de SECRETARY (la instance / worktree) para permitir que una
# rutina aislada (ej. wiki-update en un git worktree) construya desde sus propios
# artículos vía `SECRETARY_DATA=<worktree>`. Por defecto resuelve a la misma ruta
# de siempre (instance/wiki/articulos). OUTPUT y ASSETS siguen colgando del engine.
ARTICULOS = SECRETARY / "wiki" / "articulos"
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "output"

SITE_TITLE = "Wiki personal"


# -----------------------------------------------------------------------------
# Frontmatter (subset YAML)
# -----------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Devuelve (meta, cuerpo). Soporta escalares, listas simples,
    un nivel de dict (infobox) y listas de dicts (fuentes)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    header = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")

    meta: dict = {}
    lines = header.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w\- ]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        if val == "":
            # bloque: dict indentado o lista de items
            block = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith("  ") or lines[j].strip() == ""):
                block.append(lines[j])
                j += 1
            meta[key] = parse_block(block)
            i = j
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
        else:
            meta[key] = val.strip('"').strip("'")
        i += 1
    return meta, body


def parse_block(lines: list[str]) -> object:
    """Dict indentado o lista (de strings o de dicts)."""
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return {}
    # lista si todas empiezan con "- "
    if all(l.lstrip().startswith("- ") for l in non_empty):
        result: list = []
        cur: dict | None = None
        for l in non_empty:
            stripped = l.lstrip()
            indent = len(l) - len(stripped)
            if stripped.startswith("- "):
                rest = stripped[2:].strip()
                if ":" in rest and not rest.startswith("http"):
                    k, _, v = rest.partition(":")
                    cur = {k.strip(): v.strip()}
                    result.append(cur)
                else:
                    result.append(rest)
                    cur = None
            elif cur is not None and ":" in stripped:
                k, _, v = stripped.partition(":")
                cur[k.strip()] = v.strip()
        return result
    # dict: clave: valor
    d: dict = {}
    for l in non_empty:
        m = re.match(r"^\s*([^:]+):\s*(.*)$", l)
        if m:
            v = m.group(2).strip()
            # Quitar comillas envolventes (YAML scalar quoting)
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            d[m.group(1).strip()] = v
    return d


# -----------------------------------------------------------------------------
# Markdown (subset)
# -----------------------------------------------------------------------------

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def render_inline(text: str, resolve_wikilink) -> str:
    # escapar primero
    out = html.escape(text, quote=False)
    # code antes del resto para proteger contenido
    placeholders: list[str] = []

    def stash(s: str) -> str:
        placeholders.append(s)
        return f"\x00{len(placeholders) - 1}\x00"

    out = INLINE_CODE.sub(lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), out)
    out = WIKILINK.sub(lambda m: stash(resolve_wikilink(m.group(1), m.group(2))), out)
    out = LINK.sub(lambda m: stash(f'<a class="ext" href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>'), out)
    out = BOLD.sub(r"<strong>\1</strong>", out)
    out = ITALIC.sub(r"<em>\1</em>", out)

    def unstash(m):
        return placeholders[int(m.group(1))]

    out = re.sub(r"\x00(\d+)\x00", unstash, out)
    return out


@dataclass
class Heading:
    level: int
    text: str
    slug: str


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9áéíóúñü\- ]+", "", s)
    s = s.strip().replace(" ", "-")
    return s or "section"


def render_markdown(body: str, resolve_wikilink) -> tuple[str, list[Heading]]:
    lines = body.split("\n")
    html_parts: list[str] = []
    headings: list[Heading] = []
    i = 0
    slug_counts: dict[str, int] = {}

    def next_slug(txt: str) -> str:
        base = slugify(txt)
        n = slug_counts.get(base, 0)
        slug_counts[base] = n + 1
        return base if n == 0 else f"{base}-{n}"

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            txt = m.group(2).strip()
            slug = next_slug(txt)
            headings.append(Heading(level, txt, slug))
            html_parts.append(
                f'<h{level} id="{slug}">{render_inline(txt, resolve_wikilink)}'
                f' <a class="anchor" href="#{slug}">¶</a></h{level}>'
            )
            i += 1
            continue

        # hr
        if re.match(r"^-{3,}$|^\*{3,}$", stripped):
            html_parts.append("<hr/>")
            i += 1
            continue

        # blockquote
        if stripped.startswith("> "):
            buf: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                buf.append(lines[i].strip()[2:])
                i += 1
            inner = " ".join(buf)
            html_parts.append(f"<blockquote>{render_inline(inner, resolve_wikilink)}</blockquote>")
            continue

        # lista (- o *)
        if re.match(r"^[-*]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].lstrip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].lstrip()))
                i += 1
            html_parts.append("<ul>")
            for it in items:
                html_parts.append(f"<li>{render_inline(it, resolve_wikilink)}</li>")
            html_parts.append("</ul>")
            continue

        # lista ordenada
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].lstrip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].lstrip()))
                i += 1
            html_parts.append("<ol>")
            for it in items:
                html_parts.append(f"<li>{render_inline(it, resolve_wikilink)}</li>")
            html_parts.append("</ol>")
            continue

        # párrafo
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|[-*]\s|\d+\.\s|>\s|-{3,}$|\*{3,}$)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        para = " ".join(buf)
        html_parts.append(f"<p>{render_inline(para, resolve_wikilink)}</p>")

    return "\n".join(html_parts), headings


# -----------------------------------------------------------------------------
# Modelo
# -----------------------------------------------------------------------------

@dataclass
class Articulo:
    slug: str            # e.g. "user-profile" or "personas/juan"
    path: Path
    meta: dict
    body: str
    html_body: str = ""
    headings: list[Heading] = field(default_factory=list)

    @property
    def titulo(self) -> str:
        return self.meta.get("titulo") or self.slug.split("/")[-1].replace("-", " ").title()

    @property
    def categoria(self) -> str:
        parts = self.slug.split("/")
        return parts[0] if len(parts) > 1 else "perfil"

    @property
    def output_path(self) -> Path:
        return OUTPUT / f"{self.slug}.html"

    @property
    def href_from_root(self) -> str:
        return f"{self.slug}.html"


def load_articulos() -> list[Articulo]:
    arts: list[Articulo] = []
    for md in sorted(ARTICULOS.rglob("*.md")):
        rel = md.relative_to(ARTICULOS).with_suffix("")
        slug = str(rel).replace("\\", "/")
        text = md.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        arts.append(Articulo(slug=slug, path=md, meta=meta, body=body))
    return arts


# -----------------------------------------------------------------------------
# Render
# -----------------------------------------------------------------------------

def make_resolver(current: Articulo, by_slug: dict[str, Articulo]):
    depth = current.slug.count("/")
    prefix = "../" * depth

    def resolve(target: str, label: str | None) -> str:
        t = target.strip()
        display = label.strip() if label else (by_slug[t].titulo if t in by_slug else t)
        if t in by_slug:
            href = prefix + by_slug[t].href_from_root
            return f'<a class="int" href="{html.escape(href)}">{html.escape(display)}</a>'
        # enlace rojo (no existe)
        return f'<a class="int missing" title="artículo aún no creado">{html.escape(display)}</a>'

    return resolve


def render_infobox(meta: dict, titulo: str, resolve_wikilink=None) -> str:
    box = meta.get("infobox")
    if not isinstance(box, dict) or not box:
        return ""

    def render_value(v: object) -> str:
        s = str(v)
        if resolve_wikilink is None:
            return html.escape(s)
        return render_inline(s, resolve_wikilink)

    rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{render_value(v)}</td></tr>"
        for k, v in box.items()
    )
    return (
        f'<aside class="infobox"><div class="infobox-title">{html.escape(titulo)}</div>'
        f'<table>{rows}</table></aside>'
    )


def render_toc(headings: list[Heading]) -> str:
    top = [h for h in headings if h.level >= 2]
    if len(top) < 2:
        return ""
    out = ['<div class="toc"><div class="toc-title">Contenido</div><ol>']
    stack = [2]
    for h in top:
        while h.level > stack[-1]:
            out.append("<ol>")
            stack.append(stack[-1] + 1)
        while h.level < stack[-1]:
            out.append("</ol>")
            stack.pop()
        out.append(f'<li><a href="#{h.slug}">{html.escape(h.text)}</a></li>')
    while len(stack) > 1:
        out.append("</ol>")
        stack.pop()
    out.append("</ol></div>")
    return "".join(out)


def render_fuentes(meta: dict) -> str:
    fs = meta.get("fuentes")
    if not isinstance(fs, list) or not fs:
        return ""
    items = []
    for f in fs:
        if isinstance(f, dict):
            tipo = f.get("tipo", "")
            ref = f.get("ref", "")
            items.append(f"<li><span class=\"f-tipo\">{html.escape(str(tipo))}</span> {html.escape(str(ref))}</li>")
        else:
            items.append(f"<li>{html.escape(str(f))}</li>")
    return f'<section class="fuentes"><h2 id="fuentes">Fuentes</h2><ul>{"".join(items)}</ul></section>'


PAGE_TEMPLATE = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo} — {site}</title>
<link rel="stylesheet" href="{prefix}assets/wiki.css?v={asset_v}">
<script>document.documentElement.setAttribute('data-theme',localStorage.getItem('wiki-theme')||'light')</script>
</head><body>
<header class="topbar">
  <a class="home" href="{prefix}index.html">{site}</a>
  <nav>
    <a href="{prefix}personas/_index.html">Personas</a>
    <a href="{prefix}organizaciones/_index.html">Organizaciones</a>
    <a href="{prefix}temas/_index.html">Temas</a>
  </nav>
  <button class="theme-toggle" id="theme-toggle" title="Cambiar tema">🌙</button>
  <input id="search" placeholder="Buscar…" autocomplete="off">
</header>
<main class="content">
  <h1 class="page-title">{titulo}</h1>
  {hatnote}
  {infobox}
  {toc}
  <div class="body">{body}</div>
  {fuentes}
  {relacionados}
  <footer class="page-footer">
    <div>Última actualización: {ultima}</div>
    <div>Categoría: {categoria}</div>
  </footer>
</main>
<script src="{prefix}assets/wiki.js?v={asset_v}" defer></script>
<script src="{prefix}assets/wiki-comments.js?v={asset_v}" defer></script>
<script>window.WIKI_INDEX = {index_json};window.WIKI_SLUG = "{wiki_slug}";window.WIKI_COMMENTS_API = "{comments_api}";window.WIKI_COMMENTS_SECRET = "{comments_secret}";</script>
</body></html>
"""


def _compute_asset_version() -> str:
    import hashlib
    h = hashlib.md5()
    for f in sorted(ASSETS.iterdir()):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


ASSET_V = _compute_asset_version()

COMMENTS_API = os.environ.get("WIKI_COMMENTS_API", "")
COMMENTS_SECRET = os.environ.get("WIKI_COMMENTS_SECRET", "")


def render_page(art: Articulo, by_slug: dict[str, Articulo], index_json: str, relacionados_html: str = "") -> str:
    resolver = make_resolver(art, by_slug)
    body_html, headings = render_markdown(art.body, resolver)
    art.html_body = body_html
    art.headings = headings

    depth = art.slug.count("/")
    prefix = "../" * depth

    tipo = art.meta.get("tipo", "")
    hatnote = f'<div class="hatnote">Tipo: <em>{html.escape(str(tipo))}</em></div>' if tipo else ""

    return PAGE_TEMPLATE.format(
        titulo=html.escape(art.titulo),
        site=SITE_TITLE,
        prefix=prefix,
        hatnote=hatnote,
        infobox=render_infobox(art.meta, art.titulo, resolver),
        toc=render_toc(headings),
        body=body_html,
        fuentes=render_fuentes(art.meta),
        relacionados=relacionados_html,
        ultima=html.escape(str(art.meta.get("ultima_actualizacion", "—"))),
        categoria=html.escape(art.categoria),
        index_json=index_json,
        asset_v=ASSET_V,
        wiki_slug=art.slug,
        comments_api=COMMENTS_API,
        comments_secret=COMMENTS_SECRET,
    )


# -----------------------------------------------------------------------------
# Dashboard — data parsers
# -----------------------------------------------------------------------------

@dataclass
class Pendiente:
    texto: str
    source: str  # "correo", "whatsapp", "reuniones"
    deadline: str  # ISO date or ""
    urgency: int  # 0=urgent, 1=deadline, 2=open
    detail: str = ""

    @property
    def sort_key(self) -> tuple:
        return (self.urgency, self.deadline or "9999-99-99")


@dataclass
class Evento:
    titulo: str
    fecha: str  # ISO date
    hora: str
    detalle: str

    @property
    def day(self) -> str:
        try:
            return str(int(self.fecha.split("-")[2]))
        except Exception:
            return "?"

    @property
    def month(self) -> str:
        meses = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
                 "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
                 "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}
        try:
            return meses.get(self.fecha.split("-")[1], "?")
        except Exception:
            return "?"


@dataclass
class Proyecto:
    nombre: str
    org: str
    estado: str
    href: str = ""


@dataclass
class JobOpp:
    titulo: str
    org: str
    fecha: str
    source: str


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def parse_correo_estado() -> tuple[list[Pendiente], list[Evento], list[Proyecto], int]:
    text = _read_file(SECRETARY / "correo" / "estado.md")
    if not text:
        return [], [], [], 0

    pendientes: list[Pendiente] = []
    eventos: list[Evento] = []
    proyectos: list[Proyecto] = []
    inbox_count = 0

    current_section = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip().lower()
            continue

        if current_section == "estado del inbox":
            m = re.search(r"inbox.*?:\s*\**(\d+)\**", stripped)
            if m:
                inbox_count = int(m.group(1))

        if not stripped.startswith("- **"):
            continue

        label_m = re.match(r"^- \*\*(.+?)\*\*:?\s*(.*)", stripped)
        if not label_m:
            continue
        label = label_m.group(1)
        rest = label_m.group(2)

        if "problemas de pago" in current_section:
            detail = re.sub(r"\*\*", "", rest).strip(". ")
            pendientes.append(Pendiente(
                texto=label,
                source="correo",
                deadline="",
                urgency=0,
                detail=detail,
            ))

        elif "proyectos" in current_section and "compromisos" in current_section:
            clean = re.sub(r"\s*<[^>]+>", "", rest)
            clean = re.sub(r"\*\*", "", clean)
            clean = re.sub(r"\s*,\s*,", ",", clean).strip(". ,")
            proyectos.append(Proyecto(
                nombre=label,
                org="",
                estado=clean[:80] if clean else "",
            ))

        elif "eventos" in current_section:
            fecha_m = re.search(r"(\d{1,2})\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)", stripped, re.I)
            hora_m = re.search(r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?|\d{1,2}\s*(?:AM|PM))", stripped)
            eventos.append(Evento(
                titulo=label,
                fecha=_parse_event_date(stripped),
                hora=hora_m.group(1) if hora_m else "",
                detalle=rest[:100] if rest else "",
            ))

        elif "alertas con deadline" in current_section:
            deadline_str = _parse_event_date(rest)
            pendientes.append(Pendiente(
                texto=label,
                source="correo",
                deadline=deadline_str,
                urgency=1 if deadline_str else 2,
                detail=re.sub(r"\*\*", "", rest).strip(". "),
            ))

    return pendientes, eventos, proyectos, inbox_count


MONTH_MAP = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}


def _parse_event_date(text: str) -> str:
    m = re.search(r"(\d{1,2})\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)", text, re.I)
    if m:
        day = int(m.group(1))
        month = MONTH_MAP.get(m.group(2).lower(), "01")
        year = date.today().year
        return f"{year}-{month}-{day:02d}"
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m2:
        return m2.group(0)
    return ""


def parse_acciones_md(path: Path, source: str, max_age_days: int = 30) -> list[Pendiente]:
    """Parser genérico de memory/acciones.md (formato común de los módulos).
    Devuelve sólo items con estado=pendiente que sigan vivos: con deadline
    futuro O detectados en los últimos `max_age_days`. Excluye `[update]`."""
    text = _read_file(path)
    if not text:
        return []

    today = date.today()
    cutoff_iso = date.fromordinal(today.toordinal() - max_age_days).isoformat()

    pendientes: list[Pendiente] = []
    blocks = re.split(r"(?m)^## acc-", text)
    for block in blocks[1:]:
        first_line, _, rest = block.partition("\n")
        if "[update]" in first_line:
            continue
        id_m = re.match(r"(\d{8})-\d{3}", first_line)
        if not id_m:
            continue
        raw = id_m.group(1)
        acc_date_iso = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

        fields: dict[str, str] = {}
        for line in (first_line + "\n" + rest).split("\n"):
            m = re.match(r"^- (\w+):\s*(.+)", line.strip())
            if m:
                fields[m.group(1)] = m.group(2).strip()

        if fields.get("estado", "") != "pendiente":
            continue
        accion = fields.get("accion", "")
        if not accion or accion.startswith("<"):
            continue

        deadline = fields.get("deadline", "—")
        deadline_iso = deadline if re.match(r"\d{4}-\d{2}-\d{2}", deadline) else ""

        if deadline_iso and deadline_iso >= today.isoformat():
            pass
        elif acc_date_iso >= cutoff_iso:
            pass
        else:
            continue

        if deadline_iso:
            try:
                delta = (date.fromisoformat(deadline_iso) - today).days
                urgency = 0 if delta <= 1 else 1
            except ValueError:
                urgency = 2
        else:
            urgency = 2

        pendientes.append(Pendiente(
            texto=accion,
            source=source,
            deadline=deadline_iso,
            urgency=urgency,
            detail=fields.get("contexto", "") or fields.get("responsable", ""),
        ))
    return pendientes


def parse_job_search() -> list[JobOpp]:
    text = _read_file(SECRETARY / "job-search" / "inbox.md")
    if not text:
        return []

    jobs: list[JobOpp] = []
    blocks = re.split(r"^### ", text, flags=re.MULTILINE)
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        header = lines[0].strip()
        fecha_m = re.match(r"(\d{4}-\d{2}-\d{2})\s*—\s*(.*)", header)
        if not fecha_m:
            continue
        fecha = fecha_m.group(1)
        titulo = fecha_m.group(2).strip()
        org = ""
        for line in lines[1:]:
            m = re.match(r"^-\s*\*\*Org\*\*:\s*(.*)", line.strip())
            if m:
                org = m.group(1).strip()
                break
        jobs.append(JobOpp(titulo=titulo, org=org, fecha=fecha, source="LinkedIn"))
    return jobs


def compute_heatmap(arts: list[Articulo], days: int = 90) -> list[int]:
    today = date.today()
    counts: dict[str, int] = {}
    for a in arts:
        d = str(a.meta.get("ultima_actualizacion", ""))
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            counts[d] = counts.get(d, 0) + 1

    cells: list[int] = []
    for i in range(days - 1, -1, -1):
        d = date.fromordinal(today.toordinal() - i)
        c = counts.get(d.isoformat(), 0)
        if c == 0:
            cells.append(0)
        elif c <= 2:
            cells.append(1)
        elif c <= 5:
            cells.append(2)
        elif c <= 10:
            cells.append(3)
        else:
            cells.append(4)
    return cells


# -----------------------------------------------------------------------------
# Dashboard — HTML renderer
# -----------------------------------------------------------------------------

def render_dashboard(arts: list[Articulo], by_slug: dict[str, Articulo], index_json: str) -> str:
    today = date.today()
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")

    correo_pend, eventos, proyectos, inbox_count = parse_correo_estado()
    wa_pend = parse_acciones_md(SECRETARY / "whatsapp" / "memory" / "acciones.md", "whatsapp")
    reu_pend = parse_acciones_md(SECRETARY / "reuniones" / "memory" / "acciones.md", "reuniones")
    jobs = parse_job_search()
    heatmap = compute_heatmap(arts)

    all_pend = sorted(correo_pend + wa_pend + reu_pend, key=lambda p: p.sort_key)
    recent = sorted(arts, key=lambda a: str(a.meta.get("ultima_actualizacion", "")), reverse=True)[:10]
    by_cat: dict[str, list[Articulo]] = {}
    for a in arts:
        by_cat.setdefault(a.categoria, []).append(a)

    # --- Stats ---
    stats_html = (
        '<div class="stats-row">'
        f'<div class="stat-card"><div class="number">{len(arts)}</div><div class="label">Artículos wiki</div></div>'
        f'<div class="stat-card"><div class="number">{inbox_count}</div><div class="label">Correos en inbox</div></div>'
        f'<div class="stat-card"><div class="number">{len(all_pend)}</div><div class="label">Pendientes</div></div>'
        f'<div class="stat-card"><div class="number">{len(eventos)}</div><div class="label">Eventos próximos</div></div>'
        f'<div class="stat-card"><div class="number">{len(proyectos)}</div><div class="label">Proyectos activos</div></div>'
        f'<div class="stat-card"><div class="number">{len(jobs)}</div><div class="label">Oportunidades</div></div>'
        '</div>'
    )

    # --- Pendientes ---
    pend_items = []
    shown = min(len(all_pend), 12)
    for p in all_pend[:shown]:
        dot_cls = {0: "urgent", 1: "deadline", 2: "open"}[p.urgency]
        deadline_html = ""
        if p.urgency == 0:
            detail_text = p.detail if p.detail else "URGENTE"
            deadline_html = f' <span class="action-deadline">{html.escape(detail_text)}</span>'
        elif p.deadline:
            try:
                d = date.fromisoformat(p.deadline)
                delta = (d - today).days
                if delta == 0:
                    label = "hoy"
                elif delta == 1:
                    label = "mañana"
                elif delta < 0:
                    label = f"hace {-delta}d"
                else:
                    label = d.strftime("%-d %b")
                deadline_html = f' <span class="action-deadline">{html.escape(label)}</span>'
            except ValueError:
                pass
        elif p.detail:
            deadline_html = ""

        pend_items.append(
            f'<div class="action-item"><div class="action-dot {dot_cls}"></div><div>'
            f'<div>{html.escape(p.texto)}</div>'
            f'<span class="action-source">{html.escape(p.source)}</span>{deadline_html}'
            f'</div></div>'
        )
    remaining = len(all_pend) - shown
    more_link = f'<div style="text-align:center;padding:0.4rem 0;font-size:0.82em;color:var(--muted)">{remaining} más</div>' if remaining > 0 else ""
    pend_html = (
        f'<section class="dash-card full-card"><div class="dash-card-header">'
        f'<h3>Pendientes</h3><span class="dash-badge">{len(all_pend)}</span></div>'
        f'<div class="dash-card-body">{"".join(pend_items)}{more_link}</div></section>'
    )

    # --- Eventos ---
    evt_items = []
    for e in sorted(eventos, key=lambda x: x.fecha)[:8]:
        evt_items.append(
            f'<div class="event-item">'
            f'<div class="event-date"><div class="day">{html.escape(e.day)}</div>'
            f'<div class="month">{html.escape(e.month)}</div></div>'
            f'<div><div class="event-title">{html.escape(e.titulo)}</div>'
            f'<div class="event-meta">{html.escape(e.hora)} · {html.escape(e.detalle[:80])}</div></div></div>'
        )
    evt_html = (
        f'<div class="dash-card"><div class="dash-card-header">'
        f'<h3>Eventos próximos</h3><span class="dash-badge">{len(eventos)}</span></div>'
        f'<div class="dash-card-body">{"".join(evt_items)}</div></div>'
    )

    # --- Proyectos ---
    proj_items = []
    for p in proyectos[:8]:
        proj_items.append(
            f'<div class="action-item"><div class="action-dot project"></div><div>'
            f'<div>{html.escape(p.nombre)}</div>'
            f'<span class="action-source">{html.escape(p.estado[:80])}</span>'
            f'</div></div>'
        )
    proj_html = (
        f'<div class="dash-card"><div class="dash-card-header">'
        f'<h3>Proyectos activos</h3></div>'
        f'<div class="dash-card-body">{"".join(proj_items)}</div></div>'
    )

    # --- Heatmap ---
    hm_cells = "".join(
        f'<div class="heatmap-cell{" l" + str(c) if c else ""}"></div>'
        for c in heatmap
    )
    hm_html = (
        f'<div class="dash-card"><div class="dash-card-header"><h3>Actividad wiki — 90 días</h3></div>'
        f'<div class="dash-card-body"><div class="heatmap-grid">{hm_cells}</div>'
        f'<div class="heatmap-legend">Menos '
        f'<div class="cell" style="background:var(--accent)"></div>'
        f'<div class="cell" style="background:#c6e48b"></div>'
        f'<div class="cell" style="background:#7bc96f"></div>'
        f'<div class="cell" style="background:#239a3b"></div>'
        f'<div class="cell" style="background:#196127"></div> Más</div></div></div>'
    )

    # --- Source activity bars (count all files recursively) ---
    def _count_md(path: Path) -> int:
        return sum(1 for _ in path.rglob("*.md")) if path.exists() else 0

    source_counts = {
        "Correo": inbox_count,
        "WhatsApp": _count_md(SECRETARY / "whatsapp" / "resumenes"),
        "Reuniones": _count_md(SECRETARY / "reuniones" / "resumenes"),
        "Wiki": len(arts),
    }
    source_cls = {"Correo": "email", "WhatsApp": "whatsapp", "Reuniones": "meetings", "Wiki": "wiki"}
    max_source = max(source_counts.values(), default=1) or 1

    source_bars = "".join(
        f'<div class="source-bar"><span class="source-label">{label}</span>'
        f'<div class="bar-bg"><div class="bar-fill {source_cls[label]}" style="width:{int(count / max_source * 100)}%"></div></div>'
        f'<span class="source-count">{count}</span></div>'
        for label, count in source_counts.items()
    )
    source_html = (
        f'<div class="dash-card"><div class="dash-card-header"><h3>Volumen por fuente</h3></div>'
        f'<div class="dash-card-body">{source_bars}</div></div>'
    )

    # --- Recent wiki ---
    wiki_items = []
    for a in recent:
        fecha = str(a.meta.get("ultima_actualizacion", "—"))
        try:
            d = date.fromisoformat(fecha)
            fecha_fmt = d.strftime("%-d %b")
        except ValueError:
            fecha_fmt = fecha
        wiki_items.append(
            f'<div class="wiki-item"><div><a href="{html.escape(a.href_from_root)}">'
            f'{html.escape(a.titulo)}</a> <span class="cat">{html.escape(a.categoria)}</span></div>'
            f'<div class="date">{html.escape(fecha_fmt)}</div></div>'
        )
    wiki_html = (
        f'<div class="dash-card"><div class="dash-card-header"><h3>Wiki — recientes</h3></div>'
        f'<div class="dash-card-body">{"".join(wiki_items)}</div></div>'
    )

    # --- Job search ---
    job_items = []
    for j in jobs[:6]:
        job_items.append(
            f'<div class="action-item"><div class="action-dot open"></div><div>'
            f'<div>{html.escape(j.titulo)}</div>'
            f'<span class="action-source">{html.escape(j.org)} · {html.escape(j.fecha)} · {html.escape(j.source)}</span>'
            f'</div></div>'
        )
    job_html = (
        f'<div class="dash-card"><div class="dash-card-header">'
        f'<h3>Oportunidades laborales</h3><span class="dash-badge">{len(jobs)}</span></div>'
        f'<div class="dash-card-body">{"".join(job_items)}</div></div>'
    )

    # --- Assemble ---
    body = (
        f'<div class="dashboard">'
        f'<p class="dash-subtitle">Actualizado: {html.escape(now_str)} · Fuentes: correo, WhatsApp, reuniones, wiki</p>'
        f'{stats_html}'
        f'{pend_html}'
        f'<div class="two-col">{evt_html}{proj_html}</div>'
        f'<div class="two-col">{hm_html}{source_html}</div>'
        f'<div class="two-col">{wiki_html}{job_html}</div>'
        f'<footer class="dash-footer">'
        f'<div>Datos: secretary/ (correo, whatsapp, reuniones, wiki)</div>'
        f'<div>Generado: {html.escape(now_str)}</div></footer>'
        f'</div>'
    )

    return PAGE_TEMPLATE.format(
        titulo="Dashboard",
        site=SITE_TITLE,
        prefix="",
        hatnote="",
        infobox="",
        toc="",
        body=body,
        fuentes="",
        relacionados="",
        ultima=today.isoformat(),
        categoria="portada",
        index_json=index_json,
        asset_v=ASSET_V,
        wiki_slug="",
        comments_api=COMMENTS_API,
        comments_secret=COMMENTS_SECRET,
    )


def render_index(arts: list[Articulo], index_json: str) -> str:
    return render_dashboard(arts, {a.slug: a for a in arts}, index_json)


_MD_STRIP_RE = re.compile(
    r"<!--.*?-->|"           # comentarios HTML
    r"```.*?```|"            # bloques de código
    r"`[^`]*`|"              # inline code
    r"\[\[([^|\]]+\|)?|\]\]|"  # wikilinks: [[slug|label]] -> "label" (mantener label)
    r"!\[[^\]]*\]\([^)]*\)|"  # imágenes
    r"\[([^\]]+)\]\([^)]*\)|"  # links: mantener texto
    r"^[#>\-\*\|]\s*|"        # marcadores de inicio de línea
    r"[*_~]+",                # énfasis
    re.DOTALL | re.MULTILINE,
)


def strip_markdown(body: str) -> str:
    """Devuelve texto plano en minúsculas, normalizado, listo para búsqueda fuzzy."""
    text = body
    # mantener label de links/wikilinks: [text](url) -> text, [[slug|label]] -> label
    text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)  # [[slug|label]] -> label
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)            # [[slug]] -> slug
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)       # [text](url) -> text
    # quitar bloques HTML/código y marcadores
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^[#>\-\*\|\s]+", " ", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_search_index(arts: list[Articulo]) -> str:
    import json

    entries = []
    for a in arts:
        body_text = strip_markdown(a.body)
        # Limitar tamaño por documento para mantener el índice manejable
        if len(body_text) > 4000:
            body_text = body_text[:4000]
        entries.append({
            "titulo": a.titulo,
            "href": a.href_from_root,
            "cat": a.categoria,
            "body": body_text,
        })
    return json.dumps(entries, ensure_ascii=False)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def compute_relations(arts: list[Articulo], by_slug: dict[str, Articulo]) -> dict[str, str]:
    from collections import Counter
    from itertools import combinations
    
    outlinks: dict[str, set[str]] = {}
    inlinks: dict[str, set[str]] = {a.slug: set() for a in arts}
    
    for a in arts:
        targets = set()
        for m in WIKILINK.finditer(a.body):
            tgt = m.group(1).strip()
            if tgt and tgt != a.slug and tgt in by_slug:
                targets.add(tgt)
        outlinks[a.slug] = targets

    backlinks = Counter()
    for src, tgts in outlinks.items():
        for t in tgts:
            backlinks[t] += 1
            if t in inlinks:
                inlinks[t].add(src)
                
    EXCLUDE_HUBS = {
        a.slug for a in arts
        if a.meta.get("type") == "profile" or a.meta.get("tipo") == "profile" or a.categoria == "perfil"
    }
    # Fallback/Backward compatibility for default names
    EXCLUDE_HUBS.update({"personas/alvaro-mur", "personas/user-profile", "personas/user-name"})
    cooc = Counter()
    for src, tgts in outlinks.items():
        clean = sorted(
            t for t in tgts
            if t not in EXCLUDE_HUBS and not t.split("/")[-1].startswith("_index")
        )
        for t1, t2 in combinations(clean, 2):
            cooc[(t1, t2)] += 1
            
    related_html_by_slug = {}
    for a in arts:
        bl = sorted(inlinks[a.slug], key=lambda x: backlinks[x], reverse=True)[:5]
        
        my_cooc = {}
        for (t1, t2), count in cooc.items():
            if t1 == a.slug:
                my_cooc[t2] = count
            elif t2 == a.slug:
                my_cooc[t1] = count
        
        valid_cooc = {k: v for k, v in my_cooc.items() if v >= 2}
        co = sorted(valid_cooc.keys(), key=lambda x: valid_cooc[x], reverse=True)[:5]
        
        if not bl and not co:
            related_html_by_slug[a.slug] = ""
            continue
            
        resolver = make_resolver(a, by_slug)
        html_parts = ['<section class="relacionados"><h2 id="relacionados">Relacionados</h2>']
        if bl:
            html_parts.append('<h3>Mencionan este artículo</h3><ul>')
            for t in bl:
                html_parts.append(f'<li>{resolver(t, None)}</li>')
            html_parts.append('</ul>')
        if co:
            html_parts.append('<h3>Aparecen frecuentemente juntos</h3><ul>')
            for t in co:
                html_parts.append(f'<li>{resolver(t, None)} <span class="cooc-count">(×{valid_cooc[t]})</span></li>')
            html_parts.append('</ul>')
        html_parts.append('</section>')
        
        related_html_by_slug[a.slug] = "".join(html_parts)
        
    return related_html_by_slug


def main() -> int:
    if OUTPUT.exists():
        for child in OUTPUT.iterdir():
            if child.name in (".gitkeep", ".git"):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # assets
    out_assets = OUTPUT / "assets"
    out_assets.mkdir(exist_ok=True)
    for a in ASSETS.iterdir():
        shutil.copy2(a, out_assets / a.name)

    arts = load_articulos()
    by_slug = {a.slug: a for a in arts}
    index_json = build_search_index(arts)
    
    relations = compute_relations(arts, by_slug)

    for a in arts:
        page = render_page(a, by_slug, index_json, relations.get(a.slug, ""))
        a.output_path.parent.mkdir(parents=True, exist_ok=True)
        a.output_path.write_text(page, encoding="utf-8")

    (OUTPUT / "index.html").write_text(render_index(arts, index_json), encoding="utf-8")

    print(f"Generados {len(arts)} artículos en {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
