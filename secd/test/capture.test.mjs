// Offline tests for the extractor memory writes (capture.mjs) against
// synthetic, throwaway instances. Needs no real instance, so CI runs it.

import assert from 'node:assert/strict';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { appendAccion, appendChatCapture } from '../lib/capture.mjs';
import { configScalar } from '../lib/config.mjs';

function withInstance(fn) {
  const instance = mkdtempSync(join(tmpdir(), 'secd-capture-'));
  try {
    return fn(instance);
  } finally {
    rmSync(instance, { recursive: true, force: true });
  }
}

const memory = (inst) => join(inst, 'extractors', 'whatsapp', 'memory');
const summaries = (inst) => join(inst, 'extractors', 'whatsapp', 'summaries');
const capture = {
  chatId: 'c1',
  alias: 'Contacto Prueba',
  periodo: '2026-01-01 a 2026-01-01',
  mensajes: 2,
  caso: 'extractors/whatsapp/inbox/cases/2026-01-01-contacto-prueba-case-1',
  transcript: '# Contacto Prueba\n\n## Contacto Prueba — 2026-01-01 00:00:00\n\nhola\n',
};
const withOwner = (inst, name) =>
  writeFileSync(join(inst, '.secretary.yml'), `timezone: UTC\nidentity:\n  name: "${name}"  # display name\n  handle: x\npaths:\n  name: nope\n`);

test('first capture on an empty instance creates memory/ and summaries/', () => withInstance((inst) => {
  const out = appendChatCapture(inst, capture);
  assert.ok(out, 'expected a written capture');
  const chats = readFileSync(join(memory(inst), 'chats.md'), 'utf8');
  assert.match(chats, /resumen_path: extractors\/whatsapp\/summaries\//);
  assert.match(chats, /mensajes_procesados: 2/);
  assert.match(chats, /pendiente_wiki: true/);
  const summary = readFileSync(join(inst, out.summaryFile), 'utf8');
  assert.match(summary, /caso: "extractors\/whatsapp\/inbox\/cases\//);
  assert.ok(summary.endsWith(capture.transcript));
}));

test('a capture with no selected messages writes nothing', () => withInstance((inst) => {
  assert.equal(appendChatCapture(inst, { ...capture, mensajes: 0 }), null);
  assert.ok(!existsSync(memory(inst)));
}));

test('a known summaryFile is rewritten in place without a second chats.md entry', () => withInstance((inst) => {
  const first = appendChatCapture(inst, capture);
  const again = appendChatCapture(inst, { ...capture, transcript: 'actualizado\n', summaryFile: first.summaryFile });
  assert.equal(again.summaryFile, first.summaryFile);
  assert.equal(readdirSync(summaries(inst)).length, 1);
  assert.match(readFileSync(join(inst, first.summaryFile), 'utf8'), /actualizado/);
  const chats = readFileSync(join(memory(inst), 'chats.md'), 'utf8');
  assert.equal(chats.match(/^## /gm).length, 1);
}));

test('first accion on an empty instance creates memory/', () => withInstance((inst) => {
  const out = appendAccion(inst, { accion: 'enviar propuesta' });
  assert.match(out.id, /^acc-\d{8}-001$/);
  assert.match(readFileSync(join(memory(inst), 'acciones.md'), 'utf8'), /accion: enviar propuesta/);
}));

test('accion ids increment within the same day', () => withInstance((inst) => {
  appendAccion(inst, { accion: 'uno' });
  assert.match(appendAccion(inst, { accion: 'dos' }).id, /-002$/);
}));

test('accion responsable defaults to identity.name in .secretary.yml', () => withInstance((inst) => {
  withOwner(inst, 'Persona Sintética');
  appendAccion(inst, { accion: 'x' });
  assert.match(readFileSync(join(memory(inst), 'acciones.md'), 'utf8'), /responsable: Persona Sintética/);
}));

test('owner name falls back to a neutral label without config', () => withInstance((inst) => {
  appendAccion(inst, { accion: 'x' });
  assert.match(readFileSync(join(memory(inst), 'acciones.md'), 'utf8'), /responsable: yo/);
}));

test('configScalar reads nested keys and ignores same-named keys elsewhere', () => withInstance((inst) => {
  withOwner(inst, 'Persona Sintética');
  assert.equal(configScalar(inst, 'identity.name'), 'Persona Sintética');
  assert.equal(configScalar(inst, 'timezone'), 'UTC');
  assert.equal(configScalar(inst, 'identity.email', 'none'), 'none');
  assert.equal(configScalar(inst, 'paths.estilo_voz', 'none'), 'none');
}));

test('failed chats.md append leaves no orphan summary', (t) => withInstance((inst) => {
  if (process.getuid && process.getuid() === 0) return t.skip('root ignores permissions');
  mkdirSync(memory(inst), { recursive: true });
  chmodSync(memory(inst), 0o500);
  try {
    assert.throws(() => appendChatCapture(inst, capture));
  } finally {
    chmodSync(memory(inst), 0o700);
  }
  assert.ok(!existsSync(join(memory(inst), 'chats.md')));
  assert.equal(readdirSync(summaries(inst)).length, 0);
}));
