# conductor — ejemplos (cargar solo para ver formatos)

Títulos y enlaces ficticios; en uso real enlaza solo archivos que existen (`ls`).

## Bloque completo (cualquier momento)

Fuera del bloque, el harness conversa normal («Abrí el repo; esto es lo que veo:»). Lo del conductor va así:

> ▌ **conductor**
> Fila = frente · nodo (n) = paso de la fila · F = fallo a corregir · #n = pull request
>
> **Estado**
>
> | Fila | Qué busca | Dónde va |
> |------|-----------|----------|
> | [Fila G · publicación segura de entregas](docs/plans/publicacion-segura.md) | Que ninguna entrega salga sin revisión | G n7 · prueba de dry-run, en curso |
> | Fila ACC · archivo de cuentas cerradas | Plegar cuentas sin perder rastro | ACC n2 · plegado, bloqueado por #41 |
>
> ```text
> G · publicación segura de entregas
> ├─ ✅ n5 · inventario de destinos
> ├─ ❓ n7 · prueba de dry-run   ← esta sesión
> └─ ⏳ n8 · activación           (espera n7)
> ```
>
> **Decisiones**
> - DEC-1 · dry-run antes de activar ([plan](docs/plans/publicacion-segura.md)). Para ti: nada sale sin que lo veas.
>
> **Riesgos**
> - RSK-1 · #41 sin CI verde bloquea ACC n2. Para ti: ACC espera hasta que se arregle.
>
> **Pregunta**
> - CND-1 · ¿Terminamos G n7 antes de tocar ACC n2?
>
> ```text
> CND-1: sí
> ```

## Momento 1 — abrir
Mismo bloque, solo con Estado (tabla corta + grafo del plan más probable) y Pregunta.

## Momento 2 — relación detectada
Señal: la rama de esta sesión comparte `skills/jump/SKILL.md` con otro worktree.
Bloque con Estado (las dos filas implicadas), Riesgos (RSK-1 · edición cruzada del mismo archivo; para ti: conflicto al integrar) y Pregunta (CND-2 · ¿terminamos primero «Fila J · ajuste de jump»?).

## Momento 3 — cerrar
Bloque con Estado (nodo que avanza y fila propuesta para el log, sin escribirla), Decisiones (DEC-1 · qué falta para integrar: PR listo, CI, comentarios) y Pregunta (CND-3 · ¿anoto el estado en el plan?).

## Avisos de disciplina (modo «avisa»)
Una línea dentro de Riesgos: «RSK-2 · rama sin worktree propio y commit no convencional. Para ti: nada que hacer ahora; lo corrijo si me lo pides.»

## Casos en los que NO debe hablar
- Repo sin `docs/plans` (o todos `status: done`).
- Pregunta suelta («¿qué hace este flag?»).
- Dos sesiones editan archivos distintos y solo se parecen en el tema: sin señal determinista, calla.
- Ya avisó de esa relación en esta sesión.
- El propietario dijo «ok» a un detalle técnico: no es aprobación para escribir en el plan.
- Un enlace que no existe en disco: no se muestra.
