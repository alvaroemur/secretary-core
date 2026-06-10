// Relay — DETERMINISTIC STUB (Feature 007, P2 scaffold).
//
// The real relay will run an LLM (Claude) over the conversation + context card
// to (a) detect intention, (b) suggest objectives, (c) derive tasks, and
// (d) draft copy-paste replies in Álvaro's voice. This stub keeps the SAME
// shape so the Axon side and the daemon contract can be built and wired now;
// swapping in the model later does not change the interface.
//
// It does NOT call any model and does NOT invent content beyond simple,
// transparent heuristics — every field is marked `stub: true`.

/**
 * @param {object} input
 * @param {object} input.contextCard   — output of buildContextCard()
 * @param {{role:'in'|'out', text:string}[]} input.messages — recent messages
 * @returns {object} relay suggestion envelope (stub)
 */
export function runRelay({ contextCard, messages = [] }) {
  const last = [...messages].reverse().find((m) => m.role === 'in');
  const lastInbound = last ? last.text : '';

  // Transparent heuristic intention detection (placeholder for the LLM).
  const intention = detectIntentionHeuristic(lastInbound);

  const activeObjectives = contextCard?.objectives?.active || [];
  const suggestedObjectives = contextCard?.objectives?.suggested || [];

  return {
    stub: true,
    note: 'Deterministic stub — no LLM. Replace with Claude-backed relay (RFC 007 P2).',
    intention,
    objectives: {
      // objectives already known for this entity, surfaced for the user to act on
      active: activeObjectives.map((o) => ({ id: o.id, titulo: o.titulo, nivel: o.nivel })),
      suggested: suggestedObjectives.map((o) => ({ id: o.id, titulo: o.titulo, nivel: o.nivel })),
      // a stubbed proposal the real relay would generate from the conversation
      proposed:
        activeObjectives.length === 0
          ? [{ titulo: '(stub) definir objetivo para esta conversación', nivel: 'L1', origen: 'relay' }]
          : [],
    },
    suggestedReplies: [
      {
        text: '(stub) respuesta sugerida — el relay real la redactará en tu voz, alineada al objetivo activo.',
        advances: activeObjectives[0]?.id || null,
        stub: true,
      },
    ],
    styleApplied: Boolean(contextCard?.styleRules),
  };
}

function detectIntentionHeuristic(text) {
  const t = (text || '').toLowerCase();
  if (!t) return { label: 'unknown', confidence: 0 };
  if (/[?¿]/.test(t)) return { label: 'pregunta', confidence: 0.4 };
  if (/(gracias|listo|ok|dale|perfecto)/.test(t)) return { label: 'acuse', confidence: 0.4 };
  if (/(precio|costo|propuesta|cotiza|presupuesto)/.test(t))
    return { label: 'negociación', confidence: 0.5 };
  if (/(reun|agenda|llamada|meet|cita)/.test(t)) return { label: 'coordinación', confidence: 0.5 };
  return { label: 'conversación', confidence: 0.2 };
}
