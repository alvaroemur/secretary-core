import { createHash } from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs';
import { basename, dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { loadLlmConfig } from './llm.mjs';

export const CASE_SCHEMA_VERSION = '1.1';
const MAX_MESSAGES = 5000;
const MAX_MEDIA_BYTES = 100 * 1024 * 1024;
const MAX_CASE_BYTES = 1024 * 1024 * 1024;
const MAX_TEXT_CHARS = 2 * 1024 * 1024;
const ALLOWED_DIRECTIONS = new Set(['in', 'out']);
const ALLOWED_KINDS = new Set([
  'text', 'audio', 'image', 'document', 'video', 'sticker', 'location', 'contact',
]);

function readJson(path, fallback = null) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJsonAtomic(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temp = `${path}.${process.pid}.tmp`;
  writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  renameSync(temp, path);
}

function scalar(value) {
  return value.trim().replace(/\s+#.*$/, '').replace(/^['"]|['"]$/g, '');
}

function readConfigScalars(instance) {
  const path = join(instance, '.secretary.yml');
  const config = existsSync(path) ? readFileSync(path, 'utf8') : '';
  const values = new Map();
  const stack = [];
  for (const line of config.split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith('#')) continue;
    const indent = line.length - line.trimStart().length;
    const text = line.trim();
    const match = text.match(/^([A-Za-z0-9_.-]+):(?:\s*(.*))?$/);
    if (!match) continue;
    while (stack.length && stack.at(-1).indent >= indent) stack.pop();
    const keyPath = [...stack.map((entry) => entry.key), match[1]].join('.');
    if (match[2]) values.set(keyPath, scalar(match[2]));
    else stack.push({ indent, key: match[1] });
  }
  return values;
}

/** Resolve the canonical paths.extractors.whatsapp.inbox, then exact legacy aliases. */
export function resolveCasesRoot(instance) {
  const values = readConfigScalars(instance);
  const inbox =
    values.get('paths.extractors.whatsapp.inbox') ||
    values.get('paths.whatsapp.inbox') ||
    'extractors/whatsapp/inbox';
  const root = isAbsolute(inbox) ? resolve(inbox) : resolve(instance, inbox);
  const rel = relative(resolve(instance), root);
  if (rel.startsWith('..') || isAbsolute(rel)) {
    throw new Error('configured WhatsApp inbox must stay inside SECRETARY_INSTANCE');
  }
  return join(root, 'cases');
}

function validateTimezone(value) {
  if (typeof value !== 'string' || value.length > 100) throw new Error('timezone is invalid');
  try {
    new Intl.DateTimeFormat('en', { timeZone: value }).format(0);
    return value;
  } catch {
    throw new Error('timezone is invalid');
  }
}

function resolveTimezone(instance, payloadTimezone) {
  if (payloadTimezone) return validateTimezone(payloadTimezone);
  const configured = instance ? readConfigScalars(instance).get('timezone') : null;
  return validateTimezone(configured || 'UTC');
}

function localTimestamp(epochMs, timezone) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
      timeZoneName: 'longOffset',
    }).formatToParts(epochMs).map((part) => [part.type, part.value]),
  );
  return {
    timestamp_local: `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} ${parts.timeZoneName} [${timezone}]`,
    local_date: `${parts.year}-${parts.month}-${parts.day}`,
  };
}

export function slug(value, fallback = 'case') {
  const cleaned = String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
  return cleaned || fallback;
}

function safeId(value, field) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_.:@-]{1,240}$/.test(value)) {
    throw new Error(`${field} is invalid`);
  }
  if (value.includes('..') || value.includes('/') || value.includes('\\')) {
    throw new Error(`${field} contains an unsafe path segment`);
  }
  return value;
}

