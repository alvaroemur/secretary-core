// Entity resolution: map a WhatsApp chat (a display name / alias, and maybe a
// phone or jid) to a Secretary wiki entity (person or organization).
//
// The reliable signal from a DOM scrape is the contact's display name, so the
// resolver matches primarily on normalized names, with slug and jid as
// secondary keys. It is deliberately conservative: ambiguous matches are
// reported as such rather than guessed.

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { loadWikiCategory } from './memory.mjs';

/** Normalize a name for matching: lowercase, strip accents/emoji/punctuation. */
export function norm(s) {
  return (s || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // diacritics
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

let _cache = null;

/** Build (and cache) the entity index from wiki articles + whatsapp chat names. */
export function buildIndex(instance) {
  if (_cache && _cache.instance === instance) return _cache;
  const entities = [];
  for (const cat of ['personas', 'organizaciones']) {
    for (const art of loadWikiCategory(instance, cat)) {
      const names = new Set([art.title, art.shortSlug.replace(/-/g, ' ')]);
      // include infobox Nombre/Apellido combos when present
      const ib = art.frontmatter.infobox || {};
      if (ib.Nombre && ib.Apellido) names.add(`${ib.Nombre} ${ib.Apellido}`);
      entities.push({
        slug: art.slug,
        title: art.title,
        category: cat,
        keys: [...names].map(norm).filter(Boolean),
      });
    }
  }
  // whatsapp chats.md may carry jid → chat-name hints (best effort)
  const jidByName = {};
  const chats = readSafe(join(instance, 'extractors', 'whatsapp', 'memory', 'chats.md'));
  for (const block of chats.split(/\n(?=##\s)/)) {
    const name = (block.match(/^##\s+[\d-]+\s+—\s+(.+)/m) || [])[1];
    const jid = (block.match(/-\s*jid:\s*(.+)/) || [])[1]?.trim();
    if (name && jid && jid !== '—') jidByName[norm(name)] = jid;
  }
  _cache = { instance, entities, jidByName };
  return _cache;
}

function readSafe(path) {
  try {
    return existsSync(path) ? readFileSync(path, 'utf8') : '';
  } catch {
    return '';
  }
}

/**
 * Resolve a chat to an entity.
 * @param {string} instance
 * @param {{name?: string, chatId?: string}} q
 * @returns {{status:'matched'|'ambiguous'|'unknown', entity?:object, candidates?:object[], confidence?:number}}
 */
export function resolveEntity(instance, q) {
  const idx = buildIndex(instance);
  const nq = norm(q.name || q.chatId || '');
  if (!nq) return { status: 'unknown' };

  const scored = [];
  for (const e of idx.entities) {
    let best = 0;
    for (const k of e.keys) {
      if (!k) continue;
      if (k === nq) best = Math.max(best, 1.0);
      else if (k.includes(nq) || nq.includes(k)) best = Math.max(best, 0.7);
      else {
        // token overlap
        const a = new Set(k.split(' '));
        const b = new Set(nq.split(' '));
        const inter = [...a].filter((t) => b.has(t)).length;
        const overlap = inter / Math.max(a.size, b.size);
        if (overlap >= 0.5) best = Math.max(best, 0.5 + overlap * 0.2);
      }
    }
    if (best > 0) scored.push({ ...e, confidence: Number(best.toFixed(2)) });
  }
  scored.sort((a, b) => b.confidence - a.confidence);

  if (scored.length === 0) return { status: 'unknown' };
  const top = scored[0];
  const second = scored[1];
  // exact or clearly-ahead match
  if (top.confidence >= 1.0 || !second || top.confidence - second.confidence >= 0.25) {
    return {
      status: 'matched',
      confidence: top.confidence,
      entity: { slug: top.slug, title: top.title, category: top.category },
    };
  }
  return {
    status: 'ambiguous',
    candidates: scored.slice(0, 4).map((e) => ({ slug: e.slug, title: e.title, confidence: e.confidence })),
  };
}

/** Reset the cache (used by tests / after instance writes). */
export function resetIndex() {
  _cache = null;
}
