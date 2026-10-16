---
name: brief-update
description: Publica cambios materiales del estado y decisiones pendientes en el brief existente, sin ejecutar trabajo ni crear otro brief.
---

# brief-update

ID técnico conservado: `pulse-headless`; no registra un cron nuevo. Lee AGENTS y el contrato de `desk-context/references/control.md`. Reutiliza fuentes/criterios de desk-overview para cobertura global; no pide hidratar trabajo ni autoriza acciones.

Busca el brief de la fecha local exacta. Si falta, registra el fallo; no comenta un brief anterior. Compara heartbeat, sec-status, PR y decisiones con el último reporte. Publica un comentario firmado solo ante cambios materiales: entrega, fallo, decisión nueva/vencida, urgencia o desbloqueo. Incluye problemas de utilidad de rutinas como falta de fuentes o cambio de estrategia; usa sus issues canónicos. Sin cambios materiales, registra no-op sin comentario.

Deduplica por fingerprint del contenido, no por fecha: puede publicar otro avance durante el mismo día si cambió el estado. No envía otro correo, no modifica checkboxes, no crea issues/PR ni ejecuta encargos. Abrir PR es en revisión; fusionarlo se reporta aparte.

La publicación material puede ejecutarse sin otro modelo usando `secretary-desk publish-event --routine <id> --body-file <texto>`. Esto permite avisos durante el día aunque no exista una tarea nativa periódica habilitada.
