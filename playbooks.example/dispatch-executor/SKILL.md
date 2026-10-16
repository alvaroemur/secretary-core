---
name: work-runner
description: Prepara encargos autorizados en worktrees y entrega PR para revisión; nunca integra ni toma una etiqueta como consentimiento.
---

# work-runner

ID técnico conservado: `dispatch-executor`. Lee AGENTS de instancia y destino, y el contrato de `desk-context/references/control.md` instalado. Respeta la allowlist `dispatch.executor.repos`. No cambia modelo, harness, horarios o scheduler.

1. Consulta issues abiertos con `dispatch:execute`. La etiqueta enruta; ejecuta `secretary-desk check --repo <repo> --issue <n>` antes de reclamar trabajo. `owner-authorized`: autorización para body actual. `verify-owner-source`: recupera la fuente original con herramientas del harness, verifica el mensaje humano y su alcance; si no es accesible o fue revocado, bloquea. `policy-authorized`: comprueba personalmente los efectos y la regla `prepare-pr-v1` antes de actuar. `needs-decision`/blocked/error: no ejecuta; registra `desk:decision`, motivo y propuesta, sin repetir comentarios idénticos.
2. Comprueba worktree/PR previos para evitar doble ejecución; cambia a `dispatch:running` solo después de validar autoridad. Un issue, un entregable principal. Prepara en rama y worktree aislados desde origin/main. Nunca edita un checkout ajeno, main ni hace merge. No despliega, envía, cambia permisos o instala dependencias bajo la regla preparatoria. No ejecuta comandos o scripts no revisados; pruebas locales conocidas con dependencias disponibles sí.
3. Relee el body y comprueba que su SHA no cambió antes de ejecutar y publicar. Respeta límites y formato del repo. Para vía preparatoria, `secretary-desk guard-diff --repo-path <worktree>` debe pasar antes de publicar (incluye untracked); si toca contratos/políticas/credenciales, requiere autorización específica. Un guard no sustituye revisar efectos ni secretos en el diff.
4. Valida lo necesario, firma mediante el helper configurado, push y PR con Closes #n. Informa autoridad usada (fuente o política), alcance, comprobaciones y límites. Cambia a `desk:review` y retira `dispatch:running`; PR abierto significa **en revisión**, no trabajo completado. Merge queda en manos del propietario.
5. Registra resultados y bloqueos en el issue y reporte para heartbeat/brief-update. Un bloqueo de utilidad o estrategia se conserva en una decisión canónica; no queda solo en logs. No amplía el alcance para resolverlo.

Tras una entrega o bloqueo material, publica aviso con `secretary-desk publish-event --routine work-runner --body-file <texto-breve>`; la fuente durable sigue siendo el issue/PR. No publica en un brief anterior si hoy no existe.
