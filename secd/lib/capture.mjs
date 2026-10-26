// Capture write-path (Feature 007 P3): persist a WhatsApp conversation that
// Axon just read into the same extractor contract that `whatsapp-monitor`
// (Baileys, retired) used to write, so `wiki-update` integrates it with no
// code changes on its side.
//
// Called by whatsapp-cases.mjs once a case bundle finishes processing. Writes
// the case transcript (not an LLM-synthesized memo); `wiki-update` (run by an
// LLM) does the synthesis into wiki prose when it integrates, same as it
// already does for other extractors' raw consolidated facts.

import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { configScalar } from './config.mjs';
import { resolveEntity } from './resolver.mjs';

function memoryDir(instance) {
  return join(instance, 'extractors', 'whatsapp', 'memory');
}

function summariesDir(instance) {
  return join(instance, 'extractors', 'whatsapp', 'summaries');
}

/** Create the extractor contract dirs (memory/, summaries/) before any write. */
function ensureContractDirs(instance) {
  for (const dir of [memoryDir(instance), summariesDir(instance)]) {
    mkdirSync(dir, { recursive: true });
  }
}

/** Instance owner's display name, read at runtime from `identity.name` in `.secretary.yml`. */
export function ownerName(instance) {
  return configScalar(instance, 'identity.name', 'yo');
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function todayStamp(d = new Date()) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/** Compact YYYYMMDD, used only in acc-<compact>-NNN ids (contract convention). */
function compactStamp(d = new Date()) {
  return `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}`;
}

function timeStamp(d = new Date()) {
  return `${pad2(d.getHours())}${pad2(d.getMinutes())}`;
}

function slugify(s) {
  return (s || 'chat')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'chat';
}

/** Frontmatter for a summary file; the body is the case transcript from whatsapp-cases.mjs. */
function renderSummary({ chatId, alias, jid, isGroup, categoria, periodo, caso, transcript }) {
  const fm = [
    '---',
    'fuente: axon',
    `chat: "${alias || chatId}"`,
    `chat_id: "${chatId}"`,
    `jid: "${jid || (isGroup ? '—' : chatId)}"`,
    `fecha: ${todayStamp()}`,
    'tipo: captura-axon (transcripción cruda, sin sintetizar)',
    `categoria: ${categoria}`,
    `periodo: "${periodo}"`,
    `caso: "${caso || '—'}"`,
    '---',
    '',
  ].join('\n');
  return fm + transcript;
}

/**
 * Write a case summary to summaries/ and index it in chats.md. `transcript` is
 * the rendered case transcript (whatsapp-cases.mjs owns the rendering). With
 * `summaryFile` from an earlier pass (a retried case), the summary is rewritten
 * in place and chats.md is left alone, so a retry never duplicates the entry.
 * Returns the written paths, or null when no message was selected.
 */
export function appendChatCapture(instance, { chatId, alias, jid, isGroup, periodo, mensajes, caso, transcript, summaryFile: previous }) {
  if (!chatId) throw new Error('chatId required');
  if (!mensajes) return null;

  const resolution = resolveEntity(instance, { name: alias, chatId });
  const matched = resolution.status === 'matched';

  // categoria mapping (v1, documented assumption): attended capture has no
  // access to the old whitelist's proyecto/radar distinction, so this maps
  // 1:1 from WhatsApp's own group/individual signal. "radar" (passive
  // monitoring) doesn't apply to an attended read.
  const categoria = isGroup ? 'proyecto' : 'persona';

  ensureContractDirs(instance);
  const dir = summariesDir(instance);
  const body = renderSummary({ chatId, alias, jid, isGroup, categoria, periodo, caso, transcript });
  if (previous) {
    writeFileSync(join(instance, previous), body);
    return { chatsFile: 'extractors/whatsapp/memory/chats.md', summaryFile: previous, entity: matched ? resolution.entity : null };
  }
  const stamp = todayStamp();
  const slug = slugify(alias || chatId);
  let summaryFile = `${stamp}-${timeStamp()}-${slug}.md`;
  let summaryPath = join(dir, summaryFile);
  // avoid clobbering a same-minute re-capture
  let n = 2;
  while (existsSync(summaryPath)) {
    summaryFile = `${stamp}-${timeStamp()}-${slug}-${n}.md`;
    summaryPath = join(dir, summaryFile);
    n += 1;
  }
  writeFileSync(summaryPath, body);

  // temas: only emit a wikilink when it resolves to an *existing* wiki
  // article (the resolver's index is built from real articles, so this is
  // never a forward-ref); otherwise plain text — never invent [[...]] here,
  // that breaks the wikilinks validator (see wiki-update skill notes).
  const temas = matched ? `[[${resolution.entity.slug}]]` : (alias || chatId);

  const chatsFile = join(memoryDir(instance), 'chats.md');
  const entry = [
    '',
    `## ${stamp} — ${alias || chatId}`,
    `- categoria: ${categoria}`,
    `- jid: ${jid || (isGroup ? '—' : chatId)}`,
    `- periodo: "${periodo}"`,
    `- mensajes_procesados: ${mensajes}`,
    `- temas: ${temas}`,
    `- resumen_path: extractors/whatsapp/summaries/${summaryFile}`,
    `- detectado: ${stamp}`,
    '- pendiente_wiki: true',
    '',
  ].join('\n');
  try {
    appendFileSync(chatsFile, entry);
  } catch (err) {
    // no orphan summary: chats.md is the index wiki-update reads
    rmSync(summaryPath, { force: true });
    throw err;
  }

  return {
    chatsFile: `extractors/whatsapp/memory/chats.md`,
    summaryFile: `extractors/whatsapp/summaries/${summaryFile}`,
    entity: matched ? resolution.entity : null,
  };
}

function nextAccionId(instance, stamp) {
  const file = join(memoryDir(instance), 'acciones.md');
  const text = existsSync(file) ? readFileSync(file, 'utf8') : '';
  const re = new RegExp(`## acc-${stamp}-(\\d{3})`, 'g');
  let max = 0;
  let m;
  while ((m = re.exec(text))) max = Math.max(max, parseInt(m[1], 10));
  return `acc-${stamp}-${String(max + 1).padStart(3, '0')}`;
}

/**
 * Append an explicit action to acciones.md. v1 has no automatic action
 * detection (that needs an LLM pass — relay/P2 territory); this only
 * records an action the caller already identified.
 */
export function appendAccion(instance, { responsable, accion, deadline, contexto, origen }) {
  if (!accion) throw new Error('accion required');
  ensureContractDirs(instance);
  const id = nextAccionId(instance, compactStamp());
  const file = join(memoryDir(instance), 'acciones.md');
  const entry = [
    '',
    `## ${id}`,
    `- responsable: ${responsable || ownerName(instance)}`,
    `- accion: ${accion}`,
    `- deadline: ${deadline || '—'}`,
    '- estado: pendiente',
    `- contexto: ${contexto || '—'}`,
    `- origen: ${origen || 'axon'}`,
    `- detectado: ${todayStamp()}`,
    '- pendiente_wiki: true',
    '',
  ].join('\n');
  appendFileSync(file, entry);
  return { id, accionesFile: 'extractors/whatsapp/memory/acciones.md' };
}
