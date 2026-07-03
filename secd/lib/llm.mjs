// Minimal provider-agnostic LLM client for the relay. Zero dependencies (global
// fetch). Reads credentials from, in order:
//   1. <instance>/.secd/llm.json  → { provider, apiKey, model }
//   2. env OPENAI_API_KEY (provider 'openai') or ANTHROPIC_API_KEY ('anthropic')
//
// Returns { configured: boolean, provider, model } from describe(), and a parsed
// JSON object from chatJSON(). If nothing is configured, callers fall back to the
// deterministic stub.

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const DEFAULTS = {
  openai: { model: 'gpt-4o-mini', url: 'https://api.openai.com/v1/chat/completions' },
  anthropic: { model: 'claude-haiku-4-5-20251001', url: 'https://api.anthropic.com/v1/messages' },
};

export function loadLlmConfig(instance) {
  const file = join(instance, '.secd', 'llm.json');
  if (existsSync(file)) {
    try {
      const j = JSON.parse(readFileSync(file, 'utf8'));
      if (j.apiKey) {
        const provider = j.provider || 'openai';
        return { provider, apiKey: j.apiKey, model: j.model || DEFAULTS[provider].model };
      }
    } catch {
      /* fall through to env */
    }
  }
  if (process.env.OPENAI_API_KEY)
    return { provider: 'openai', apiKey: process.env.OPENAI_API_KEY, model: process.env.SECD_LLM_MODEL || DEFAULTS.openai.model };
  if (process.env.ANTHROPIC_API_KEY)
    return { provider: 'anthropic', apiKey: process.env.ANTHROPIC_API_KEY, model: process.env.SECD_LLM_MODEL || DEFAULTS.anthropic.model };
  return null;
}

export function describe(instance) {
  const cfg = loadLlmConfig(instance);
  return cfg ? { configured: true, provider: cfg.provider, model: cfg.model } : { configured: false };
}

/**
 * Run a chat completion that must return a JSON object. Throws on transport or
 * parse failure (caller decides whether to fall back).
 * @returns {Promise<object>}
 */
export async function chatJSON(instance, { system, user, temperature = 0.4, maxTokens = 900 }) {
  const cfg = loadLlmConfig(instance);
  if (!cfg) throw new Error('no LLM configured');

  if (cfg.provider === 'anthropic') {
    const res = await fetch(DEFAULTS.anthropic.url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': cfg.apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: cfg.model,
        max_tokens: maxTokens,
        temperature,
        system: system + '\n\nReturn ONLY a valid JSON object, no prose, no code fences.',
        messages: [{ role: 'user', content: user }],
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || `anthropic HTTP ${res.status}`);
    const text = (data.content || []).map((c) => c.text || '').join('');
    return parseJsonLoose(text);
  }

  // default: openai
  const res = await fetch(DEFAULTS.openai.url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${cfg.apiKey}` },
    body: JSON.stringify({
      model: cfg.model,
      temperature,
      max_tokens: maxTokens,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error?.message || `openai HTTP ${res.status}`);
  return parseJsonLoose(data.choices?.[0]?.message?.content || '');
}

function parseJsonLoose(text) {
  if (!text) throw new Error('empty LLM response');
  try {
    return JSON.parse(text);
  } catch {
    const m = text.match(/\{[\s\S]*\}/);
    if (m) return JSON.parse(m[0]);
    throw new Error('LLM response was not JSON');
  }
}
