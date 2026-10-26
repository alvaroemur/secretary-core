// Offline tests for the /capture write-path against synthetic, throwaway
// instances. Needs no real instance, so CI runs it: node test/capture.mjs

import assert from 'node:assert';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { appendAccion, appendChatCapture } from '../lib/capture.mjs';
import { configScalar } from '../lib/config.mjs';

let pass = 0;
const t = (name, fn) => {
  const instance = mkdtempSync(join(tmpdir(), 'secd-capture-'));
  try {
    fn(instance);
    pass++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    console.error(`  ✗ ${name}\n    ${e.message}`);
    process.exitCode = 1;
  } finally {
    rmSync(instance, { recursive: true, force: true });
  }
};

const memory = (inst) => join(inst, 'extractors', 'whatsapp', 'memory');
const summaries = (inst) => join(inst, 'extractors', 'whatsapp', 'summaries');
const messages = [
  { type: 'message-in', senderName: 'Contacto Prueba', content: 'hola', timestamp: 1767225600000 },
  { type: 'message-out', content: 'hola, ¿qué tal?', timestamp: 1767225660000 },
];
const withOwner = (inst, name) =>
  writeFileSync(join(inst, '.secretary.yml'), `timezone: UTC\nidentity:\n  name: "${name}"  # display name\n  handle: x\npaths:\n  name: nope\n`);

t('first capture on an empty instance creates memory/ and summaries/', (inst) => {
  const out = appendChatCapture(inst, { chatId: 'c1', alias: 'Contacto Prueba', messages });
  assert.ok(out, 'expected a written capture');
  const chats = readFileSync(join(memory(inst), 'chats.md'), 'utf8');
  assert.match(chats, /resumen_path: extractors\/whatsapp\/summaries\//);
  assert.equal(readdirSync(summaries(inst)).length, 1);
});

t('first accion on an empty instance creates memory/', (inst) => {
  const out = appendAccion(inst, { accion: 'enviar propuesta' });
  assert.match(out.id, /^acc-\d{8}-001$/);
  assert.match(readFileSync(join(memory(inst), 'acciones.md'), 'utf8'), /accion: enviar propuesta/);
});

t('accion ids increment within the same day', (inst) => {
  appendAccion(inst, { accion: 'uno' });
  assert.match(appendAccion(inst, { accion: 'dos' }).id, /-002$/);
});

t('owner name comes from identity.name in .secretary.yml', (inst) => {
  withOwner(inst, 'Persona Sintética');
  const out = appendChatCapture(inst, { chatId: 'c1', alias: 'Contacto Prueba', messages });
  const summary = readFileSync(join(inst, out.summaryFile), 'utf8');
  assert.match(summary, /\*\*Persona Sintética\*\*/);
  appendAccion(inst, { accion: 'x' });
  assert.match(readFileSync(join(memory(inst), 'acciones.md'), 'utf8'), /responsable: Persona Sintética/);
});

t('owner name falls back to a neutral label without config', (inst) => {
  appendAccion(inst, { accion: 'x' });
  assert.match(readFileSync(join(memory(inst), 'acciones.md'), 'utf8'), /responsable: yo/);
});

t('configScalar reads nested keys and ignores same-named keys elsewhere', (inst) => {
  withOwner(inst, 'Persona Sintética');
  assert.equal(configScalar(inst, 'identity.name'), 'Persona Sintética');
  assert.equal(configScalar(inst, 'timezone'), 'UTC');
  assert.equal(configScalar(inst, 'identity.email', 'none'), 'none');
  assert.equal(configScalar(inst, 'paths.estilo_voz', 'none'), 'none');
});

t('failed chats.md append leaves no orphan summary', (inst) => {
  if (process.getuid && process.getuid() === 0) return; // root ignores permissions
  mkdirSync(memory(inst), { recursive: true });
  chmodSync(memory(inst), 0o500);
  try {
    assert.throws(() => appendChatCapture(inst, { chatId: 'c1', alias: 'Contacto Prueba', messages }));
  } finally {
    chmodSync(memory(inst), 0o700);
  }
  assert.ok(!existsSync(join(memory(inst), 'chats.md')));
  assert.equal(readdirSync(summaries(inst)).length, 0);
});

console.log(`\n${pass} capture checks passed`);
