---
name: sec-project-sync
description: Actualiza instrucciones estables y memoria operativa del proyecto con los cambios de la sesión; integrado en wind-down, reutiliza su close_context.
user-invocable: true
---

# sec-project-sync

Usa el `close_context` de `wind-down` cuando exista. No repitas la recogida de git, decisiones ni archivos. Invocado por separado, recoge solo el contexto necesario del proyecto activo una vez.

## Instrucciones estables

- `AGENTS.md` contiene reglas, comandos, fuentes canónicas, estructura y convenciones vigentes. Cambia solo ante una decisión estable de esta sesión. No añadas diarios, estado de PRs ni próximos pasos.
- Actualiza el archivo más cercano al proyecto afectado. La raíz mantiene un índice de los contextos de proyecto; no duplica sus instrucciones.
- Usa el contrato de entidad como fuente de verdad para estado, EDT y mirrors. Reporta contradicciones; no cambies el contrato dentro de este skill.
- Procedimientos largos e inventarios viven en skills o documentación bajo demanda. Deja referencias precisas y conserva en AGENTS.md los límites críticos.
- No crees CLAUDE.md. Si queda uno antiguo, no lo borres sin comprobar que se migró su contenido y que el harness carga AGENTS.md.
- Si no cambió ninguna instrucción estable, reporta «sin cambios de instrucciones».

## Higiene acotada

Revisa solo el trabajo de la sesión. No escanees otros worktrees. No borres archivos por patrones como `test_*.py`: podrían ser código real. Retira únicamente scratch que esta sesión creó e identificó como descartable, respetando las reglas del repo.

Si hay contrato de entidad, verifica la estructura afectada contra el EDT. No inventes actividades ni reconstruyas el contrato desde carpetas. Si falta un contrato necesario, propón su creación por el flujo correspondiente.

## Continuidad

Durante wind-down, agrega el resultado de esta revisión al `close_context`; `handover` es el único escritor del brief. No generes otro documento.

Invocado por separado, actualiza un brief existente solo si se solicita continuidad; no lo crees automáticamente por cada sincronización.

Reporte breve: instrucciones cambiadas, higiene aplicada, contradicciones y bloqueo pendiente. No hagas cambios fuera de la autorización de la sesión.
