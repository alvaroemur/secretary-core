// Module contract admin — spec 015 phase 3.
// Delegates to `secretary modules … --format json` (Python engine).

import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

function secretaryJson(instance, args) {
  const out = execFileSync('secretary', args, {
    encoding: 'utf8',
    env: { ...process.env, SECRETARY_INSTANCE: instance },
  });
  return JSON.parse(out);
}

export function listModules(instance) {
  return { modules: secretaryJson(instance, ['modules', 'list', '--format', 'json']) };
}

export function moduleHealth(instance, moduleId) {
  return secretaryJson(instance, ['modules', 'health', '--module', moduleId, '--format', 'json']);
}

export function getModuleContract(instance, moduleId) {
  return {
    module: moduleId,
    contract: secretaryJson(instance, ['modules', 'contract', 'get', moduleId, '--format', 'json']),
  };
}

/** Shallow-merge patch into contract.yaml via secretary contract put. */
export function putModuleContract(instance, moduleId, patch) {
  const dir = join(instance, '.secd');
  mkdirSync(dir, { recursive: true });
  const tmp = join(dir, `contract-patch-${moduleId}.json`);
  writeFileSync(tmp, JSON.stringify(patch), 'utf8');
  const raw = execFileSync(
    'secretary',
    ['modules', 'contract', 'put', moduleId, '--file', tmp],
    { encoding: 'utf8', env: { ...process.env, SECRETARY_INSTANCE: instance } },
  );
  return JSON.parse(raw);
}
