import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import {
  createCase,
  estimateCase,
  readCase,
  resolveCasesRoot,
  retryCase,
  validateCasePayload,
} from '../lib/whatsapp-cases.mjs';

function fixture(overrides = {}) {
  const content = Buffer.from('synthetic media');
  return {
    case_id: 'case-001',
    account_profile_id: 'profile-a',
    chat_id: 'group-opaque',
    chat_name: 'Project group',
    title: '2026-09-12 Project group',
    timezone: 'Etc/UTC',
    messages: [
      {
        message_id: 'msg-002',
        source_order: 1,
        timestamp_iso: '2026-09-12T15:02:00.000Z',
        timestamp_epoch: 1789225320,
        sender_name: 'Member B',
        direction: 'in',
        kind: 'text',
        text: 'Second',
        selected: false,
      },
      {
        message_id: 'msg-001',
        source_order: 0,
        timestamp_iso: '2026-09-12T15:01:00.000Z',
        timestamp_epoch: 1789225260,
        sender_name: 'Member A',
        direction: 'in',
        kind: 'image',
        caption: 'Diagram',
        selected: true,
        media: {
          media_id: 'media-001',
          mime_type: 'image/png',
          size_bytes: content.length,
          filename: 'diagram.png',
          content_base64: content.toString('base64'),
          selected: true,
        },
      },
    ],
    ...overrides,
  };
}

function instance() {
  const root = mkdtempSync(join(tmpdir(), 'secd-cases-'));
  writeFileSync(
    join(root, '.secretary.yml'),
    [
      'timezone: Etc/UTC',
      'paths:',
      '  inbox: unrelated-root-inbox',
      '  whatsapp:',
      '    inbox: legacy/whatsapp-inbox',
      '  extractors:',
      '    mail:',
      '      inbox: unrelated-mail-inbox',
      '    whatsapp:',
      '      inbox: runtime/whatsapp-inbox',
      '',
    ].join('\n'),
  );
  mkdirSync(join(root, '.secd'));
  writeFileSync(join(root, '.secd', 'llm.json'), JSON.stringify({
    provider: 'openai',
    apiKey: 'test-key',
    model: 'test-model',
  }));
  return root;
}

function imageFetch() {
  return Promise.resolve({
    ok: true,
    json: async () => ({
      choices: [{ message: { content: JSON.stringify({
        description: 'A synthetic diagram.',
        ocr: 'TEST',
        caption_relation: 'The caption identifies the diagram.',
      }) } }],
    }),
  });
}

