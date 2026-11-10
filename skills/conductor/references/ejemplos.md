# conductor — ejemplos (cargar solo para ver formatos)

Salidas esperadas. Los títulos son ficticios.

## Momento 1 — abrir
> 2 planes en marcha. Siguiente probable: «n2 · migración de esquemas» (plan «cierre del backlog»); n1 · «inventario» está hecho. ¿Entramos ahí?

## Momento 2 — relación detectada
Señal: la rama `core/skills-x` de esta sesión comparte `skills/jump/SKILL.md` con el worktree de «n4 · ajuste de jump».
> «Ajuste de skills-x» toca los mismos archivos que «n4 · ajuste de jump» (señal: archivos). ¿Terminamos n4 antes y luego «n5 · pruebas de jump»?

Referencia explícita: el propietario dice «esto es lo del plan de WhatsApp».
> Entendido: lo ligo a «n3 · revisión local» (plan «whatsapp-local»). Al cerrar te propongo la fila del log.

## Momento 3 — cerrar
> «n2 · migración» avanza a done: PR #41 listo, CI verde. Propongo anotarlo en el plan (fila de estado + log); siguiente: «n3 · documentación». ¿Anoto?

## Avisos de disciplina (modo «avisa»)
> Aviso: esta rama no está en un worktree propio y el commit «arreglos» no es convencional. Sin acción por mi parte.

## Casos en los que NO debe hablar
- Repo sin `docs/plans` (o todos `status: done`).
- Pregunta suelta («¿qué hace este flag?»).
- Dos sesiones editan archivos distintos y solo se parecen en el tema: sin señal determinista, calla.
- Ya avisó de esa relación en esta sesión.
- El propietario dijo «ok» a un detalle técnico: no es aprobación para escribir en el plan.
