<!-- claude-generated:dispatch -->
> Nota (2026-07-27): tras la auditoría de `_diseño/specs/`, el contrato formal vive en
> [`spec.md`](spec.md), el contexto técnico y el gate de constitución en [`plan.md`](plan.md),
> y las decisiones DD-1…DD-5 en [`research.md`](research.md). Este archivo queda como la
> narrativa de origen (el gatillo real, la sesión de dispatch) — no se duplica en los otros.

# Feature 006 — `sec-compose`: destilar fragmento + destinatario → mensaje contextualizado

**Estado:** `implementado v1 — SKILL.md en runtime` (draft aprobado por el operador 2026-06-08)
**Origen:** dispatch desde sesión de diseño de la "capa de enriquecimiento" de la wiki (2026-06-08).
**Decisión de naming relacionada:** `../../decisiones/2026-06-07-naming-skills.md` (instance design log)

## Síntesis del problema

La familia `sec-*` cubre **leer** memoria (`sec-recall`), **escribir** memoria (`sec-write`)
y **mantenerla** (`sec-consolidate`). Falta el primitivo simétrico de **salida**: tomar un
material (un fragmento, una idea, un link) y un **destinatario** de la wiki, y producir un
mensaje listo para copiar, **contextualizado por el historial de relación** con esa persona.

El gatillo concreto: el operador tenía un párrafo técnico (una crítica sobre vector DBs/embeddings)
que quería compartir con [[personas/greg-minaya|Greg]]. Invocó `sec-recall` esperando que
secretary relacionara el material con la wiki y armara el mensaje — pero `sec-recall` solo
**lee y reporta**; no compone salida. El building block no existe.

## Solución propuesta

Un primitivo de **síntesis/composición orientado a salida** — `sec-compose` — distinto de
los de lectura/escritura. Recibe `(material, destinatario, [canal], [tono], [tema])` y devuelve
1-2 borradores en el registro del operador (tuteo peruano), **nunca un envío automático**.
`[tema]` es override explícito cuando la inferencia del material no alcanza.

Su trabajo no es solo redactar: es **anclar el material en la conversación previa relevante**
con ese destinatario. Para Greg, encuentra que en una reunión hablaron de sistemas RAG,
agentes y el trabajo de Greg, y ofrece dos variantes: arranque nuevo ("hey, ¿cómo estás?
estaba pensando…") o continuación ("como te decía la otra vez…").

**Corre aislado** (subagente), para no contaminar el contexto de la sesión que lo invoca.
Ese es un requisito explícito: la sesión en curso sigue limpia; solo recibe de vuelta los
borradores.

## Composición con la familia

```
sec-compose  →  (subagente)  →  sec-recall sobre el destinatario  →  borradores
                                  + extractors/meetings/summaries/ y memory/
                                    (paths vía .secretary.yml)
                                  + scan PRs auto-* abiertos (anti-amnesia)
```

Reusa `sec-recall` como capa de lectura; no reimplementa la búsqueda en memoria.

## Estado v1

`SKILL.md` lean desplegado en `~/.claude/skills/sec-compose/` (runtime), siguiendo el molde
de `canon/rules/skills/skills.md`. Decisiones DD-1 a DD-5 cerradas en spec (2026-07-02).

## Próximo paso

Probar `sec-compose` con el caso gatillo (material sobre vector DBs → Greg) y ajustar el
SKILL.md si el borrador resultante no engancha bien la conversación previa.

---
🤖 _Generado por Claude Code — dispatch · 2026-06-08_