test('resolves configured inbox and cases directory', () => {
  const root = instance();
  try {
    assert.equal(resolveCasesRoot(root), join(root, 'runtime/whatsapp-inbox/cases'));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('falls back to the canonical instance timezone', () => {
  const root = instance();
  try {
    const payload = fixture();
    delete payload.timezone;
    assert.equal(validateCasePayload(payload, root).timezone, 'Etc/UTC');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('sorts, deduplicates, and preserves group senders', () => {
  const normalized = validateCasePayload(fixture());
  assert.deepEqual(normalized.messages.map((m) => m.message_id), ['msg-001', 'msg-002']);
  assert.equal(normalized.messages[0].sender_name, 'Member A');
  assert.throws(
    () => validateCasePayload(fixture({ messages: [fixture().messages[0], fixture().messages[0]] })),
    /duplicate/,
  );
});

test('uses source_order before lexical IDs for equal timestamps', () => {
  const timestamp = '2026-09-12T15:01:00.000Z';
  const epoch = Date.parse(timestamp) / 1000;
  const normalized = validateCasePayload(fixture({
    messages: [
      {
        message_id: 'z-last-lexically',
        source_order: 0,
        timestamp_iso: timestamp,
        timestamp_epoch: epoch,
        sender_name: 'Member A',
        direction: 'in',
        kind: 'text',
        text: 'First in conversation',
        selected: true,
      },
      {
        message_id: 'a-first-lexically',
        source_order: 1,
        timestamp_iso: timestamp,
        timestamp_epoch: epoch,
        sender_name: 'Member B',
        direction: 'in',
        kind: 'text',
        text: 'Second in conversation',
        selected: true,
      },
    ],
  }));
  assert.deepEqual(
    normalized.messages.map((message) => message.message_id),
    ['z-last-lexically', 'a-first-lexically'],
  );
});

test('rejects traversal in opaque identifiers', () => {
  assert.throws(() => validateCasePayload(fixture({ case_id: '../outside' })), /invalid|unsafe/);
  assert.throws(() => validateCasePayload(fixture({ account_profile_id: '..' })), /unsafe/);
});

test('rejects duplicated source_order', () => {
  const duplicate = fixture();
  duplicate.messages[1].source_order = duplicate.messages[0].source_order;
  assert.throws(() => validateCasePayload(duplicate), /source_order/);
});

test('rejects unresolved media decisions', () => {
  const unresolved = fixture();
  unresolved.messages[1].media.selected = null;
  assert.throws(() => validateCasePayload(unresolved), /unresolved/);
});

test('reports missing pricing instead of inventing cost', () => {
  const root = instance();
  try {
    const estimate = estimateCase(fixture(), root);
    assert.equal(estimate.messages, 1);
    assert.equal(estimate.media, 1);
    assert.equal(estimate.estimated_cost_usd, null);
    assert.deepEqual(estimate.missing_rates, ['image_per_item_usd']);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('writes originals, ordered JSONL, manifest, and transcript', async () => {
  const root = instance();
  try {
    const manifest = await createCase(root, fixture(), { fetchImpl: imageFetch });
    assert.equal(manifest.status, 'ready');
    assert.deepEqual(manifest.source_counts, { messages: 2, media: 1 });
    assert.deepEqual(manifest.selected_counts, { messages: 1, media: 1 });
    assert.deepEqual(manifest.processed_counts, { messages: 1, media: 1 });
    const transcript = readFileSync(join(manifest.bundle_path, 'transcript.md'), 'utf8');
    assert.match(transcript, /Member A — 2026-09-12 15:01:00 GMT\+00:00 \[Etc\/UTC\]/);
    assert.match(transcript, /Factual description/);
    assert.doesNotMatch(transcript, /Second/);
    const records = readFileSync(join(manifest.bundle_path, 'messages.jsonl'), 'utf8')
      .trim().split('\n').map(JSON.parse);
    assert.equal(records.length, 1);
    assert.equal(records[0].message_id, 'msg-001');
    assert.ok(records[0].media.absolute_path.startsWith(manifest.bundle_path));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('uses the case timezone for the bundle date near UTC midnight', async () => {
  const root = instance();
  const timestamp = '2026-09-13T03:30:00.000Z';
  try {
    const manifest = await createCase(root, fixture({
      case_id: 'case-midnight',
      timezone: 'America/Lima',
      messages: [{
        message_id: 'msg-midnight',
        source_order: 0,
        timestamp_iso: timestamp,
        timestamp_epoch: Date.parse(timestamp) / 1000,
        timestamp_local: '2026-09-12 22:30:00 GMT-5',
        sender_name: 'Member A',
        direction: 'in',
        kind: 'text',
        text: 'Near midnight',
        selected: true,
      }],
    }));
    assert.equal(manifest.date, '2026-09-12');
    assert.equal(manifest.timezone, 'America/Lima');
    assert.match(manifest.bundle_path.split('/').at(-1), /^2026-09-12-/);
    const transcript = readFileSync(join(manifest.bundle_path, 'transcript.md'), 'utf8');
    assert.match(transcript, /2026-09-12 22:30:00 GMT-05:00 \[America\/Lima\]/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('can return processing state before deferred work finishes', async () => {
  const root = instance();
  try {
    const processing = await createCase(root, fixture(), { fetchImpl: imageFetch, defer: true });
    assert.equal(processing.status, 'processing');
    await new Promise((resolve) => setImmediate(resolve));
    const bundleName = processing.bundle_path.split('/').at(-1);
    assert.equal(readCase(root, bundleName).status, 'ready');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('marks partial failures and retries idempotently', async () => {
  const root = instance();
  try {
    const failFetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
    const partial = await createCase(root, fixture(), { fetchImpl: failFetch });
    assert.equal(partial.status, 'partial');
    assert.equal(partial.failures.length, 1);
    const bundleName = partial.bundle_path.split('/').at(-1);
    const ready = await retryCase(root, bundleName, { fetchImpl: imageFetch });
    assert.equal(ready.status, 'ready');
    assert.equal(ready.failures.length, 0);
    assert.equal(readCase(root, bundleName).status, 'ready');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('serializes deferred processing and a concurrent retry on the same bundle', async () => {
  const root = instance();
  try {
    let calls = 0;
    let inFlight = 0;
    let maxInFlight = 0;
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    let firstCall;
    const started = new Promise((resolve) => { firstCall = resolve; });
    const gatedFetch = async (...args) => {
      calls += 1;
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      firstCall();
      await gate;
      inFlight -= 1;
      return imageFetch(...args);
    };
    const processing = await createCase(root, fixture(), { fetchImpl: gatedFetch, defer: true });
    const bundleName = processing.bundle_path.split('/').at(-1);
    await started;
    const retry = retryCase(root, bundleName, { fetchImpl: gatedFetch });
    const recreate = createCase(root, fixture(), { fetchImpl: gatedFetch });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(calls, 1);
    release();
    const [retried, recreated] = await Promise.all([retry, recreate]);
    assert.equal(calls, 1);
    assert.equal(maxInFlight, 1);
    assert.equal(retried.status, 'ready');
    assert.equal(recreated.status, 'ready');
    const stored = readCase(root, bundleName);
    assert.equal(stored.status, 'ready');
    assert.equal(stored.processed_counts.media, 1);
    const lines = readFileSync(join(processing.bundle_path, 'messages.jsonl'), 'utf8').trim().split('\n');
    assert.equal(lines.length, 1);
    assert.equal(JSON.parse(lines[0]).media.processing.description, 'A synthetic diagram.');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('a processed case feeds the extractor memory with owner name from config', async () => {
  const root = instance();
  try {
    writeFileSync(join(root, '.secretary.yml'), `${readFileSync(join(root, '.secretary.yml'), 'utf8')}identity:\n  name: Persona Sintética\n`);
    const out = {
      message_id: 'msg-003',
      source_order: 2,
      timestamp_iso: '2026-09-12T15:03:00.000Z',
      timestamp_epoch: 1789225380,
      sender_name: 'You',
      direction: 'out',
      kind: 'text',
      text: 'Respuesta sintética',
      selected: true,
    };
    const manifest = await createCase(root, fixture({
      messages: [...fixture().messages, out],
      accion: { accion: 'Enviar el diagrama revisado', deadline: '2026-09-20' },
    }), { fetchImpl: imageFetch });
    assert.equal(manifest.status, 'ready');
    assert.equal(manifest.is_group, false);
    assert.match(manifest.memory.summary_file, /^extractors\/whatsapp\/summaries\/.+-project-group\.md$/);
    assert.match(manifest.memory.accion_id, /^acc-\d{8}-001$/);

    const memory = join(root, 'extractors', 'whatsapp', 'memory');
    const chats = readFileSync(join(memory, 'chats.md'), 'utf8');
    assert.match(chats, /## \d{4}-\d{2}-\d{2} — Project group/);
    assert.match(chats, /periodo: "2026-09-12 a 2026-09-12"/);
    assert.match(chats, /mensajes_procesados: 2/);
    assert.match(chats, /pendiente_wiki: true/);

    const summary = readFileSync(join(root, manifest.memory.summary_file), 'utf8');
    const transcript = readFileSync(join(manifest.bundle_path, 'transcript.md'), 'utf8');
    assert.ok(summary.endsWith(transcript), 'summary reuses the case transcript');
    assert.match(summary, /caso: "runtime\/whatsapp-inbox\/cases\//);
    assert.match(transcript, /## Persona Sintética — /);
    assert.doesNotMatch(transcript, /## You — /);

    const acciones = readFileSync(join(memory, 'acciones.md'), 'utf8');
    assert.match(acciones, /accion: Enviar el diagrama revisado/);
    assert.match(acciones, /responsable: Persona Sintética/);
    assert.match(acciones, /origen: extractors\/whatsapp\/summaries\//);
    assert.match(acciones, /pendiente_wiki: true/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('a retried case updates its summary without duplicating memory entries', async () => {
  const root = instance();
  try {
    const failFetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
    const partial = await createCase(root, fixture({
      // WhatsApp group JID, built at runtime so the leak guard's email regex skips it
      chat_id: ['group-opaque', 'g.us'].join('@'),
      accion: { accion: 'Revisar el diagrama' },
    }), { fetchImpl: failFetch });
    assert.equal(partial.status, 'partial');
    assert.equal(partial.is_group, true);
    const summaryPath = join(root, partial.memory.summary_file);
    assert.match(readFileSync(summaryPath, 'utf8'), /Processing error/);

    const bundleName = partial.bundle_path.split('/').at(-1);
    const ready = await retryCase(root, bundleName, { fetchImpl: imageFetch });
    assert.equal(ready.status, 'ready');
    assert.equal(ready.memory.summary_file, partial.memory.summary_file);
    assert.equal(ready.memory.accion_id, partial.memory.accion_id);
    assert.match(readFileSync(summaryPath, 'utf8'), /A synthetic diagram/);

    const memory = join(root, 'extractors', 'whatsapp', 'memory');
    assert.equal(readFileSync(join(memory, 'chats.md'), 'utf8').match(/^## /gm).length, 1);
    assert.match(readFileSync(join(memory, 'chats.md'), 'utf8'), /categoria: proyecto/);
    assert.equal(readFileSync(join(memory, 'acciones.md'), 'utf8').match(/^## acc-/gm).length, 1);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('rejects a malformed accion', () => {
  assert.throws(() => validateCasePayload(fixture({ accion: { deadline: 'mañana' } })), /accion\.accion is required/);
  assert.throws(() => validateCasePayload(fixture({ accion: 'texto' })), /accion is invalid/);
  assert.throws(() => validateCasePayload(fixture({ is_group: 'sí' })), /is_group is invalid/);
});
