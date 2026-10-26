---
name: pulse-headless
description: Publica cambios materiales del estado y decisiones pendientes en el brief existente, sin ejecutar trabajo ni crear otro brief. Piloto D15.2: 1 corrida diaria 13:30 hasta 2026-11-06.
---


# brief-update

ID técnico conservado: `pulse-headless`. Piloto D15.2 (2026-10-23 a 2026-11-06): una corrida diaria a las 13:30 America/Lima. Lee AGENTS y el contrato de `desk-context/references/control.md`. Reutiliza fuentes/criterios de desk-overview para cobertura global; no pide hidratar trabajo ni autoriza acciones.

Busca el brief de la fecha local exacta. Si falta, registra el fallo; no comenta un brief anterior. Compara heartbeat, sec-status, PR y decisiones con el último reporte. Publica un comentario firmado solo ante cambios materiales: entrega, fallo, decisión nueva/vencida, urgencia o desbloqueo. Incluye problemas de utilidad de rutinas como falta de fuentes o cambio de estrategia; usa sus issues canónicos. Sin cambios materiales, registra no-op sin comentario.

Deduplica por fingerprint del contenido, no por fecha: puede publicar otro avance durante el mismo día si cambió el estado. No envía otro correo, no modifica checkboxes, no crea issues/PR ni ejecuta encargos. Abrir PR es en revisión; fusionarlo se reporta aparte.

La publicación material puede ejecutarse sin otro modelo usando `secretary-desk publish-event --routine <id> --body-file <texto>`.

Al terminar, di en la primera línea del mensaje final si la corrida publicó un comentario material o fue no-op. El piloto se mide con ese dato.
