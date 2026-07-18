// Read/write the objectives store under the instance at `objetivos/`.
// Objectives are markdown files with frontmatter (see objetivos/_schema.md).
// L0 (strategy) live in `estrategia/`, L1 (relationship) in `relaciones/`.

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { parseFrontmatter } from './memory.mjs';

function storeDir(instance) {
  return join(instance, 'objetivos');
}

function walk(dir) {
  if (!existsSync(dir)) return [];
  const out = [];
  for (const name of readdirSync(dir, { withFileTypes: true })) {
    if (name.isDirectory()) out.push(...walk(join(dir, name.name)));
    else if (name.name.endsWith('.md') && !name.name.startsWith('_') && name.name !== 'README.md')
      out.push(join(dir, name.name));
  }
  return out;
}

/** Load every objective as a record. */
export function loadObjectives(instance) {
  return walk(storeDir(instance))
    .map((path) => {
      const text = readFileSync(path, 'utf8');
      const fm = parseFrontmatter(text);
      if (!fm.id) return null;
      const bodyM = text.match(/##\s+Objetivo\s*\n([\s\S]*?)(\n##\s|\n*$)/);
      return {
        id: fm.id,
        nivel: fm.nivel || '',
        titulo: fm.titulo || '',
        parent: fm.parent && fm.parent !== '—' ? fm.parent : null,
        entidad: fm.entidad && fm.entidad !== '—' ? fm.entidad : null,
        estado: fm.estado || 'sugerido',
        origen: fm.origen || 'user',
        ambito: fm.ambito || '',
        descripcion: bodyM ? bodyM[1].trim() : '',
        path,
      };
    })
    .filter(Boolean);
}

/** Filter objectives by entity wikilink and/or state/level. */
export function queryObjectives(instance, { entity, estado, nivel } = {}) {
  let objs = loadObjectives(instance);
  if (entity) {
    // entity may be a slug like "personas/luna-rondon"; match inside the wikilink
    objs = objs.filter((o) => o.entidad && o.entidad.includes(entity));
  }
  if (estado) objs = objs.filter((o) => o.estado === estado);
  if (nivel) objs = objs.filter((o) => o.nivel === nivel);
  return objs;
}

/** Next free id for a given day, e.g. obj-20260610-005. */
function nextId(instance, dateStr) {
  const ids = loadObjectives(instance)
    .map((o) => o.id)
    .filter((id) => id.startsWith(`obj-${dateStr}-`));
  let max = 0;
  for (const id of ids) {
    const n = Number(id.split('-').pop());
    if (n > max) max = n;
  }
  return `obj-${dateStr}-${String(max + 1).padStart(3, '0')}`;
}

/**
 * Create or update an objective. For updates, pass an existing `id`. For
 * creation, pass `dateStr` (YYYYMMDD) so the daemon can mint a deterministic id
 * (the daemon supplies the date; this module never calls Date.now()).
 *
 * Returns {id, path, created}.
 */
export function upsertObjective(instance, payload, dateStr) {
  const objs = loadObjectives(instance);
  const existing = payload.id ? objs.find((o) => o.id === payload.id) : null;

  const id = existing ? existing.id : nextId(instance, dateStr);
  const nivel = payload.nivel || existing?.nivel || 'L1';
  const subdir = nivel === 'L0' ? 'estrategia' : 'relaciones';
  const dir = join(storeDir(instance), subdir);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const path = existing?.path || join(dir, `${id}.md`);

  const fm = {
    id,
    nivel,
    titulo: payload.titulo ?? existing?.titulo ?? '',
    parent: payload.parent ?? existing?.parent ?? '—',
    entidad: payload.entidad ?? existing?.entidad ?? '—',
    estado: payload.estado ?? existing?.estado ?? 'sugerido',
    origen: payload.origen ?? existing?.origen ?? 'relay',
    ambito: payload.ambito ?? existing?.ambito ?? '—',
    creado: existing ? frontmatterField(existing.path, 'creado') || dateStr : dateStr,
    actualizado: dateStr,
  };
  const desc = payload.descripcion ?? existing?.descripcion ?? '(sin descripción)';

  const out =
    `---\n` +
    `id: ${fm.id}\n` +
    `nivel: ${fm.nivel}\n` +
    `titulo: ${fm.titulo}\n` +
    `parent: ${fm.parent || '—'}\n` +
    `entidad: ${quoteIfLink(fm.entidad)}\n` +
    `estado: ${fm.estado}\n` +
    `origen: ${fm.origen}\n` +
    `ambito: ${fm.ambito}\n` +
    `creado: ${fmtDate(fm.creado)}\n` +
    `actualizado: ${fmtDate(fm.actualizado)}\n` +
    `acciones: []\n` +
    `---\n\n## Objetivo\n\n${desc}\n`;

  writeFileSync(path, out);
  return { id, path, created: !existing };
}

function quoteIfLink(v) {
  if (!v || v === '—') return '—';
  return v.startsWith('"') ? v : `"${v}"`;
}
function fmtDate(d) {
  // d is YYYYMMDD or YYYY-MM-DD
  if (/^\d{8}$/.test(d)) return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
  return d;
}
function frontmatterField(path, key) {
  try {
    const fm = parseFrontmatter(readFileSync(path, 'utf8'));
    return fm[key];
  } catch {
    return null;
  }
}
