---
id: "008"
slug: sec-heartbeat
layer: L1
status: implementado
last_reviewed: 2026-07-08
implemented:
  - ~/.claude/skills/sec-heartbeat/SKILL.md
  - ~/.claude/scheduled-tasks/sec-heartbeat/SKILL.md
  - $SECRETARY_INSTANCE/subsystem/heartbeat/
  - $SECRETARY_INSTANCE/canon/operational/routines/heartbeat-match-model.md
---

# Spec 008 — sec-heartbeat

**Estado:** `implementado` (de facto — latido en main, consumido por `pulse` y `secretary-briefing`)

Consolidador de **memoria de corto plazo** para estado operativo. `pulse` lee; `sec-heartbeat` escribe.

## Objetivo

Producir un estado compacto y fresco en `subsystem/heartbeat/` para:

- `secretary-briefing` (lectura enfocada en pre-brief).
- `pulse` (lectura de `latest.md` en cualquier momento).
- sesiones interactivas (narrativa breve sin re-escanear todo el sistema).

## Store

```
subsystem/heartbeat/
├── README.md
├── latest.md           # overwrite en cada latido (verdad actual)
└── YYYY-MM-DD.md       # log diario (append de cada latido)
```

### Semántica de escritura

- `latest.md` se **sobrescribe** en cada corrida.
- `YYYY-MM-DD.md` se **append** con una sección por latido (`## Latido HH:MM` + contenido).
- El heartbeat nunca escribe fuera de `subsystem/heartbeat/`.

## Cadencia oficial (America/Lima)

| Hora aprox. | Tipo | Uso principal |
|---|---|---|
| 07:10 | pre-brief | Fuente principal del briefing matutino |
| post-reuniones | hook | Tras exit 0 de `reuniones-update` (ventana laboral; no cron denso) |
| 22:10 | close | Cierre diurno (dream/pulse) |

Sin slots fijos q2h/q4h (`09:10`…`21:10`) ni `00:10` nocturno — wind-down/sesión y el hook post-reuniones cubren cambios materiales.

| Hora / disparo | Extractora | Nota |
|------|------------|------|
| poll `*/30` 08–21 | `reuniones-scheduler` | Sin LLM: calendario (fin 30–90m) → scout → opcional `reuniones-update` |
| 22:00 | `reuniones-update` | Catch-up fijo |
| pre-brief pipeline | `reuniones-update` | Solo si `need_reuniones` |
| 18:00 | `revision-correo` | Batch vespertino |

## Lectura por consumidor

- **briefing**: prioriza el latido pre-brief (07:10). Si no existe, usa el más reciente con timestamp `<= 07:45`.
- **pulse**: usa `latest.md` en cualquier momento; **prioriza filas `loose-*` del match** para rampa de arranque (ver § Contrato pulse).
- **wind-down** y **sec-merge**: invocan `sec-heartbeat` inmediatamente tras cambios materiales para no cerrar con estado stale.

## Inputs mínimos

- `extractores/*/memory/` y `acciones.md`
- `extractores/correo/estado.md` (puede ser del batch vespertino 18:00 — ver § Frescura)
- `subsystem/wip/`
- Issue de briefing abierto + comentarios `sec-status`
- estado git/PRs: `gh pr list` + scan de ramas/worktrees/dirty por repo (allowlist + workspaces de acc abiertas)
- **Calendario** (solo lectura): eventos hoy ±1 día vía `gog calendar` (cuenta personal; work account si `gog` la tiene registrada). Barrer **todos** los calendarios accesibles, no solo primary.
- **Frescura de extractoras** (§ Frescura) y **conflictos multi-fuente** (§ Conflictos)

## Frescura de extractoras

Bloque estructurado en `## Frescura extractoras` del latido. Generación determinística:
`$SECRETARY_INSTANCE/scripts/routines/extractor-freshness.sh` (invocado por `run.sh` antes del agente;
copiar salida verbatim). En sesión interactiva, ejecutar el script manualmente.

Antes del match, registrar en **Notas operativas** solo flags adicionales (gaps del script, ventana Tactiq):

