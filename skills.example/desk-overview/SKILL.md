---
name: desk-overview
description: Muestra el estado del proyecto o conjunto de repos actual, trabajo entre sesiones, decisiones pendientes y asuntos relacionados del brief.
---

# desk-overview

Lee `../desk-context/references/control.md`. Observa y presenta; no actualices fuentes ni publiques por el hecho de consultar. Una autorización explícita posterior puede registrarse según ese contrato.

## Alcance y fuentes

Ejecuta `secretary-desk overview --context <cwd-real>`. Sin argumento: contexto de la sesión, no todo el sistema. Dentro de un repo, usa ese proyecto y todos sus worktrees; en un contenedor, los repos configurados debajo; sin match, explica la cobertura y consulta el repo actual con herramientas disponibles sin ampliar a todos. Resuelve worktrees administrados usando el repo común y el proyecto de la sesión. Un argumento de proyecto o repo fija el alcance.

El helper devuelve git, PR, stash, fuentes de rutinas y decisiones con errores visibles. Los stashes pertenecen al repo compartido: no sumes el mismo stash por worktree. Los contadores remotos de git son caché: verifica con fetch si necesitas afirmar actualidad. No equipares ausencia de datos con ausencia de trabajo.

Consulta herramientas de sesiones del harness (en Codex, list_threads/read_thread; en otros, su inventario disponible). Cruza repo, checkout, rama y PR. Indica harness, sesión y actividad cuando haya evidencia; un transcript reciente no prueba que siga ejecutándose. Declara cobertura no disponible para otros harnesses. No interrumpas ni envíes mensajes a otras sesiones.

Consulta `secretary-desk decisions` para decisiones globales y `secretary-desk signals` para reportes de utilidad de rutinas. Lee las fuentes originales antes de concluir. Cruza issues abiertos, PR pendientes, state, recurrence y políticas vigentes. Especialmente job-search y ventas: fuentes agotadas, falta de resultados, cola vacía y cambios de estrategia. No revivas como pendiente un bloqueo histórico resuelto por una regla posterior.

Localiza el brief más reciente de la fecha local y sus comentarios sec-status. Cruza progreso con evidencia real; no marques completado solo por etiqueta, checkbox o PR abierto.

## Entrega breve

Primero responde al motivo de la consulta:
- Estado del proyecto: sesiones, ubicaciones/harness, worktrees, PR, dirty, commits sin publicar, stash y bloqueos.
- Requiere tu decisión: hasta tres propuestas prioritarias con evidencia, recomendación y decisión requerida. Expón cuántas quedan y sus enlaces. Incluye decisiones sobre utilidad de las rutinas del contexto y urgencias globales. Si no hay urgencia, señala aparte el número de decisiones globales pendientes sin desplazar el proyecto.
- Desde el brief: avances, entregas y asuntos relacionados, enlazados.
- Cobertura y frescura: qué se comprobó, qué faltó y de cuándo es.

Conserva el estado de posposición en el issue mediante comentario firmado solo cuando el propietario lo pida. La consulta sola no autoriza ejecución. No ofrece trabajo nuevo automáticamente ni obliga a leer el brief completo.
