---
name: desk-dream
description: Rutina programada (05:00, 13:00, 21:00) que elige su propio trabajo y entrega PRs no pedidos solo cuando son útiles para un compromiso del propietario; reporta cada corrida sin PR de reporte.
---

# desk-dream

ID técnico conservado: `sec-dream`. Absorbe a work-runner (`dispatch-executor`): esta rutina es la única que ejecuta encargos. Lee AGENTS de la instancia, `procedure.md` junto a este archivo y el contrato de `desk-context/references/control.md`, y sigue el procedimiento completo. Ya no existe el skill `desk-dream`: este playbook y su procedimiento son la única fuente.

Una corrida, un trabajo principal. No decide cambios de estrategia, no envía y no integra. Las autorizaciones particulares vigentes conservan sus límites. Registra los problemas de utilidad de rutinas en sus decisiones canónicas, no solo en el reporte. No cambia modelo, harness, horarios ni scheduler.

Resumen del procedimiento:

1. Métricas y freno por límite de uso.
2. Estado de los PRs de dream: refresca la lista del hook de solape, evalúa la utilidad de los de 7 días o más y respeta el tope de 10 sin revisar.
3. Fuentes en orden: encargos `dispatch:execute`, cola del propietario (opcional), síntesis entre señales, decisiones pendientes del brief, issues con plazo, minado de backlog. La revisión de PRs ajenos no es fuente.
4. Seis filtros de utilidad antes de abrir un PR no pedido; si fallan, registra el motivo y no abre nada.
5. Entrega en un worktree `<repo>/.wt/<rama-slug>`, PR con metadato `dream:entrega`.
6. Reporte por worktree temporal + commit + push, sin PR de reporte; aviso en el brief.
7. `secretary dream emit-metrics`.