function normalizeTimestamp(message, timezone) {
  const epoch = Number(message.timestamp_epoch);
  const parsed = Date.parse(message.timestamp_iso);
  if (!Number.isFinite(epoch) || epoch <= 0 || !Number.isFinite(parsed)) {
    throw new Error('message timestamp is invalid');
  }
  const epochMs = epoch < 1e12 ? epoch * 1000 : epoch;
  if (Math.abs(epochMs - parsed) > 120_000) {
    throw new Error('message timestamp fields disagree');
  }
  return {
    timestamp_iso: new Date(parsed).toISOString(),
    timestamp_epoch: Math.floor(epochMs / 1000),
    source_timestamp_local: message.timestamp_local == null
      ? null
      : String(message.timestamp_local).slice(0, 160),
    ...localTimestamp(epochMs, timezone),
  };
}

function normalizeMedia(media, messageId) {
  if (!media) return null;
  if (typeof media.selected !== 'boolean') {
    throw new Error(`media decision is unresolved for ${messageId}`);
  }
  const mediaId = safeId(String(media.media_id || `${messageId}-media`), 'media_id');
  const mime = String(media.mime_type || '').toLowerCase();
  if (!/^[a-z0-9.+-]+\/[a-z0-9.+-]+$/.test(mime)) throw new Error('media MIME is invalid');
  const selected = media.selected !== false;
  const declaredSize = Number(media.size_bytes);
  if (!Number.isInteger(declaredSize) || declaredSize < 0 || declaredSize > MAX_MEDIA_BYTES) {
    throw new Error('media size is invalid');
  }
  if (!selected) {
    return {
      media_id: mediaId,
      mime_type: mime,
      size_bytes: declaredSize,
      filename: basename(String(media.filename || mediaId)).replace(/[^A-Za-z0-9._-]/g, '_'),
      duration_seconds: Number.isFinite(Number(media.duration_seconds))
        ? Number(media.duration_seconds)
        : null,
      selected: false,
      bytes: Buffer.alloc(0),
    };
  }
  const content = String(media.content_base64 || '');
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(content)) throw new Error('media base64 is invalid');
  const bytes = Buffer.from(content, 'base64');
  if (bytes.length > MAX_MEDIA_BYTES) throw new Error('media exceeds 100 MiB');
  if (declaredSize !== bytes.length) throw new Error('media size does not match content');
  return {
    media_id: mediaId,
    mime_type: mime,
    size_bytes: bytes.length,
    filename: basename(String(media.filename || mediaId)).replace(/[^A-Za-z0-9._-]/g, '_'),
    duration_seconds: Number.isFinite(Number(media.duration_seconds))
      ? Number(media.duration_seconds)
      : null,
    selected,
    bytes,
  };
}

