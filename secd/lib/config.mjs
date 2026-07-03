// secd configuration: resolve the instance path, port and auth token.
//
// The instance path is resolved via SECRETARY_INSTANCE (engine convention) —
// never from __dirname. The daemon refuses to start without it.

import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/** Resolve the Secretary instance directory (where the private data lives). */
export function resolveInstance() {
  const inst =
    process.env.SECRETARY_INSTANCE ||
    process.env.SECRETARY_DATA ||
    '';
  if (!inst) {
    throw new Error(
      'SECRETARY_INSTANCE is not set. Point it at your Secretary instance ' +
        'directory, e.g. export SECRETARY_INSTANCE=~/.secretary',
    );
  }
  const abs = resolve(inst.replace(/^~(?=$|\/)/, process.env.HOME || ''));
  if (!existsSync(abs)) {
    throw new Error(`SECRETARY_INSTANCE points at a missing path: ${abs}`);
  }
  return abs;
}

export const PORT = Number(process.env.SECD_PORT || 8910);
export const HOST = '127.0.0.1'; // loopback only — never expose to the network.
export const VERSION = '0.1.0';

/**
 * Load (or create on first run) the local auth token. Stored under the
 * instance at `.secd/token` (gitignored). The same token must be pasted into
 * the Axon extension options.
 */
export function loadOrCreateToken(instance) {
  const dir = join(instance, '.secd');
  const file = join(dir, 'token');
  if (existsSync(file)) {
    const t = readFileSync(file, 'utf8').trim();
    if (t) return t;
  }
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const token = randomBytes(24).toString('hex');
  writeFileSync(file, token + '\n', { mode: 0o600 });
  return token;
}
