# Implementation Plan: sec-compose

**Branch**: `006-sec-compose` | **Date**: 2026-07-27 (retrofit — implementado desde 2026-06-08) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/L2-memoria/006-sec-compose/spec.md`

**Nota de retrofit**: este `plan.md` se escribió después de que `sec-compose` ya estaba
implementado y en uso — es una migración de contenido que vivía suelto en `spec.md`
(`## Decisiones de diseño`, `## Implementación`) al árbol de documentos que define
`_diseño/.specify/templates/plan-template.md`, no un plan pre-implementación real. Se marca
explícitamente para no aparentar un orden que no ocurrió.

## Summary

`sec-compose` es un primitivo de salida de la familia `sec-*`: toma `(material, destinatario,
[canal], [tono], [tema])` y devuelve 1-2 borradores de mensaje anclados en el historial real de
conversación con esa persona (wiki + reuniones), sin escribir memoria ni enviar nada. Corre
como subagente aislado para no ensuciar el contexto de la sesión que lo invoca.

## Technical Context

**Language/Version**: N/A — no es código compilado; es un `SKILL.md` (prompt estructurado) que
orquesta tools nativos del harness (`Agent`, lectura de archivos) y reusa `sec-recall`.

**Primary Dependencies**: `sec-recall` (capa de lectura de wiki/memoria, reusada sin cambios) ·
tool `Agent` (mecanismo de aislamiento, nativo del harness) · `.secretary.yml` (resolución de
rutas lógicas: `wiki.articulos`, `meetings.summaries`, `meetings.memory`).

**Storage**: N/A — primitivo de salida pura, no persiste nada (ver DD-5 en [research.md](research.md)).

**Testing**: Manual, vía el caso gatillo US-1 (ver [quickstart.md](quickstart.md)). No hay
suite automatizada — consistente con el resto de la familia `sec-*` (skills, no software con
CI de tests unitarios).

**Target Platform**: Claude Code / harness de sesión interactiva del operador.

**Project Type**: Skill (primitivo de salida) — no aplica ninguna de las opciones de
proyecto de software (single/web/mobile) del template.

**Performance Goals**: N/A — no hay presupuesto de latencia declarado; el corte de calidad es
"no contamina el contexto de la sesión invocadora", ya cubierto por el aislamiento en subagente.

**Constraints**: debe respetar `feedback_tuteo_peruano` (registro del operador) y
`feedback_envios_explicitos` (nunca envía, siempre devuelve texto para copiar).

**Scale/Scope**: single-user (el operador), invocaciones ad-hoc en sesión — no diseñado para
concurrencia ni multi-tenant.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluado contra `_diseño/.specify/memory/constitution.md`:

- **Principio III (skills lean, 3 capas)** — ✅ pasa. El skill no repite doctrina invariante
  (idioma/firmas viven en `CLAUDE.md`), no hardcodea rutas (usa `.secretary.yml`).
- **Test anti-acoplamiento** (¿menciona al usuario por nombre?) — ⚠️ **hallazgo real, menor**:
  `~/.claude/skills/sec-compose/SKILL.md` menciona "el operador" por nombre 2 veces (líneas 67, 70:
  "If el operador prefers another candidate...", "...if el operador later..."). El propio principio III
  dice que eso es doctrina invariante (capa 1) y debería vivir en el `CLAUDE.md` del runtime,
  no en el skill. No bloquea (es referencia de tercera persona en texto de reporte, no una regla
  de negocio acoplada), pero es una limpieza pendiente real detectada por este gate — no se
  encontró en las auditorías anteriores porque estaban a nivel de `spec.md`, no de la
  implementación real.
- **Principio V (Spec Kit aplica en `_diseño/`)** — ✅ pasa; este mismo `plan.md` es la
  aplicación del principio.

**Resultado del gate**: PASA, con una nota menor no bloqueante (ver arriba). No hay violación
que requiera `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
_diseño/specs/L2-memoria/006-sec-compose/
├── spec.md              # Contrato: problema, insumos/salida, user scenarios, success criteria
├── plan.md              # Este archivo — contexto técnico + gate de constitución
├── research.md           # DD-1…DD-5 migradas: decisión + rationale + alternativa descartada
├── quickstart.md          # Caso US-1 como escenario de validación ejecutable
└── (data-model.md, contracts/, tasks.md — omitidos, ver nota abajo)
```

**Omitidos y por qué** (no se crean archivos vacíos por ritual):
- `data-model.md` — no hay entidades ni storage (DD-5: primitivo sin persistencia).
- `contracts/` — el contrato de I/O (`material, destinatario, canal, tono, tema → borradores`)
  ya está completo en `spec.md § Solución`; una carpeta de contratos separada duplicaría sin
  agregar información — el primitivo no expone una API externa formal (no es un servicio).
- `tasks.md` — es Fase 2 de `/speckit-tasks`, solo aplica a trabajo por implementar; `sec-compose`
  ya está implementado (v1, 2026-06-08).

### Source Code (repository root)

No aplica el árbol `src/`/`tests/` del template — no es un proyecto de software independiente.
El artefacto real vive en el runtime de skills, fuera de este repo de diseño:

```text
~/.claude/skills/sec-compose/SKILL.md    # implementación real (runtime, fuera de este repo)
```

**Structure Decision**: carpeta de spec mínima (spec + plan + research + quickstart), sin
`data-model.md`/`contracts/`/`tasks.md` — justificado arriba, no por omisión.

## Complexity Tracking

*Sin violaciones del Constitution Check — tabla no aplica.*