export function validateCasePayload(payload, instance = null) {
  if (!payload || typeof payload !== 'object') throw new Error('JSON object required');
  const accountId = safeId(payload.account_profile_id, 'account_profile_id');
  const chatId = safeId(payload.chat_id, 'chat_id');
  const caseId = safeId(payload.case_id, 'case_id');
  const timezone = resolveTimezone(instance, payload.timezone);
  if (!Array.isArray(payload.messages) || payload.messages.length === 0) {
    throw new Error('messages must be a non-empty array');
  }
  if (payload.messages.length > MAX_MESSAGES) throw new Error(`messages exceeds ${MAX_MESSAGES}`);
  const seen = new Set();
  const seenOrders = new Set();
  let totalBytes = 0;
  const messages = payload.messages.map((input, index) => {
    const messageId = safeId(input.message_id, `messages[${index}].message_id`);
    if (seen.has(messageId)) throw new Error(`duplicate message_id: ${messageId}`);
    seen.add(messageId);
    const sourceOrder = Number(input.source_order);
    if (!Number.isInteger(sourceOrder) || sourceOrder < 0 || seenOrders.has(sourceOrder)) {
      throw new Error(`source_order is invalid or duplicated for ${messageId}`);
    }
    seenOrders.add(sourceOrder);
    if (typeof input.selected !== 'boolean') {
      throw new Error(`message selection is invalid for ${messageId}`);
    }
    if (!ALLOWED_DIRECTIONS.has(input.direction)) throw new Error(`invalid direction for ${messageId}`);
    const kind = String(input.kind || 'text').toLowerCase();
    if (!ALLOWED_KINDS.has(kind)) throw new Error(`invalid kind for ${messageId}`);
    const timestamps = normalizeTimestamp(input, timezone);
    const media = normalizeMedia(input.media, messageId);
    if (media?.selected && kind === 'audio' && !media.mime_type.startsWith('audio/')) {
      throw new Error(`audio MIME does not match kind for ${messageId}`);
    }
    if (media?.selected && kind === 'image' && !media.mime_type.startsWith('image/')) {
      throw new Error(`image MIME does not match kind for ${messageId}`);
    }
    const text = input.text == null ? null : String(input.text);
    const caption = input.caption == null ? null : String(input.caption);
    if ((text?.length || 0) > MAX_TEXT_CHARS || (caption?.length || 0) > MAX_TEXT_CHARS) {
      throw new Error(`message text exceeds 2 MiB for ${messageId}`);
    }
    if (media) totalBytes += media.size_bytes;
    return {
      message_id: messageId,
      source_order: sourceOrder,
      ...timestamps,
      sender_name: String(input.sender_name || (input.direction === 'out' ? 'You' : 'Unknown')).slice(0, 240),
      direction: input.direction,
      kind,
      text,
      caption,
      selected: input.selected !== false,
      media,
    };
  });
  if (totalBytes > MAX_CASE_BYTES) throw new Error('case media exceeds 1 GiB');
  messages.sort((a, b) =>
    a.timestamp_epoch - b.timestamp_epoch ||
    a.source_order - b.source_order ||
    a.message_id.localeCompare(b.message_id));
  return {
    case_id: caseId,
    account_profile_id: accountId,
    chat_id: chatId,
    chat_name: String(payload.chat_name || 'chat').slice(0, 240),
    title: payload.title == null ? null : String(payload.title).slice(0, 240),
    timezone,
    messages,
    total_bytes: totalBytes,
  };
}

export function estimateCase(payload, instance) {
  const normalized = validateCasePayload(payload, instance);
  const selected = normalized.messages.filter((m) => m.selected);
  const media = selected.filter((m) => m.media?.selected);
  const pricing = readJson(join(instance, '.secd', 'capture.json'), {})?.pricing || {};
  let cost = 0;
  const missing = [];
  const audioSeconds = media
    .filter((m) => m.kind === 'audio')
    .reduce((sum, m) => sum + (m.media.duration_seconds || 0), 0);
  const imageCount = media.filter((m) => m.kind === 'image').length;
  if (audioSeconds > 0) {
    if (Number.isFinite(Number(pricing.audio_per_minute_usd))) {
      cost += (audioSeconds / 60) * Number(pricing.audio_per_minute_usd);
    } else missing.push('audio_per_minute_usd');
  }
  if (imageCount > 0) {
    if (Number.isFinite(Number(pricing.image_per_item_usd))) {
      cost += imageCount * Number(pricing.image_per_item_usd);
    } else missing.push('image_per_item_usd');
  }
  return {
    messages: selected.length,
    media: media.length,
    size_bytes: media.reduce((sum, m) => sum + m.media.size_bytes, 0),
    estimated_cost_usd: missing.length ? null : Number(cost.toFixed(6)),
    cost_configured: missing.length === 0,
    missing_rates: missing,
  };
}

function extensionFor(mime) {
  const known = {
    'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'audio/mp4': '.m4a',
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
    'video/mp4': '.mp4', 'application/pdf': '.pdf',
  };
  return known[mime] || '';
}

function selectedCounts(messages) {
  const selected = messages.filter((m) => m.selected);
  return {
    messages: selected.length,
    media: selected.filter((m) => m.media?.selected).length,
  };
}

