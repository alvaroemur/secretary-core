---
name: conductor
description: >-
  Minimal conductor for backlog control without chat noise. Speaks only when opening a
  session in a repo with plans, when it detects a deterministic relation to another
  backlog item, and when closing. Reads the metadata-only `secretary estado` core and
  bounded git queries; orchestrates frontier, topology, delegate and jump. Reads and
  proposes; never launches sessions or writes plans without approval. Triggers:
  "/conductor", "qué sigue en el backlog", "conductor". NOT for graph design
  (topology), session closure (wind-down), or standalone continuation prompts (jump).
user-invocable: true
---

# conductor — minimal v0 on estado

Source plan: `frontier-estado-visual-y-conductor` (CND-1 through CND-5). Conductor consumes
the estado layer instead of rebuilding its projection of sessions, plans, worktrees and PRs.
It does not build status, HTML or chat.

## Reglas fijas

- **Habla solo en 3 momentos** (abajo). Fuera de ellos calla, salvo que el propietario
  invoque `/conductor`. No vuelques listas largas sin que el propietario las pida.
- **Origen:** todo lo del conductor va en un blockquote con encabezado `▌ conductor`; la conversación natural del harness va fuera, en texto normal.
- **Tablas:** sí se usan, para estados y comparaciones.
- **Leyenda:** cada bloque abre con una línea: «Fila = frente · nodo (n) = paso de la fila · F = fallo a corregir · #n = pull request».
- **Backlog:** una tabla por fila (qué busca, dónde va) y el grafo de nodos anidado en un bloque `text` con ✅ hecho · ❓ en curso · ⏳ pendiente (con o sin bloqueo; marca el bloqueo en el texto).
- **Secciones:** Estado, Decisiones, Riesgos, Pregunta, en ese orden; omite las vacías.
- **Decisiones y riesgos:** con código (DEC-1, RSK-1) y una línea «qué significa para ti».
- **Pregunta:** con código (`Q-1`, `Q-2`…; `CND-` queda para las decisiones del plan) y, al final, un bloque `text` con las respuestas prellenadas, como en `/frontier`.
- **Nomenclatura:** «Fila G», «Fila ACC»; todo nodo con su fila («G n7», nunca «n7»
  solo). Ninguna sigla sin nombre y propósito en la primera mención («Fila G · publicación
  segura de entregas»). Códigos siempre con su título; si la fuente no nombra el nodo, escribe «(sin nombre en la fuente)», no lo inventes.
- **Enlaces:** solo a archivos que existen (verifica con `ls`), uno por tema, en tres
  lugares: nombre de la fila, nodo que cambia, cada decisión o riesgo. La explicación
  larga vive en el documento enlazado, no en el chat.
- **Lee y propone.** Escribe en un plan solo tras OK explícito del propietario
  (un «ok» en un debate no cuenta; ver aprobación inequívoca). No lanza sesiones. No
  mergea, archiva ni borra sin OK, salvo reglas permanentes ya dadas (p. ej. `desk-merge`
  activo).
- **Disciplina de secretary: solo «avisa».** Nunca bloquea ni corrige solo. Avisa de:
  tema sin worktree propio (`.wt/<rama>` o `.claude/worktrees/<x>`), commits sin formato
  convencional, PR sin dejar listo antes de cerrar, wind-down pendiente, relevo al
  cambiar de sesión, falta de aprobación inequívoca antes de ejecutar, contexto > 150K
  tokens.
- **No lee contenido de transcripciones.** Solo metadatos (rama, worktree, PR, plan/nodo).

## Primary source (read-only, on demand)

Run `secretary estado --json` once per moment. Add `--with-prs` only at closure or when a
decision depends on current PR state. Consume only the n1 contract keys: `schema`,
`generated_at`, `repos`, `sessions`, `warnings` and their whitelisted fields. If the command
fails, the JSON does not parse, or `schema` is not `1`, report that estado is unavailable.
Do not rebuild the same projection with ad hoc searches.

| Data | Estado report field |
|------|---------------------|
| Plans | `repos[].plans[]`: `id`, `goal`, `status`, `path` and `nodes`. Ignore `done`, `complete`, `completed` and `closed`; list `paused` separately; treat unknown values as `draft` and warn. |
| Current session | Match `sessions[]` by worktree, branch or id, in that order. Never infer from the title. |
| Worktrees | `repos[].worktrees[]`; accept `.wt/` and harness-managed worktrees. |
| PR | `sessions[].pr`, using `--with-prs` when fresh PR state matters. |

Allowed supplemental reads for data that n1 does not model:

- Backlog: from the plan that declares it or `docs/plans/*backlog*.md`; read only the rows
  table and the last 10 log lines. If a row conflicts with an n1 node, the row wins and the
  discrepancy appears under Riesgos.
- File overlap: `git diff --name-only origin/main...<branch>` only for candidate branches
  already returned by the report.

Cargar `references/ejemplos.md` solo para ver el formato (las reglas viven aquí); `references/relevo.md`
solo al hacer relevo. No releer ninguno en la misma sesión.

## Momento 1 — abrir

Condition: the report returns at least one `active`, `draft` or non-`done` plan for the repo.
Once per session. If the owner's first message is a closed question, defer M1 until the first
topic change or `/conductor`. In the block, report the number of active plans, the most likely
next node (the first `pending` node whose dependencies are `done`) and whether the current
session matches one. Show at most five rows: active PRs or branches first, then rows waiting
for an owner decision. Group consecutive ✅ nodes on one graph line. If more remain, say
«y N más; pide /conductor para la lista». End with one short question or no question.

## Momento 2 — relación detectada

Speak only on a **deterministic** signal, in this order: (1) the report links the same branch
to a node or PR; (2) the branch shares changed files with another worktree branch, using
`git diff --name-only` against `origin/main`; (3) commits, PR or branch cite the same plan or
node, but only when both branches have unmerged commits (`git rev-list --count
origin/main..<branch>` > 0) or an open PR; group branches for the same node in one warning;
(4) an explicit owner reference («esto es lo de X»). Stay silent without a signal. Never infer
from text similarity. Speak once per session-item pair. Content: «<título A> toca lo mismo
que <título B> (<señal>). ¿Terminamos B antes y luego <C>?». When work should move, offer
`delegate` for a loose idea or `jump` for a next step; never run them automatically.

## Momento 3 — cerrar

Trigger on `/wind-down`, «cerremos» or an evident end. Run the core with `--with-prs`. In the
block, show the node that advances and propose the plan log row without writing it. Under
Estado, show what remains for integration (ready PR, CI and comments) and the next item. This
is status, not a decision. For a handoff to another session or harness, use
`references/relevo.md`. After approval, write only the node status and log row to the plan,
append-only as required by `topology`; never reshape the graph.

## Orquestación

- Backlog sin scope claro → propón `frontier`. Scope cerrado sin grafo → `topology`.
- Idea lateral que no es de esta sesión → `delegate`. Siguiente paso o QA con otro
  arnés → `jump`. Cierre → `wind-down` (el conductor no lo reemplaza).
- Una propuesta por intervención; el propietario elige.

## Cuándo NO hablar

Repo sin planes; sesión de pregunta rápida; sin señal determinista; ya avisado para ese
par; mitad de una tarea que el propietario está dictando; intervención repetida del mismo
momento sin cambio de estado. Ante duda, calla.

## Costo de contexto

SKILL.md costs about 2 K tokens when loaded. Each moment consumes one reconciled JSON report
and runs supplemental git queries only when a signal requires them. Load the references
(about 1 K tokens each) on demand. Chat output budget: one compact block per intervention,
at most three interventions per session.
