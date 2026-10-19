"""Issue del brief (markdown) -> correo HTML con estilo de resumen de sesión. Sin dependencias."""
from __future__ import annotations
import html
import re

INK, MUTED, LINE = '#0f172a', '#64748b', '#e2e8f0'
ACCENT = {'✅': '#059669', '🧵': '#6366f1', '🤖': '#6366f1', '📅': '#6366f1', '🩺': '#0e7490'}


_REPO = ''


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', r'<a href="\2" style="color:#4f46e5;text-decoration:none;font-weight:500;">\1</a>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'`([^`]+)`', r'<code style="background:#f1f5f9;border-radius:4px;padding:1px 5px;font-size:12px;">\1</code>', t)
    t = re.sub(r'(?<![">/\w])#(\d{3,5})\b', r'<a href="https://github.com/'+_REPO+r'/issues/\1" style="color:#4f46e5;text-decoration:none;">#\1</a>', t)
    return t


def table(rows):
    cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows if not re.match(r'^\|[\s:|-]+\|?$', r)]
    head, body = cells[0], cells[1:]
    th = ''.join(f'<th style="padding:9px 10px;font-weight:600;text-align:left;">{inline(c)}</th>' for c in head)
    out = [f'<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:12px;border:1px solid {LINE};">'
           f'<thead><tr style="background:#f1f5f9;border-bottom:1px solid #cbd5e1;color:#475569;">{th}</tr></thead><tbody>']
    for r in body:
        tds = ''.join(f'<td style="padding:9px 10px;color:#1e293b;vertical-align:top;">{inline(c)}</td>' for c in r)
        out.append(f'<tr style="border-bottom:1px solid {LINE};">{tds}</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)


def block(lines):
    out, i = [], 0
    while i < len(lines):
        l = lines[i].rstrip()
        if not l.strip():
            i += 1; continue
        if l.startswith('|'):
            j = i
            while j < len(lines) and lines[j].startswith('|'): j += 1
            out.append(table(lines[i:j])); i = j; continue
        if re.match(r'^\s*(- |\d+\. )', l):
            j, items = i, []
            while j < len(lines) and re.match(r'^\s*(- |\d+\. )', lines[j]):
                items.append(re.sub(r'^\s*(- |\d+\. )', '', lines[j]).rstrip()); j += 1
            li = []
            for it in items:
                box = ''
                if it.startswith('[ ] '): box, it = '☐ ', it[4:]
                li.append(f'<li style="margin-bottom:7px;list-style:none;margin-left:-20px;">{box}{inline(it)}</li>' if box
                          else f'<li style="margin-bottom:7px;">{inline(it)}</li>')
            out.append(f'<ul style="margin:0 0 10px 0;padding-left:20px;">{"".join(li)}</ul>'); i = j; continue
        if l.startswith('> '):
            out.append(f'<div style="background:#f8fafc;border:1px solid {LINE};border-radius:10px;padding:12px 14px;color:#1e293b;font-size:13px;margin-bottom:12px;">{inline(l[2:])}</div>')
            i += 1; continue
        out.append(f'<p style="margin:0 0 10px 0;">{inline(l)}</p>'); i += 1
    return ''.join(out)


def render(md: str, title: str, url: str, date: str, repo: str = '', number: int | str = '') -> str:
    global _REPO
    _REPO = repo
    md = re.sub(r'<!--.*?-->', '', md, flags=re.S)
    md = re.split(r'\n---\n🤖', md)[0]
    sections = re.split(r'\n---\n', md)
    cards = []
    for sec in sections:
        sec = sec.strip()
        m = re.match(r'^## (\S+)\s+(.*)\n', sec)
        if not m:
            continue
        emoji, name = m.group(1), m.group(2)
        color = ACCENT.get(emoji, '#64748b')
        body = block(sec[m.end():].splitlines())
        cards.append(f'<div style="margin-bottom:26px;"><div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:{color};margin-bottom:10px;">{emoji} {html.escape(name)}</div>'
                     f'<div style="color:#334155;font-size:13px;line-height:1.6;">{body}</div></div>')
    chip = lambda t: f'<span style="display:inline-block;background:#fff;border:1px solid #cbd5e1;border-radius:6px;padding:3px 8px;margin:0 6px 4px 0;">{t}</span>'
    return f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>{html.escape(title)}</title></head>
<body style="margin:0;padding:24px 16px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{INK};line-height:1.6;">
<div style="max-width:640px;margin:0 auto;background:#fff;border:1px solid {LINE};border-radius:16px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,.05);">
<div style="background:#f1f5f9;border-bottom:1px solid {LINE};padding:20px 24px;">
<div style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6366f1;margin-bottom:6px;">Brief diario · Secretary</div>
<h1 style="margin:0 0 12px 0;font-size:20px;font-weight:700;line-height:1.3;">{html.escape(title)}</h1>
<div style="font-size:12px;color:#475569;">{chip('📅 '+date)}{chip(f'📋 Issue #{number}')}</div></div>
<div style="padding:24px;font-size:14px;">{''.join(cards)}
<div style="text-align:center;margin-top:8px;"><a href="{url}" style="display:inline-block;background:#4f46e5;color:#fff;text-decoration:none;font-weight:600;font-size:13px;border-radius:8px;padding:10px 18px;">Abrir el brief completo</a></div></div>
<div style="border-top:1px solid {LINE};padding:14px 24px;font-size:11px;color:{MUTED};">🤖 Generado por Claude Code — briefing · {date}.</div>
</div></body></html>'''

