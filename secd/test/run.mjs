// Offline unit-ish tests for secd's read side. No server, no network: exercises
// the resolver, context card and objectives directly against the instance set
// in SECRETARY_INSTANCE. Run: SECRETARY_INSTANCE=~/.secretary node test/run.mjs

import assert from 'node:assert';
import { resolveInstance } from '../lib/config.mjs';
import { buildIndex, resolveEntity, norm } from '../lib/resolver.mjs';
import { buildContextCard } from '../lib/context.mjs';
import { queryObjectives } from '../lib/objectives.mjs';

let pass = 0;
const t = (name, fn) => {
  try {
    fn();
    pass++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    console.error(`  ✗ ${name}\n    ${e.message}`);
    process.exitCode = 1;
  }
};

const instance = resolveInstance();
console.log(`instance: ${instance}\n`);

t('norm strips accents and emoji', () => {
  assert.equal(norm('Álvaro Mür 🍃'), 'alvaro mur');
});

t('index loads entities', () => {
  const idx = buildIndex(instance);
  assert.ok(idx.entities.length > 10, `only ${idx.entities.length} entities`);
});

t('resolves a known person by name', () => {
  const r = resolveEntity(instance, { name: 'Roger Hidalgo' });
  assert.equal(r.status, 'matched');
  assert.ok(r.entity.slug.startsWith('personas/'));
});

t('unknown contact returns unknown', () => {
  const r = resolveEntity(instance, { name: 'Zxqw Nonexistent Person 9931' });
  assert.equal(r.status, 'unknown');
});

t('context card for known entity has summary + objectives', () => {
  const card = buildContextCard(instance, { name: 'Roger Hidalgo' });
  assert.equal(card.resolution, 'matched');
  assert.ok(card.styleRules.length > 0, 'style rules missing');
  // obj-20260610-004 (suggested) is tied to roger-hidalgo
  assert.ok(
    card.objectives.suggested.length + card.objectives.active.length >= 1,
    'expected at least one objective for Roger',
  );
});

t('objectives query by entity works', () => {
  const objs = queryObjectives(instance, { entity: 'organizaciones/changelab' });
  assert.ok(objs.some((o) => o.id === 'obj-20260610-003'), 'changelab objective missing');
});

t('unknown contact card flags pendiente_wiki', () => {
  const card = buildContextCard(instance, { name: 'Zxqw Nonexistent 9931' });
  assert.equal(card.pendiente_wiki, true);
});

console.log(`\n${pass} checks passed`);
