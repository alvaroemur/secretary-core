---
name: jump
description: Propone continuaciones de la sesión y genera prompts para otro harness, reutilizando el brief único de wind-down cuando exista.
user-invocable: true
---

# jump

Ofrece próximos pasos; no cierra la sesión ni hace push/merge. No crea chats ni delega sin autorización.

## Contexto

Si recibes `close_context`, usa su estado, decisiones, plan y brief. No repitas git ni la conversación, no leas otros worktrees y no generes otro brief.

Invocado por separado, consulta una vez el estado y rama del checkout activo, el plan activo (`docs/plans/` o `_diseño/plans/`), contrato de entidad y brief pertinente. No inventes nodos del plan ni actividades EDT.

## Opciones

Propón solo las opciones que tengan fundamento, con intención y nivel recomendado:

| Opción | Cuándo aplica |
|---|---|
| Replicar | Aplicar el método a otro dataset, cliente o tema |
| Revisar | Validar un artefacto producido o contrastar evidencia |
| Siguiente paso | Continuar un nodo listo del plan o una actividad EDT |
| Hilo lateral | Capturar una idea que pertenece a otro trabajo |

El usuario elige qué prompts generar y su nivel. No repitas una elección ya aportada por wind-down.

- Breve: acción y destino, una o dos líneas; la siguiente sesión lee el repo.
- Operativo: objetivo, nodo/actividad, fuentes, entregable y criterio de terminación.
- Autónomo: contexto autocontenido, destino, decisiones, límites, fuentes y aceptación. No depende del historial del chat.

## Continuación portable

Durante wind-down, apunta al brief existente y al primer archivo a leer. El prompt indica objetivo y criterio de terminación; no copia las instrucciones globales ni presupone herramientas exclusivas de un harness.

Invocado por separado, deja el prompt en chat; escribir un brief es opcional y requiere autorización. Mantén briefs de Cowork/Dev en su repo. Para offload, usa el flujo disponible de issue y contexto limpio tras la elección del usuario.

No cambies contract.yaml ni el grafo de un plan para elaborar una continuación. Si no hay trabajo material, reporta continuidad y pendientes en dos líneas; no bloquees el cierre ni produzcas un brief vacío.
