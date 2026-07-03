#!/usr/bin/env node
// secd — Secretary local daemon (Feature 007).
//
// A tiny loopback-only HTTP server that exposes Secretary's context to the Axon
// browser extension while you read a WhatsApp conversation, and accepts signals
// back. Zero external dependencies: Node built-in http only. Run with:
//
//   SECRETARY_INSTANCE=~/.secretary node secd/server.mjs
//
// Security: binds 127.0.0.1 only; every endpoint except /health requires the
// bearer token printed on startup (and stored at <instance>/.secd/token).

import { createServer } from 'node:http';
import { appendFileSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { HOST, PORT, VERSION, loadOrCreateToken, resolveInstance } from './lib/config.mjs';
import { buildIndex, resetIndex } from './lib/resolver.mjs';
import { buildContextCard } from './lib/context.mjs';
import { queryObjectives, upsertObjective } from './lib/objectives.mjs';
import { recall } from './lib/memory.mjs';
import { runRelay } from './lib/relay.mjs';
import { describe as describeLlm } from './lib/llm.mjs';
import { appendAccion, appendChatCapture } from './lib/capture.mjs';

const instance = resolveInstance();
const TOKEN = loadOrCreateToken(instance);

function corsHeaders(origin) {
  // Allow the extension (chrome-extension://…) and localhost tools. Loopback
  // bind already prevents remote pages from reaching us.
  const allow =
    origin && (/^chrome-extension:\/\//.test(origin) || /^https?:\/\/(localhost|127\.0\.0\.1)/.test(origin))
      ? origin
      : '*';
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Secd-Token',
    'Access-Control-Max-Age': '600',
  };
}

function send(res, status, body, origin) {
  const payload = JSON.stringify(body, null, 2);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    ...corsHeaders(origin),
  });
  res.end(payload);
}

function authed(req) {
  const h = req.headers['authorization'] || '';
  const bearer = h.startsWith('Bearer ') ? h.slice(7).trim() : '';
  const alt = (req.headers['x-secd-token'] || '').toString().trim();
  return bearer === TOKEN || alt === TOKEN;
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = '';
    req.on('data', (c) => (data += c));
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        resolve(null);
      }
    });
  });
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
}

const server = createServer(async (req, res) => {
  const origin = req.headers.origin;
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const path = url.pathname;

  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders(origin));
    return res.end();
  }

  // --- open endpoint: health (proves reachability + CORS, no token) ---
  if (path === '/health' && req.method === 'GET') {
    const idx = buildIndex(instance);
    return send(res, 200, {
      ok: true,
      service: 'secd',
      version: VERSION,
      instance,
      entities: idx.entities.length,
      authRequired: true,
      relay: describeLlm(instance),
    }, origin);
  }

  // --- everything below requires the token ---
  if (!authed(req)) {
    return send(res, 401, { error: 'unauthorized', hint: 'send Authorization: Bearer <token>' }, origin);
  }

  try {
    if (path === '/context' && req.method === 'GET') {
      const card = buildContextCard(instance, {
        chatId: url.searchParams.get('chatId') || undefined,
        name: url.searchParams.get('name') || undefined,
      });
      return send(res, 200, card, origin);
    }

    if (path === '/objectives' && req.method === 'GET') {
      const objs = queryObjectives(instance, {
        entity: url.searchParams.get('entity') || undefined,
        estado: url.searchParams.get('estado') || undefined,
        nivel: url.searchParams.get('nivel') || undefined,
      });
      return send(res, 200, { objectives: objs }, origin);
    }

    if (path === '/objectives' && req.method === 'POST') {
      const body = await readBody(req);
      if (!body) return send(res, 400, { error: 'invalid json' }, origin);
      const result = upsertObjective(instance, body, today());
      resetIndex();
      return send(res, 200, { ok: true, ...result }, origin);
    }

    if (path === '/recall' && req.method === 'GET') {
      const hits = recall(instance, url.searchParams.get('q') || '');
      return send(res, 200, { hits }, origin);
    }

    if (path === '/relay' && req.method === 'POST') {
      const body = await readBody(req);
      if (!body) return send(res, 400, { error: 'invalid json' }, origin);
      const card =
        body.contextCard ||
        buildContextCard(instance, { chatId: body.chatId, name: body.name });
      const relayOut = await runRelay(instance, { contextCard: card, messages: body.messages || [] });
      return send(res, 200, relayOut, origin);
    }

    if (path === '/signal' && req.method === 'POST') {
      const body = await readBody(req);
      if (!body || !body.text) return send(res, 400, { error: 'text required' }, origin);
      // Scaffold: append to a pending-signals file. Not yet wired into
      // sec-write's wiki annotation flow — that's relay/P2 territory, not
      // part of the P3 capture write-path. Path fixed to the post-migration
      // instance layout (was whatsapp/memory/, pre spec-012).
      const dir = join(instance, 'extractors', 'whatsapp', 'memory');
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
      const file = join(dir, 'relay-signals.md');
      const entry =
        `\n## ${new Date().toISOString()} — ${body.entity || 'sin-entidad'}\n` +
        `- fuente: axon-relay\n- texto: ${body.text}\n- pendiente_wiki: false\n`;
      appendFileSync(file, entry);
      return send(res, 200, { ok: true, recorded: 'extractors/whatsapp/memory/relay-signals.md' }, origin);
    }

    if (path === '/capture' && req.method === 'POST') {
      const body = await readBody(req);
      if (!body || !body.chatId) return send(res, 400, { error: 'chatId required' }, origin);
      const chat = appendChatCapture(instance, {
        chatId: body.chatId,
        alias: body.alias || body.name,
        jid: body.jid,
        isGroup: !!body.isGroup,
        messages: body.messages || [],
      });
      let accion = null;
      if (body.accion && body.accion.accion) {
        accion = appendAccion(instance, {
          ...body.accion,
          origen: chat ? chat.summaryFile : 'axon',
        });
      }
      if (!chat && !accion) {
        return send(res, 200, { ok: true, skipped: 'no-new-messages' }, origin);
      }
      return send(res, 200, { ok: true, chat, accion }, origin);
    }

    return send(res, 404, { error: 'not found', path }, origin);
  } catch (err) {
    return send(res, 500, { error: 'internal', message: String(err && err.message) }, origin);
  }
});

server.listen(PORT, HOST, () => {
  const idx = buildIndex(instance);
  console.log(`secd ${VERSION} listening on http://${HOST}:${PORT}`);
  console.log(`instance: ${instance}`);
  console.log(`entities indexed: ${idx.entities.length}`);
  console.log(`token: ${TOKEN}`);
  console.log(`(paste this token into Axon → options → Secretary bridge)`);
});
