# Research: sec-compose

**Input**: [spec.md](spec.md) · **Phase**: 0 (retrofit — decisiones ya tomadas en el draft aprobado 2026-06-08, reformateadas al formato Spec Kit, no re-investigadas)

Migrado desde el bloque "Decisiones de diseño — resueltas en v1" de `spec.md` (DD-1…DD-5).
Sin cambio de contenido, solo de formato: cada decisión ya tenía la forma
decisión/razón/alternativa descartada, que es exactamente lo que pide esta fase.

## DD-1 — Mecanismo de aislamiento de contexto

- **Decision**: correr `sec-compose` como subagente vía el tool `Agent`.
- **Rationale**: la lectura de wiki + reuniones es voluminosa; el subagente devuelve solo los
  borradores y muere con todo su contexto pesado. Sin estado persistente que mantener.
- **Alternatives considered**: sesión hermana vía `dispatch`/`send_message` — más pesada,
  pensada para trabajo continuable. Rechazada: no hay necesidad de continuidad en este primitivo,
  es una llamada de una sola pasada.

## DD-2 — Ubicación en la familia `sec-*`

- **Decision**: `sec-compose` queda como skill `sec-*` puro, invocado directamente por el operador.
- **Rationale**: mantiene la "búsqueda de ancla por tema" dentro del skill hasta que exista un
  segundo consumidor real que justifique extraerla.
- **Alternatives considered**: extraer un primitivo interno `sec-sys-find-anchor` (patrón
  `sec-sys-*` reservado para mecánica invocada por otros skills, no por el usuario). Rechazada
  por ahora — un solo consumidor no justifica la indirección (regla de tres).

## DD-3 — Origen del "tema" de búsqueda

- **Decision**: inferencia por defecto (el subagente extrae conceptos clave del `material`),
  con `tema` como override explícito opcional.
- **Rationale**: cubre el caso común (el operador no quiere pensar el tema de antemano) sin perder
  control cuando la inferencia no alcanza.
- **Alternatives considered**: exigir `tema` siempre explícito. Rechazada — fricción
  innecesaria para el caso gatillo (US-1), donde el tema es obvio del material.

## DD-4 — Selección de ancla entre varias candidatas

- **Decision**: elegir la conversación más temática (mayor afinidad con el material), no la más
  reciente; nombrar la elegida (fuente, fecha, razón) en el reporte.
- **Rationale**: recencia no es proxy de relevancia — una conversación de hace meses sobre el
  tema exacto ancla mejor que una de ayer sin relación. El reporte explícito deja a el operador
  corregir la elección sin tener que confiar ciegamente.
- **Alternatives considered**: ancla siempre por recencia (más simple, pero produce anclas
  irrelevantes cuando la última conversación no tocó el tema). Rechazada.

## DD-5 — Persistencia de memoria

- **Decision**: `sec-compose` no escribe wiki, no deja `sec:pending`, no toca `*/memory/` — es
  primitivo de salida pura.
- **Rationale**: registrar "el operador compartió X" antes de que efectivamente lo comparta sería
  persistir un envío no confirmado como si fuera un hecho. Ver `feedback_desahogos_no_son_acciones`
  y la doctrina de envíos explícitos.
- **Alternatives considered**: dejar un `sec:pending` automático al generar el borrador.
  Rechazada — acopla generación con confirmación de envío, dos eventos distintos que no siempre
  coinciden (el operador puede pedir el borrador y no usarlo).

## Notas de la migración (no eran gaps, son honestas sobre el formato)

Esta es una migración retroactiva de una feature ya implementada (v1, aprobada 2026-06-08) — no
una investigación previa a construir. No hay `NEEDS CLARIFICATION` pendiente: las 5 decisiones
ya estaban cerradas en el spec original.
