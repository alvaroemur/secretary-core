---
name: handover
description: Escribe un único brief de continuidad para retomar en otro harness; reutiliza close_context cuando lo llama wind-down.
---

# handover

Un cierre produce un solo brief. Si recibes `close_context`, úsalo sin volver a consultar git ni releer la conversación. Si te invocan por separado, recoge una sola vez el contexto del repo activo y las decisiones de la conversación.

## Destino e identidad

- En wind-down: `<checkout-real>/.briefs/YYYY-MM-DD-HHMM-<slug>.md`. El cierre fija la ruta en `close_context`; las llamadas posteriores de esa sesión actualizan ese mismo archivo.
- Invocación independiente: respeta el destino explícito; por defecto usa `.briefs/` del repo activo. Un handover para otra persona puede usar `docs/handovers/` si se solicita.
- No escribas briefs de Cowork/Dev en la instancia. Respeta rutas absolutas del checkout real y las políticas de firma.
- Si falta una decisión necesaria, pregunta una sola vez. No vuelvas a pedir los datos ni autorización ya aportados por wind-down o el usuario.

## Contenido mínimo

1. Identidad: sesión, repo, rama, commit y fecha con zona horaria.
2. Objetivo y resultado observable de la sesión.
3. Estado actual de los archivos afectados y decisiones confirmadas con su motivo.
4. Bloqueos y preguntas pendientes.
5. Siguiente acción, criterio de terminación y primer archivo a leer.
6. Referencias canónicas, PRs/issues y comprobaciones ya realizadas o pendientes.

Usa rutas del repo y enlaces reales. No dependas de ids de chats, herramientas exclusivas del harness ni memoria interna para poder retomar. Un link al chat puede ser complementario, nunca la única fuente. No copies la transcripción ni instrucciones globales enteras.

No inventes estados ni incluyas secretos. No actualices AGENTS.md: eso corresponde a sec-project-sync. Durante wind-down no hagas git add/commit/push por separado: el orquestador reúne los cambios. No ejecutes tests/builds para elaborar el brief.

Devuelve la ruta y el resumen al orquestador. `jump` usa ese resultado; no crea otro brief.
