// Build the "context card" for a chat: the bundle Axon shows in the sidebar
// while you read a WhatsApp conversation. Combines entity resolution, the wiki
// summary, open actions, active objectives, and Álvaro's voice rules.

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { extractSummary, loadWikiCategory, openActionsFor } from './memory.mjs';
import { resolveEntity } from './resolver.mjs';
import { queryObjectives } from './objectives.mjs';

const DEFAULT_ESTILO_VOZ = 'canon/rules/session/estilo-voz.md';

function readSafe(path) {
  try {
    return existsSync(path) ? readFileSync(path, 'utf8') : '';
  } catch {
    return '';
  }
}

/**
 * Resolve voice-rules path from `.secretary.yml` → `paths.estilo_voz`.
 * Zero-dep YAML: only needs the scalar under `paths:`; falls back to canon default.
 */
function resolveEstiloVozRel(instance) {
  const cfg = readSafe(join(instance, '.secretary.yml'));
  if (!cfg) return DEFAULT_ESTILO_VOZ;
  const pathsBlock = cfg.match(/^paths:\s*\n((?:[ \t]+.+\n|\n)*)/m);
  if (!pathsBlock) return DEFAULT_ESTILO_VOZ;
  const m = pathsBlock[1].match(/^[ \t]+estilo_voz:\s*(.+?)\s*$/m);
  if (!m) return DEFAULT_ESTILO_VOZ;
  return m[1].replace(/^['"]|['"]$/g, '').trim() || DEFAULT_ESTILO_VOZ;
}

/** Load Álvaro's voice rules (served to the relay so drafts sound like him). */
export function loadStyleRules(instance) {
  const text = readSafe(join(instance, resolveEstiloVozRel(instance)));
  return text.replace(/^---[\s\S]*?---\n/, '').trim();
}

/** Find a loaded wiki article by full slug (category/short). */
function findArticle(instance, slug) {
  const [cat] = slug.split('/');
  return loadWikiCategory(instance, cat).find((a) => a.slug === slug) || null;
}

/**
 * Build the context card.
 * @param {string} instance
 * @param {{name?:string, chatId?:string}} q
 */
export function buildContextCard(instance, q) {
  const resolution = resolveEntity(instance, q);
  const card = {
    chat: { name: q.name || null, chatId: q.chatId || null },
    resolution: resolution.status,
    entity: null,
    summary: null,
    organizations: [],
    openActions: [],
    objectives: { active: [], suggested: [] },
    styleRules: loadStyleRules(instance),
    pendiente_wiki: false,
  };

  if (resolution.status === 'ambiguous') {
    card.candidates = resolution.candidates;
    return card;
  }
  if (resolution.status !== 'matched') {
    card.pendiente_wiki = true;
    return card;
  }

  const ent = resolution.entity;
  card.entity = { ...ent, confidence: resolution.confidence };

  const art = findArticle(instance, ent.slug);
  if (art) {
    card.summary = extractSummary(art.text);
    const ib = art.frontmatter.infobox || {};
    if (ib['Organización']) card.organizations.push(ib['Organización']);
    // collect org wikilinks referenced in the body
    const orgLinks = [...art.text.matchAll(/\[\[organizaciones\/([\w-]+)(\|[^\]]+)?\]\]/g)];
    for (const m of orgLinks) {
      const label = `[[organizaciones/${m[1]}]]`;
      if (!card.organizations.includes(label)) card.organizations.push(label);
    }
  } else {
    card.pendiente_wiki = true;
  }

  card.openActions = openActionsFor(instance, ent.slug);

  const objs = queryObjectives(instance, { entity: ent.slug });
  card.objectives.active = objs.filter((o) => o.estado === 'activo');
  card.objectives.suggested = objs.filter((o) => o.estado === 'sugerido');

  return card;
}
