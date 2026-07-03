// Relay — Feature 007.
//
// Given the context card + recent messages, the relay (a) detects intention,
// (b) surfaces/affirms objectives, and (c) drafts copy-paste replies in Álvaro's
// voice, each annotated with the objective it advances.
//
// If an LLM is configured (see lib/llm.mjs) it runs the real reasoning; otherwise
// it falls back to a DETERMINISTIC STUB with the same output shape, so the rest
// of the system works either way. Nothing is ever sent — replies are drafts.

import { chatJSON, describe } from './llm.mjs';

/**
 * @param {string} instance
 * @param {object} input
 * @param {object} input.contextCard  — buildContextCard() output
 * @param {{role:'in'|'out', text:string}[]} input.messages
 */
export async function runRelay(instance, { contextCard, messages = [] }) {
  const llm = describe(instance);
  if (llm.configured) {
    try {
      return await runRelayLLM(instance, llm, { contextCard, messages });
    } catch (e) {
      return { ...runRelayStub({ contextCard, messages }), llmError: e.message };
    }
  }
  return runRelayStub({ contextCard, messages });
}

async function runRelayLLM(instance, llm, { contextCard, messages }) {
  const active = contextCard?.objectives?.active || [];
  const suggested = contextCard?.objectives?.suggested || [];
  const transcript = messages
    .map((m) => `${m.role === 'out' ? 'Álvaro' : (contextCard?.entity?.title || 'Contacto')}: ${m.text}`)
    .join('\n');

  const system = [
    'Eres el relay de Secretary, el copiloto de WhatsApp de Álvaro.',
    'Tu trabajo: a partir de la conversación y el contexto de Secretary, (1) detectar la intención',
    'del último mensaje del contacto, (2) proponer o reafirmar un objetivo para la conversación,',
    '(3) redactar 1-2 respuestas para que Álvaro copie y pegue, alineadas al objetivo activo.',
    'Las respuestas las envía Álvaro a mano: nunca las mandes tú, nunca lo digas en primera persona del sistema.',
    'OBEDECE estas reglas de voz al pie de la letra en cualquier borrador:',
    contextCard?.styleRules || '(sin reglas de voz)',
    'Devuelve SOLO un objeto JSON con esta forma exacta:',
    '{"intention":{"label":string,"confidence":number},',
    ' "objectiveSuggestion":{"titulo":string,"nivel":"L1"|"L2","rationale":string}|null,',
    ' "suggestedReplies":[{"text":string,"advances":string|null,"why":string}]}',
  ].join('\n');

  const user = [
    `CONTACTO: ${contextCard?.entity?.title || contextCard?.chat?.name || 'desconocido'}`,
    contextCard?.summary ? `QUIÉN ES: ${contextCard.summary}` : '',
    active.length ? `OBJETIVOS ACTIVOS: ${active.map((o) => `${o.id}:${o.titulo}`).join(' | ')}` : 'OBJETIVOS ACTIVOS: (ninguno)',
    suggested.length ? `OBJETIVOS SUGERIDOS (pendientes de OK): ${suggested.map((o) => o.titulo).join(' | ')}` : '',
    contextCard?.openActions?.length
      ? `ACCIONES ABIERTAS: ${contextCard.openActions.slice(0, 6).map((a) => a.accion).join(' | ')}`
      : '',
    '',
    'CONVERSACIÓN (reciente):',
    transcript || '(sin mensajes)',
    '',
    'Redacta las respuestas en la voz de Álvaro. `advances` = id del objetivo activo que avanza, o null.',
  ]
    .filter(Boolean)
    .join('\n');

  const out = await chatJSON(instance, { system, user });
  return {
    stub: false,
    provider: llm.provider,
    model: llm.model,
    intention: out.intention || { label: 'unknown', confidence: 0 },
    objectives: {
      active: active.map((o) => ({ id: o.id, titulo: o.titulo, nivel: o.nivel })),
      suggested: suggested.map((o) => ({ id: o.id, titulo: o.titulo, nivel: o.nivel })),
      proposed: out.objectiveSuggestion ? [{ ...out.objectiveSuggestion, origen: 'relay' }] : [],
    },
    suggestedReplies: Array.isArray(out.suggestedReplies) ? out.suggestedReplies : [],
    styleApplied: Boolean(contextCard?.styleRules),
  };
}

function runRelayStub({ contextCard, messages = [] }) {
  const last = [...messages].reverse().find((m) => m.role === 'in');
  const active = contextCard?.objectives?.active || [];
  const suggested = contextCard?.objectives?.suggested || [];
  return {
    stub: true,
    note: 'Deterministic stub — no LLM configured. Set <instance>/.secd/llm.json or OPENAI_API_KEY.',
    intention: detectIntentionHeuristic(last ? last.text : ''),
    objectives: {
      active: active.map((o) => ({ id: o.id, titulo: o.titulo, nivel: o.nivel })),
      suggested: suggested.map((o) => ({ id: o.id, titulo: o.titulo, nivel: o.nivel })),
      proposed: active.length === 0 ? [{ titulo: '(stub) definir objetivo para esta conversación', nivel: 'L1', origen: 'relay' }] : [],
    },
    suggestedReplies: [
      { text: '(stub) respuesta sugerida — configura un LLM para que el relay la redacte en tu voz.', advances: active[0]?.id || null, why: 'stub' },
    ],
    styleApplied: Boolean(contextCard?.styleRules),
  };
}

function detectIntentionHeuristic(text) {
  const t = (text || '').toLowerCase();
  if (!t) return { label: 'unknown', confidence: 0 };
  if (/[?¿]/.test(t)) return { label: 'pregunta', confidence: 0.4 };
  if (/(gracias|listo|ok|dale|perfecto)/.test(t)) return { label: 'acuse', confidence: 0.4 };
  if (/(precio|costo|propuesta|cotiza|presupuesto)/.test(t)) return { label: 'negociación', confidence: 0.5 };
  if (/(reun|agenda|llamada|meet|cita)/.test(t)) return { label: 'coordinación', confidence: 0.5 };
  return { label: 'conversación', confidence: 0.2 };
}