| Extractora | Señal de última corrida |
|------------|-------------------------|
| `reuniones-update` | Log más reciente en `subsystem/routines/latest-reuniones-update.log` (o `runs/`) **o** PR `reuniones/auto-*` del día (abierto/mergeado) |
| `revision-correo` | Log `revision-correo-*.log` **o** PR `correo/auto-*` más reciente (esperado ~18:00 Lima) |
| `drive-crawler` | Log `drive-*` o PR `drive/auto-*` |
| `wiki-update` | PR `wiki/auto-*` o timestamp en `memoria/wiki/output/` en main |

Si la última corrida de reuniones es **>3h** antes del slot actual y hubo eventos de calendario en ese intervalo sin PR reuniones posterior → flag `⚠️ reunión sin procesar (ventana Tactiq)`.

PRs extractor **abiertos sin merge** del día: listar en Frescura (el latido lee `acciones.md` en main; el PR puede tener updates más nuevos).

## Conflictos multi-fuente

Cruzar para entidades activas en acciones abiertas o brief del día:

| Par de fuentes | Acción |
|----------------|--------|
| `correo/estado.md` vs `extractores/reuniones/resumenes/*.md` reciente | Si fechas/hechos difieren (ej. evento “mañana” vs reunión “hoy 14:30”) → flag en Notas operativas con ambas citas |
| `acciones.md` vs calendario | Si acc de scheduling sin evento y brief ya dudó → no elevar a pendiente humano sin micro-pregunta |
| `acciones.md` vs comentarios `sec-status` en brief | `sec-status` **gana** para estado (✅/🔄/⏳) |

No resolver conflictos automáticamente — documentar para briefing/pulse/humano.

## Lógica mínima por corrida

1. Ingesta desde `origin/main` + estado operativo local.
2. **Match acc↔git:** cruza cada `acc-*` abierta/en-curso contra PRs abiertos/recientes, ramas locales y dirty trees; clasifica cada fila (ver § Tabla Match).
3. Delta contra el latido anterior (nuevos cambios, cierres, regresiones).
4. Persistencia: overwrite `latest.md` + append en `YYYY-MM-DD.md`.
5. Si es invocación en sesión, responder con narrativa corta del cambio desde el último latido.

## Tabla Match acc↔git

Doctrina detallada: ``heartbeat-match-model.md`` (instance path).

### Columnas

```
acc-id | título | repo | ref | estado | evidencia | match | nota
```

| Columna | Descripción |
|---------|-------------|
| `acc-id` | Identificador de acción o `—` si la fila es solo git |
| `título` | Nombre legible de la fila: campo `accion:` de `acciones.md` (filas `acc-*`); título del PR vía `gh pr view` (filas `loose-git`); descripción corta (filas informativas). Truncar a ~80 caracteres en tabla; texto completo puede ir en `nota` si hace falta |
| `repo` | Slug del repo (`<project-repo>`, `secretary-core`, …); `owner/repo` solo si ambiguo |
| `ref` | Rama (`feat/x`), `PR #N` (+ estado: open/merged/draft), o `—` |
| `estado` | Estado de la acción (ver § Iconografía) o `—` para filas git-only |
| `evidencia` | Fuente concreta con **path relativo** desde raíz del repo (ver § Evidencia) |
| `match` | Clasificación del emparejamiento con prefijo visual (ver § Iconografía) |
| `nota` | Contexto accionable en una línea |

### Iconografía (columnas enum)

Prefijos visuales **estables** en celdas de `match` y `estado`. El valor canónico sigue siendo el texto
después del emoji (`linked`, `loose-acc`, …); consumidores pueden matchear por sufijo o ignorar el prefijo.

**`match`**

| Icono | Valor | Condición | Uso |
|-------|-------|-----------|-----|
| 🔗 | `linked` | `acc-id` **y** `ref` conectados al mismo frente | Ya trazado; briefing lo refleja en Trabajo en marcha |
| 📋 | `loose-acc` | Acción sin rama/PR/dirty asociado | **Suelto accionable** — pulse puede proponer draft PR o hidratación |
| 🌿 | `loose-git` | Rama/PR/dirty sin `acc-id` | **Suelto git** — pulse puede sugerir vincular o crear acc |
| · | `—` | Fila informativa (p. ej. merge reciente sin acc pendiente) | Solo narrativa/delta |