function publicMessage(message, mediaRecord) {
  return {
    message_id: message.message_id,
    source_order: message.source_order,
    timestamp_iso: message.timestamp_iso,
    timestamp_epoch: message.timestamp_epoch,
    timestamp_local: message.timestamp_local,
    source_timestamp_local: message.source_timestamp_local,
    sender_name: message.sender_name,
    direction: message.direction,
    kind: message.kind,
    text: message.text,
    caption: message.caption,
    selected: message.selected,
    media: message.media ? {
      media_id: message.media.media_id,
      mime_type: message.media.mime_type,
      size_bytes: message.media.size_bytes,
      filename: message.media.filename,
      duration_seconds: message.media.duration_seconds,
      selected: message.media.selected,
      ...(mediaRecord || {}),
    } : null,
  };
}

function renderTranscript(manifest, messages) {
  const lines = [`# ${manifest.title || `${manifest.date} — ${manifest.chat_name}`}`, ''];
  for (const message of messages.filter((m) => m.selected)) {
    lines.push(`## ${message.sender_name} — ${message.timestamp_local}`, '');
    if (message.text) lines.push(message.text, '');
    if (message.caption && message.caption !== message.text) lines.push(`Caption: ${message.caption}`, '');
    if (message.media?.selected) {
      lines.push(`Media: ${message.media.absolute_path || 'unavailable'}`, '');
      if (message.media.processing?.transcript_faithful) {
        lines.push('Faithful transcription:', '', message.media.processing.transcript_faithful, '');
        lines.push('Clean transcription:', '', message.media.processing.transcript_clean || '', '');
      }
      if (message.media.processing?.description) {
        lines.push('Factual description:', '', message.media.processing.description, '');
        lines.push('OCR:', '', message.media.processing.ocr || '(none)', '');
        lines.push('Caption relation:', '', message.media.processing.caption_relation || '(none)', '');
      }
      if (message.media.error) lines.push(`Processing error: ${message.media.error.message}`, '');
    }
  }
  return `${lines.join('\n').trim()}\n`;
}

async function transcribeAudio(instance, path, mime, fetchImpl) {
  const loaded = loadLlmConfig(instance);
  const cfg = loaded?.provider === 'openai'
    ? loaded
    : process.env.OPENAI_API_KEY
      ? { provider: 'openai', apiKey: process.env.OPENAI_API_KEY, model: process.env.SECD_LLM_MODEL || 'gpt-4o-mini' }
      : null;
  if (!cfg) throw new Error('OpenAI is not configured for audio');
  const form = new FormData();
  form.append('model', process.env.SECD_WHISPER_MODEL || 'whisper-1');
  form.append('response_format', 'verbose_json');
  form.append('file', new Blob([readFileSync(path)], { type: mime }), basename(path));
  const response = await fetchImpl('https://api.openai.com/v1/audio/transcriptions', {
    method: 'POST',
    headers: { authorization: `Bearer ${cfg.apiKey}` },
    body: form,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data?.error?.message || `OpenAI HTTP ${response.status}`);
  const faithful = String(data.text || '').trim();
  if (!faithful) throw new Error('Whisper returned an empty transcription');
  const cleanResponse = await fetchImpl('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${cfg.apiKey}` },
    body: JSON.stringify({
      model: cfg.model,
      temperature: 0,
      messages: [
        { role: 'system', content: 'Clean transcription punctuation and obvious verbal fillers only. Preserve all facts and meaning. Do not summarize. Return plain text.' },
        { role: 'user', content: faithful },
      ],
    }),
  });
  const cleanData = await cleanResponse.json();
  if (!cleanResponse.ok) throw new Error(cleanData?.error?.message || `OpenAI HTTP ${cleanResponse.status}`);
  return {
    transcript_faithful: faithful,
    transcript_clean: String(cleanData.choices?.[0]?.message?.content || '').trim(),
  };
}

