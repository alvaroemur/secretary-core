// Capture write-path (Feature 007 P3): persist a WhatsApp conversation that
// Axon just read into the same extractor contract that `whatsapp-monitor`
// (Baileys, retired) used to write, so `wiki-update` integrates it with no
// code changes on its side.
//
// v1 scope: writes a raw transcript (not an LLM-synthesized memo — Axon's
// capture path is synchronous JS with no subagent). `wiki-update` (run by an
// LLM) does the synthesis into wiki prose when it integrates, same as it
// already does for other extractors' raw consolidated facts.

import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { resolveEntity } from './resolver.mjs';

function memoryDir(instance) {
  return join(instance, 'extractors', 'whatsapp', 'memory');
}

function summariesDir(instance) {
  return join(instance, 'extractors', 'whatsapp', 'summaries');
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

/** Period "YYYY-MM-DD a YYYY-MM-DD" from message timestamps; falls back to today. */
function periodFromMessages(messages) {
  const stamps = messages
    .map((m) => (typeof m.timestamp === 'number' ? new Date(m.timestamp) : null))
    .filter(Boolean);
  if (stamps.length === 0) {
    const t = todayStamp();
    return `${t} a ${t}`;
  }
  const min = new Date(Math.min(...stamps.map((d) => d.getTime())));
  const max = new Date(Math.max(...stamps.map((d) => d.getTime())));
  return `${todayStamp(min)} a ${todayStamp(max)}`;
}

/** Render the raw transcript body (frontmatter + message list) written to summaries/. */
function renderTranscript({ chatId, alias, jid, isGroup, categoria, messages }) {
  const fm = [
    '---',
    'fuente: axon',
    `chat: "${alias || chatId}"`,
    `chat_id: "${chatId}"`,
    `jid: "${jid || (isGroup ? '—' : chatId)}"`,
    `fecha: ${todayStamp()}`,
    'tipo: captura-axon (transcripción cruda, sin sintetizar)',
    `categoria: ${categoria}`,
    `periodo: "${periodFromMessages(messages)}"`,
    '---',
    '',
  ].join('\n');

  const lines = messages.map((m) => {
    const who = m.type === 'message-out' ? 'Álvaro' : (m.senderName || alias || 'contacto');
    const ts = m.backupTimestamp || (typeof m.timestamp === 'number' ? new Date(m.timestamp).toISOString() : '—');
    let content = m.content;
    if (content == null) content = `[${m.format || 'contenido'}]`;
    else if (typeof content !== 'string') content = `[${m.format || 'adjunto'}]`;
    return `- **${who}** (${ts}, ${m.format || 'chat'}): ${content}`;
  });

  return fm + '## Transcripción\n\n' + lines.join('\n') + '\n';
}

/** Append one section to chats.md and write its summary file. Returns the written paths, or null if there were no new messages to record. */
export function appendChatCapture(instance, { chatId, alias, jid, isGroup, messages }) {
  if (!chatId) throw new Error('chatId required');
  if (!Array.isArray(messages) || messages.length === 0) return null;

  const resolution = resolveEntity(instance, { name: alias, chatId });
  const matched = resolution.status === 'matched';

  // categoria mapping (v1, documented assumption): attended capture has no
  // access to the old whitelist's proyecto/radar distinction, so this maps
  // 1:1 from WhatsApp's own group/individual signal. "radar" (passive
  // monitoring) doesn't apply to an attended read.
  const categoria = isGroup ? 'proyecto' : 'persona';

  const dir = summariesDir(instance);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
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
  writeFileSync(summaryPath, renderTranscript({ chatId, alias, jid, isGroup, categoria, messages }));

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
    `- periodo: "${periodFromMessages(messages)}"`,
    `- mensajes_procesados: ${messages.length}`,
    `- temas: ${temas}`,
    `- resumen_path: extractors/whatsapp/summaries/${summaryFile}`,
    `- detectado: ${stamp}`,
    '- pendiente_wiki: true',
    '',
  ].join('\n');
  appendFileSync(chatsFile, entry);

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
  const id = nextAccionId(instance, compactStamp());
  const file = join(memoryDir(instance), 'acciones.md');
  const entry = [
    '',
    `## ${id}`,
    `- responsable: ${responsable || 'Álvaro Mur'}`,
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
