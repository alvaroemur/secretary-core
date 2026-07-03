// Read-side helpers over the Secretary instance: wiki articles, open actions,
// and the people/chat indexes used for entity resolution. All paths are taken
// relative to the resolved instance directory.

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { basename, join } from 'node:path';

/** Read a UTF-8 file, returning '' if it does not exist. */
function readSafe(path) {
  try {
    return readFileSync(path, 'utf8');
  } catch {
    return '';
  }
}

/** List *.md files in a directory (non-recursive), excluding _index/_meta. */
function listMd(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith('.md') && !f.startsWith('_'))
    .map((f) => join(dir, f));
}

/** Minimal YAML-ish frontmatter parser (flat keys + simple `infobox:` block). */
export function parseFrontmatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return {};
  const out = {};
  let curBlock = null;
  for (const line of m[1].split('\n')) {
    if (/^\s/.test(line) && curBlock) {
      const mm = line.trim().match(/^([^:]+):\s*(.*)$/);
      if (mm) out[curBlock][mm[1].trim()] = stripQuotes(mm[2].trim());
      continue;
    }
    const mm = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!mm) continue;
    const key = mm[1];
    const val = mm[2].trim();
    if (val === '') {
      curBlock = key;
      out[key] = {};
    } else {
      curBlock = null;
      out[key] = stripQuotes(val);
    }
  }
  return out;
}

function stripQuotes(s) {
  return s.replace(/^["']|["']$/g, '');
}

/** Extract the prose under the first `## Resumen` heading (a few lines). */
export function extractSummary(text, maxChars = 600) {
  const m = text.match(/##\s+Resumen\s*\n([\s\S]*?)(\n##\s|\n*$)/);
  let body = m ? m[1] : '';
  body = body.replace(/\n{2,}/g, '\n').trim();
  if (!body) {
    // fall back to the first non-frontmatter, non-heading paragraph
    const after = text.replace(/^---[\s\S]*?---\n/, '');
    body = (after.split(/\n##\s/)[0] || '').replace(/^#.*$/gm, '').trim();
  }
  return body.length > maxChars ? body.slice(0, maxChars).trimEnd() + '…' : body;
}

/** Load all wiki articles of a category as {slug, title, frontmatter, body, path}. */
export function loadWikiCategory(instance, category) {
  const dir = join(instance, 'wiki', 'articulos', category);
  return listMd(dir).map((path) => {
    const text = readSafe(path);
    const fm = parseFrontmatter(text);
    return {
      slug: `${category}/${basename(path, '.md')}`,
      shortSlug: basename(path, '.md'),
      title: fm.titulo || basename(path, '.md'),
      category,
      frontmatter: fm,
      text,
      path,
    };
  });
}

/**
 * Find open actions referencing an entity wikilink, scanning the known
 * acciones.md files. Returns lightweight action records.
 */
export function openActionsFor(instance, wikilinkSlug) {
  const files = [
    join(instance, 'whatsapp', 'memory', 'acciones.md'),
    join(instance, 'reuniones', 'memory', 'acciones.md'),
  ];
  const needle = `[[${wikilinkSlug}`; // matches [[personas/x]] and [[personas/x|Alias]]
  const actions = [];
  for (const file of files) {
    const text = readSafe(file);
    if (!text) continue;
    // split into `## acc-...` blocks
    const blocks = text.split(/\n(?=##\s+acc-)/);
    for (const block of blocks) {
      const idm = block.match(/^##\s+(acc-[\w-]+)(\s+\[update\])?/m);
      if (!idm) continue;
      if (!block.includes(needle)) continue;
      const estado = (block.match(/-\s*estado:\s*(.+)/) || [])[1]?.trim() || '';
      if (/lograd|cerrad|hecho|done|complet/i.test(estado)) continue; // skip closed
      actions.push({
        id: idm[1],
        accion: (block.match(/-\s*accion:\s*(.+)/) || [])[1]?.trim() || '',
        deadline: (block.match(/-\s*deadline:\s*(.+)/) || [])[1]?.trim() || '—',
        estado: estado || 'pendiente',
        source: basename(file),
      });
    }
  }
  return actions;
}

/** Crude free-text search across wiki articles. Returns ranked snippets. */
export function recall(instance, query, limit = 8) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const terms = q.split(/\s+/);
  const cats = ['personas', 'organizaciones', 'temas', 'modulos'];
  const hits = [];
  for (const cat of cats) {
    for (const art of loadWikiCategory(instance, cat)) {
      const hay = (art.title + '\n' + art.text).toLowerCase();
      let score = 0;
      for (const t of terms) if (hay.includes(t)) score += 1;
      if (art.title.toLowerCase().includes(q)) score += 3;
      if (score > 0) {
        hits.push({ slug: art.slug, title: art.title, score });
      }
    }
  }
  return hits.sort((a, b) => b.score - a.score).slice(0, limit);
}