async function describeImage(instance, path, mime, caption, fetchImpl) {
  const loaded = loadLlmConfig(instance);
  const cfg = loaded?.provider === 'openai'
    ? loaded
    : process.env.OPENAI_API_KEY
      ? { provider: 'openai', apiKey: process.env.OPENAI_API_KEY, model: process.env.SECD_LLM_MODEL || 'gpt-4o-mini' }
      : null;
  if (!cfg) throw new Error('OpenAI is not configured for images');
  const response = await fetchImpl('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${cfg.apiKey}` },
    body: JSON.stringify({
      model: cfg.model,
      temperature: 0,
      response_format: { type: 'json_object' },
      messages: [{
        role: 'user',
        content: [
          { type: 'text', text: `Inspect only this image. Return JSON with description (factual), ocr (verbatim visible text), and caption_relation (how it relates to this caption, without conversation analysis). Caption: ${caption || '(none)'}` },
          { type: 'image_url', image_url: { url: `data:${mime};base64,${readFileSync(path).toString('base64')}` } },
        ],
      }],
    }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data?.error?.message || `OpenAI HTTP ${response.status}`);
  const parsed = JSON.parse(data.choices?.[0]?.message?.content || '{}');
  return {
    description: String(parsed.description || ''),
    ocr: String(parsed.ocr || ''),
    caption_relation: String(parsed.caption_relation || ''),
  };
}

async function processBundle(instance, bundlePath, fetchImpl = globalThis.fetch) {
  const manifestPath = join(bundlePath, 'manifest.json');
  const manifest = readJson(manifestPath);
  const messages = readFileSync(join(bundlePath, 'messages.jsonl'), 'utf8')
    .trim().split('\n').filter(Boolean).map(JSON.parse);
  manifest.status = 'processing';
  manifest.updated_at = new Date().toISOString();
  manifest.failures = [];
  manifest.processed_counts = {
    messages: messages.filter((m) => m.selected).length,
    media: messages.filter((m) => m.selected && m.media?.selected && m.media.processing && !m.media.error).length,
  };
  writeJsonAtomic(manifestPath, manifest);
  for (const message of messages) {
    if (!message.selected || !message.media?.selected) continue;
    const existing = message.media.processing;
    if (existing && !message.media.error) continue;
    try {
      let processing = null;
      if (message.kind === 'audio') {
        processing = await transcribeAudio(instance, message.media.absolute_path, message.media.mime_type, fetchImpl);
      } else if (message.kind === 'image') {
        processing = await describeImage(instance, message.media.absolute_path, message.media.mime_type, message.caption, fetchImpl);
      } else {
        processing = { preserved: true };
      }
      message.media.processing = processing;
      delete message.media.error;
    } catch (error) {
      message.media.error = {
        code: 'processing_failed',
        message: String(error.message || error),
        retryable: true,
      };
      manifest.failures.push({ message_id: message.message_id, ...message.media.error });
    }
    manifest.processed_counts.media = messages
      .filter((m) => m.selected && m.media?.selected && m.media.processing && !m.media.error).length;
    manifest.updated_at = new Date().toISOString();
    writeJsonAtomic(manifestPath, manifest);
  }
  const counts = selectedCounts(messages);
  manifest.processed_counts = {
    messages: messages.filter((m) => m.selected).length,
    media: messages.filter((m) => m.selected && m.media?.selected && !m.media.error).length,
  };
  const consistent =
    counts.messages === manifest.selected_counts.messages &&
    counts.media === manifest.selected_counts.media;
  manifest.status = consistent && manifest.failures.length === 0 ? 'ready' : 'partial';
  manifest.updated_at = new Date().toISOString();
  writeFileSync(join(bundlePath, 'messages.jsonl'), `${messages.map(JSON.stringify).join('\n')}\n`);
  writeFileSync(join(bundlePath, 'transcript.md'), renderTranscript(manifest, messages));
  writeJsonAtomic(manifestPath, manifest);
  return manifest;
}

export async function createCase(instance, payload, options = {}) {
  const normalized = validateCasePayload(payload, instance);
  const date = normalized.messages[0].local_date;
  const root = resolveCasesRoot(instance);
  mkdirSync(root, { recursive: true });
  const bundleName = `${date}-${slug(normalized.chat_name, 'chat')}-${slug(normalized.case_id)}`;
  const bundlePath = join(root, bundleName);
  const rel = relative(root, bundlePath);
  if (rel.startsWith('..') || isAbsolute(rel)) throw new Error('unsafe bundle path');
  const manifestPath = join(bundlePath, 'manifest.json');
  if (existsSync(manifestPath)) {
    const existing = readJson(manifestPath);
    if (existing?.case_id !== normalized.case_id ||
        existing?.account_profile_id !== normalized.account_profile_id) {
      throw new Error('case bundle collision');
    }
    if (options.defer) return existing;
    return processBundle(instance, bundlePath, options.fetchImpl);
  }
  mkdirSync(join(bundlePath, 'originals'), { recursive: true });
  const records = [];
  for (const message of normalized.messages) {
    if (!message.selected) continue;
    let mediaRecord = null;
    if (message.media?.selected) {
      const hash = createHash('sha256').update(message.media.bytes).digest('hex');
      const name = `${slug(message.message_id)}-${slug(message.media.media_id)}${extensionFor(message.media.mime_type)}`;
      const path = join(bundlePath, 'originals', name);
      const pathRel = relative(bundlePath, path);
      if (pathRel.startsWith('..') || isAbsolute(pathRel)) throw new Error('unsafe media path');
      writeFileSync(path, message.media.bytes, { flag: 'wx', mode: 0o600 });
      mediaRecord = { absolute_path: resolve(path), sha256: hash };
    }
    records.push(publicMessage(message, mediaRecord));
  }
  const sourceCounts = {
    messages: normalized.messages.length,
    media: normalized.messages.filter((m) => m.media).length,
  };
  const selected = selectedCounts(records);
  const now = new Date().toISOString();
  const manifest = {
    schema_version: CASE_SCHEMA_VERSION,
    case_id: normalized.case_id,
    account_profile_id: normalized.account_profile_id,
    chat_id: normalized.chat_id,
    chat_name: normalized.chat_name,
    title: normalized.title,
    timezone: normalized.timezone,
    date,
    source_counts: sourceCounts,
    selected_counts: selected,
    processed_counts: { messages: 0, media: 0 },
    failures: [],
    status: 'processing',
    bundle_path: resolve(bundlePath),
    created_at: now,
    updated_at: now,
    retention: 'manual',
  };
  writeFileSync(join(bundlePath, 'messages.jsonl'), `${records.map(JSON.stringify).join('\n')}\n`);
  writeFileSync(join(bundlePath, 'transcript.md'), renderTranscript(manifest, records));
  writeJsonAtomic(manifestPath, manifest);
  if (options.defer) {
    setImmediate(() => {
      processBundle(instance, bundlePath, options.fetchImpl).catch((error) => {
        const failed = readJson(manifestPath, manifest);
        failed.status = 'partial';
        failed.failures = [{
          code: 'bundle_processing_failed',
          message: String(error.message || error),
          retryable: true,
        }];
        failed.updated_at = new Date().toISOString();
        writeJsonAtomic(manifestPath, failed);
      });
    });
    return manifest;
  }
  return processBundle(instance, bundlePath, options.fetchImpl);
}

export function readCase(instance, bundleName) {
  safeId(bundleName, 'bundle');
  const path = join(resolveCasesRoot(instance), bundleName, 'manifest.json');
  if (!existsSync(path)) return null;
  return readJson(path);
}

export async function retryCase(instance, bundleName, options = {}) {
  safeId(bundleName, 'bundle');
  const bundlePath = join(resolveCasesRoot(instance), bundleName);
  if (!existsSync(join(bundlePath, 'manifest.json'))) return null;
  return processBundle(instance, bundlePath, options.fetchImpl);
}