**`estado`** (opcional; omitir en filas git-only)

| Icono | Valor |
|-------|-------|
| ○ | `abierta` |
| 🔄 | `en-curso` |
| ✅ | `hecha` |
| ⏳ | `caducada` |

**Leyenda en `latest.md`:** bloque compacto inmediatamente bajo la tabla Match:

```markdown
**Leyenda:** match — 🔗 linked · 📋 loose-acc · 🌿 loose-git · · informativo · estado — ○ abierta · 🔄 en-curso · ✅ hecha · ⏳ caducada
```

### Evidencia (paths)

La columna `evidencia` nunca usa nombres genéricos (`acciones.md` solo). Siempre la ruta relativa
desde la raíz de `.secretary/` o el identificador externo con contexto:

| Tipo | Formato ejemplo |
|------|-----------------|
| acc-id | `extractores/reuniones/memory/acciones.md` — resolver grep del `acc-id` en `extractores/*/memory/acciones.md` |
| acc + PR | `extractores/reuniones/memory/acciones.md + gh pr view` |
| update/resumen | `extractores/reuniones/resumenes/YYYY-MM-DD-….md` (campo `origen` del update) |
| brief | `brief #N (issue)` |
| gh barrido | `gh pr list (<repo-slug>)` o `gh pr view (<owner/repo>#N)` |

**Huérfanos** (sección separada): resumen agregado de filas `loose-acc` y `loose-git` — no duplica la tabla, sintetiza lo accionable.

## Contrato pulse (consumo de loose work)

`pulse` lee `latest.md` **después** del brief y **antes** del barrido git ad-hoc:

1. Extrae filas con `match ∈ {loose-acc, loose-git}` (ignorar prefijo emoji si presente).
2. **`loose-acc`:** ofrece rampa — (a) hidratación estratégica (contexto Cowork + acc), (b) path a draft PR si el compromiso es código/docs en repo allowlist.
3. **`loose-git`:** ofrece rampa — (a) vincular a acc existente, (b) crear issue/dispatch si califica (sin ejecutar).
4. **`linked`:** no entra a rampa salvo que el operador lo pida; ya está en Trabajo en marcha del brief.
5. Si heartbeat ausente o stale (`> 6h` sin pre-brief/close/post-reuniones), pulse cae al barrido git manual (comportamiento legacy).

## Autonomía del briefing (secretary-briefing)

El briefing puede **adelantar** trabajo cuando hay inputs suficientes. Tiers de riesgo creciente:

| Tier | Qué puede hacer | Gate | Ejemplos |
|------|-----------------|------|----------|
| **0 — ambient** | Lectura, reconciliación, carry-over | Ninguno | Cerrar brief anterior, reconciliar correo/calendario |
| **1 — borradores** | Preparar borradores de email **sin enviar** | 🚧 envío explícito | Reply drafts en PR `correo/auto-*`; loose-acc de seguimiento correo |
| **2 — artefactos** | Crear/editar docs, borradores Drive, links listos en borrador | Sin envío ni mutación Drive remota | Propuesta en PR, deck borrador, email con links preparados |
| **3 — proceso** | Completar flujo multi-paso (correo + Drive + issue) | 🚧 compuerta por ítem | Responder hilo con adjuntos ya validados; dispatch a ejecutor |
| **4 — estratégico** | Decisión de negocio, contra-oferta, envío a tercero | 🚧 siempre humano | Pricing ERP, envío a Juliana/Roger, merge de PRs tier alto |

**Reglas:**

- Tier ≤ 1: autonomía plena en corrida matutina.
- Tier 2: autonomía si inputs completos en heartbeat/correo/acc; resultado en **🤖 Secretary — despacho y entregas** (`Tipo: entregado`).
- Tier ≥ 3: solo preparar y señalar 🚧; nunca enviar/mutar sin OK.
- Filas `loose-acc` del heartbeat pre-brief son **candidatos tier 1–2** si el tipo de acción y las fuentes lo permiten.
- Filas `loose-git` evalúan despacho (Fase 2.6) o vinculación a acc antes de autonomía.

