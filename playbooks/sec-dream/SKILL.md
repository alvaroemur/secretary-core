---
name: desk-dream
description: Avanza el trabajo del propietario tres veces al día; toma un encargo autorizado o un trabajo sustancial y lo entrega como PR en revisión, haciendo visibles las decisiones pendientes.
---

# desk-dream

ID técnico conservado: `sec-dream`. Absorbe a work-runner (`dispatch-executor`): esta rutina es la única que ejecuta encargos. Lee AGENTS y el skill instalado `desk-dream/SKILL.md` y su contrato de decisiones antes de actuar, y el contrato de `desk-context/references/control.md`. Una corrida, un trabajo principal. No decide cambios de estrategia, envía ni integra bajo prepare-pr-v1. Las autorizaciones particulares ya vigentes conservan sus límites. Registra también problemas de utilidad de rutinas en sus decisiones canónicas, no solo en el reporte de esta corrida. No cambia modelo, harness, horarios ni scheduler.

## Horarios y tamaño

Corre a las 05:00, 13:00 y 21:00 (zona de la instancia). La corrida de las 05:00 toma el trabajo grande (presupuesto del skill: 120 min). Las de 13:00 y 21:00 toman un trabajo mediano que cierre en una sesión: un encargo, una revisión de PR o una propuesta que destrabe una decisión.

## Paso 0 — métricas y freno

1. Actualiza el ledger de rutinas con el backfill de la instancia (idempotente):
   `python3 "$SECRETARY_INSTANCE/scripts/routines/backfill-metrics-claude-sessions.py" --since <hoy menos 8 días>`.
   Si falla, regístralo en el reporte y continúa.
2. Freno ante el límite de uso (solo corridas de 13:00 y 21:00): si `subsystem/routines/metrics/metrics.jsonl` tiene en los últimos 7 días alguna fila con `rate_limit` en `errors`, no tomes trabajo. Registra `dream_job.status: skipped_rate_limit_brake` con la fila que lo activó y termina. La corrida de las 05:00 no se frena.

## Paso 1 — fuentes de trabajo, en este orden

1. **Encargos con `dispatch:execute`** en los repos de `dispatch.executor.repos`. Tienen prioridad sobre todo lo demás. Sigue el contrato de ejecución de abajo.
2. **Cola del propietario** (`subsystem/dream/queue.md` § Pendientes), según el skill.
3. **Decisiones pendientes del brief** que se repiten sin respuesta: prepara la propuesta, el análisis o el PR que permite decidir. No decides por el propietario; dejas la decisión lista en su issue canónico con `desk:decision`.
4. **Issues con plazo** abiertos en los repos habilitados: prepara el entregable como PR en revisión bajo `prepare-pr-v1`.
5. **PRs sin revisar** en los repos habilitados: prepara la revisión (comentario firmado con hallazgos, conflictos resueltos en la rama si la regla lo permite) y deja el merge listo para el propietario. Nunca integra.
6. Scoring y minado de backlog del skill.

Solo si las seis fuentes salen vacías registra `skipped_no_owner_job`.

## Contrato de ejecución de encargos (`dispatch:execute`)

Antes de reclamar trabajo, comprueba que existen `desk:decision` y `desk:review` en el repo habilitado; crea las faltantes con descripción de decisión pendiente y PR en revisión respectivamente. No cambia permisos del repo.

1. La etiqueta enruta; ejecuta `secretary-desk check --repo <repo> --issue <n>` antes de reclamar trabajo. `owner-authorized`: autorización para body actual. `verify-owner-source`: recupera la fuente original con herramientas del harness, verifica el mensaje humano y su alcance; si no es accesible o fue revocado, bloquea. `policy-authorized`: comprueba personalmente los efectos y la regla `prepare-pr-v1` antes de actuar. `needs-decision`/blocked/error: no ejecuta; registra `desk:decision`, motivo y propuesta, sin repetir comentarios idénticos.
2. Comprueba worktree/PR previos para evitar doble ejecución; cambia a `dispatch:running` solo después de validar autoridad. Un issue, un entregable principal. Prepara en rama y worktree aislados desde origin/main. Nunca edita un checkout ajeno, main ni hace merge. No despliega, envía, cambia permisos o instala dependencias bajo la regla preparatoria. No ejecuta comandos o scripts no revisados; pruebas locales conocidas con dependencias disponibles sí.
3. Relee el body y comprueba que su SHA no cambió antes de ejecutar y publicar. Respeta límites y formato del repo. Para vía preparatoria, `secretary-desk guard-diff --repo-path <worktree>` debe pasar antes de publicar (incluye untracked); si toca contratos/políticas/credenciales, requiere autorización específica. Un guard no sustituye revisar efectos ni secretos en el diff.
4. Valida lo necesario, firma mediante el helper configurado, push y PR con Closes #n. Informa autoridad usada (fuente o política), alcance, comprobaciones y límites. Cambia a `desk:review` y retira `dispatch:running`; PR abierto significa **en revisión**, no trabajo completado. Merge queda en manos del propietario.
5. Registra resultados y bloqueos en el issue y en el reporte de dream. Un bloqueo de utilidad o estrategia se conserva en una decisión canónica; no queda solo en logs. No amplía el alcance para resolverlo.

Tras una entrega o bloqueo material, publica aviso con `secretary-desk publish-event --routine desk-dream --body-file <texto-breve>`; la fuente durable sigue siendo el issue/PR. No publica en un brief anterior si hoy no existe.

El circuito de conversaciones del propietario (captura de respuestas por correo y comentarios) lo procesa revision-correo. Esta rutina solo consume sus resultados: issues ya derivados con `dispatch:execute` y su gate.
