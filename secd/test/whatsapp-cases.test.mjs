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