## Plantilla esperada de `latest.md`

Secciones fijas:

1. `# Heartbeat` (timestamp, tipo de slot, fuente)
2. `## Match acc↔git` — tabla con columnas de § Tabla Match + leyenda de § Iconografía
3. `## Delta vs latido previo`
4. `## Huérfanos` — resumen de `loose-acc` + `loose-git` (conteo + top accionables)
5. `## Pendiente humano`
6. `## Notas operativas`

## Límites y no-objetivos

- No cierra ni muta acciones automáticamente (spec 007 + `sec-status` sigue siendo la fuente de confirmación humana).
- No escribe wiki ni promueve conocimiento durable; esa promoción sigue en `wiki-update`.
- No envía mensajes a terceros.

## Política main (latido vivo)

El heartbeat es **memoria de corto plazo siempre viva**: `pulse`, `secretary-briefing` y las rutinas leen
`$SECRETARY_INSTANCE/subsystem/heartbeat/` por path en el árbol **main** del checkout principal. No puede
quedar atrás en un PR abierto.

### Reglas

| Regla | Detalle |
|-------|---------|
| **Write path** | Solo `main`. Rutina programada **y** invocación en sesión: `commit` + `push` directo a `origin/main`. Sin PR, sin worktree de entrega. |
| **Excepción worktree** | El resto del repo sigue la disciplina de worktree para trabajo en rama; `subsystem/heartbeat/` es la excepción explícita — escribe en el checkout principal (`$SECRETARY_INSTANCE`). |
| **Tier** | **Ambient (tier 0).** Auto-merge implícito: no compuerta humana, no `sec-merge`, no babysit de latido. |
| **Scope de commit** | Solo `subsystem/heartbeat/` por corrida. Mensaje: `chore(heartbeat): latido YYYY-MM-DD HH:MM` o variante `docs(heartbeat): …` si el latido documenta un merge reciente. |
| **Pre-escritura** | `git fetch origin main` + `git pull --rebase origin main` en `$SECRETARY_INSTANCE` antes de escribir. Si el árbol local no está en `main`, abortar o reconciliar — no latir desde una rama de feature. |
| **Conflictos** | Si un PR en curso tocó `subsystem/heartbeat/`, el latido en main **gana** en `latest.md` (overwrite). El log diario (`YYYY-MM-DD.md`) hace append; en conflicto de merge, resolver conservando ambos bloques `## Latido …` en orden cronológico. Los PRs de otros hilos **no deben** incluir cambios de heartbeat — si aparecen, quitarlos del diff del PR. |
| **Concurrencia** | Scheduled + sesión pueden solaparse: último push gana en `latest.md`; el diario acumula todos los latidos. Aceptable — el objetivo es frescura, no serialización estricta. |

### Consumidores

- **`pulse`:** lee `latest.md` del path vivo (`$SECRETARY_INSTANCE/…`), no `git show` de una rama de sesión.
- **`wind-down` / `sec-merge`:** tras cambios materiales, invocan `sec-heartbeat` y **deben** dejar el latido commiteado y pusheado a main antes de cerrar (no opcional).
- **CI en push a main:** `validate_wikilinks`, `validate_paths`, `validate_ordenamiento` — el latido no introduce wikilinks; pasa CI por construcción si solo toca `subsystem/heartbeat/`.

### Alternativas descartadas

- **PR por latido:** overhead desproporcionado (~9/día); deja a consumidores con estado stale.
- **Gitignore de heartbeat:** pierde historial intradía y trazabilidad del match.

## Artefactos

- Skill interactivo: `~/.claude/skills/sec-heartbeat/SKILL.md`
- Rutina programada: `~/.claude/scheduled-tasks/sec-heartbeat/SKILL.md`
- Doctrina match: `canon/operational/routines/heartbeat-match-model.md`
