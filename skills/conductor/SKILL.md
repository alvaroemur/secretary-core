---
name: conductor
description: >-
  Conductor v0 (mínimo). Lleva el control del backlog sin llenar el chat: habla solo
  al abrir sesión en un repo con planes, al detectar relación entre el trabajo actual
  y otro ítem del backlog, y al cerrar. Lee planes en docs/plans, git worktree, gh y
  el helper de desk-overview; orquesta frontier, topology, delegate y jump. Lee y
  propone; no lanza sesiones ni escribe en planes sin OK. Triggers: "/conductor",
  "qué sigue en el backlog", "conductor". NOT para diseñar el grafo (topology),
  cerrar la sesión (wind-down) ni escribir prompts de continuación solos (jump).
user-invocable: true
---

# conductor — v0 mínimo

Plan de origen: `frontier-estado-visual-y-conductor` (CND-1 a CND-5). Esta v0 lee solo lo
que existe hoy; después se le cambia la fuente por la capa de estado sin tocar el
comportamiento. No construye estado, HTML ni chat.

## Reglas fijas

- **Habla solo en 3 momentos** (abajo). Fuera de ellos calla, salvo que el propietario
  invoque `/conductor`. No vuelques listas largas sin que el propietario las pida.
- **Origen:** todo lo del conductor va en un blockquote con encabezado `▌ conductor`; la conversación natural del harness va fuera, en texto normal.
- **Tablas:** sí se usan, para estados y comparaciones.
- **Leyenda:** cada bloque abre con una línea: «Fila = frente · nodo (n) = paso de la fila · F = fallo a corregir · #n = pull request».
- **Backlog:** una tabla por fila (qué busca, dónde va) y el grafo de nodos anidado en un bloque `text` con ✅ hecho · ❓ en curso · ⏳ bloqueado.
- **Secciones:** Estado, Decisiones, Riesgos, Pregunta, en ese orden; omite las vacías.
- **Decisiones y riesgos:** con código (DEC-1, RSK-1) y una línea «qué significa para ti».
- **Pregunta:** con código (p. ej. CND-1) y, al final, un bloque `text` con las respuestas prellenadas, como en `/frontier`.
- **Nomenclatura:** «Fila G», «Fila ACC»; todo nodo con su fila («G n7», nunca «n7»
  solo). Ninguna sigla sin nombre y propósito en la primera mención («Fila G · publicación
  segura de entregas»). Códigos siempre con su título.
- **Enlaces:** solo a archivos que existen (verifica con `ls`), uno por tema, en tres
  lugares: nombre de la fila, nodo que cambia, cada decisión o riesgo. La explicación
  larga vive en el documento enlazado, no en el chat.
- **Lee y propone.** Escribe en un plan solo tras OK explícito del propietario
  (un «ok» en un debate no cuenta; ver aprobación inequívoca). No lanza sesiones. No
  mergea, archiva ni borra sin OK, salvo reglas permanentes ya dadas (p. ej. `desk-merge`
  activo).
- **Disciplina de secretary: solo «avisa».** Nunca bloquea ni corrige solo. Avisa de:
  tema sin worktree propio (`.wt/<rama>` o `.claude/worktrees/<x>`), commits sin formato
  convencional, PR sin dejar listo antes de cerrar, wind-down pendiente, relevo al
  cambiar de sesión, falta de aprobación inequívoca antes de ejecutar, contexto > 150K
  tokens.
- **No lee contenido de transcripciones.** Solo metadatos (rama, worktree, PR, plan/nodo).

## Fuentes (todas de solo lectura, bajo demanda)

| Qué | Cómo |
|-----|------|
| Planes | `docs/plans/*.md` del repo y sus worktrees: frontmatter `id`, `goal`, `status`; nodos `nX` en la tabla `## Nodes`. Un plan sin frontmatter se lee como «sin metadatos» y se cita por nombre de archivo. Ignora `status: done`. |
| Worktrees | `git worktree list --porcelain` (tolera `.wt/` y `.claude/worktrees/`) |
| PR | `gh pr list --state open --json number,title,headRefName,isDraft,mergeable` |
| Estado amplio | `secretary-desk overview --context <cwd>` solo si hay duda; nunca pegar su salida |

Cargar `references/ejemplos.md` solo para ver el formato (las reglas viven aquí); `references/relevo.md`
solo al hacer relevo. No releer ninguno en la misma sesión.

## Momento 1 — abrir

Condición: repo con al menos un plan `active`/`draft`/sin `done`. Una vez por sesión.
Lee frontmatter y tablas de nodos (no cuerpos). Di, en el bloque: cuántos planes en
marcha, el nodo siguiente más probable (primer `pending` cuyas dependencias estén
`done`) y si la sesión parece haber caído en uno. Cierra con una pregunta corta o nada.

## Momento 2 — relación detectada

Solo con señal **determinista**, en este orden: (1) misma rama que un nodo/PR;
(2) mismos archivos que la rama de otro worktree (`git diff --name-only` contra
`origin/main`); (3) mismo plan/nodo citado en commits, PR o rama; (4) referencia
explícita del propietario («esto es lo de X»). Sin señal, calla; no infieras por
similitud de texto. Una vez por par (sesión, ítem). Contenido: «<título A> toca lo mismo
que <título B> (<señal>). ¿Terminamos B antes y luego <C>?». Si procede mover algo,
ofrece `delegate` (idea suelta) o `jump` (siguiente paso); nunca los ejecutes solo.

## Momento 3 — cerrar

Se activa con `/wind-down`, «cerremos» o fin evidente. Di, en el bloque: nodo que
avanza (propón la fila del log para el plan, sin escribirla), qué falta para integrar
(PR listo, CI, comentarios) y el siguiente ítem. Si hay relevo a otra sesión o arnés,
usa `references/relevo.md`. Con OK, escribe en el plan solo la fila de estado y del log
(append-only, como manda `topology`); no remodeles el grafo.

## Orquestación

- Backlog sin scope claro → propón `frontier`. Scope cerrado sin grafo → `topology`.
- Idea lateral que no es de esta sesión → `delegate`. Siguiente paso o QA con otro
  arnés → `jump`. Cierre → `wind-down` (el conductor no lo reemplaza).
- Una propuesta por intervención; el propietario elige.

## Cuándo NO hablar

Repo sin planes; sesión de pregunta rápida; sin señal determinista; ya avisado para ese
par; mitad de una tarea que el propietario está dictando; intervención repetida del mismo
momento sin cambio de estado. Ante duda, calla.

## Costo de contexto

SKILL.md ≈ 1.8 K tokens al cargarse. Cada momento lee solo frontmatter y tablas de
nodos (≈ 200 tokens por plan) y comandos git/gh acotados con `--json` y `head`. Las
referencias (~1 K tokens cada una) se cargan bajo demanda. Presupuesto de salida al chat:
un bloque compacto por intervención, ≤ 3 intervenciones por sesión.
