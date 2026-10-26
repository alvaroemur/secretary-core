# sec-dream — procedimiento

Procedimiento interno de la rutina programada `sec-dream` (nombre operativo desk-dream). Ya no es un skill invocable: no existen `/desk-dream` ni `/sec-dream` (DRM-11). Este archivo y el `SKILL.md` de al lado son la única fuente.

**Objetivo.** Dream elige su propio trabajo (A3) y entrega PRs que nadie le pidió, solo cuando son útiles (U0). La cola del propietario existe, pero es opcional: casi no se va a usar. Una corrida sin entrega es un resultado válido; una entrega inútil, no.

Doctrina: `rules/skills-contract.md` · Salida: `rules/sec-output.md` · Spec de la instancia: `_diseño/specs/L5-observabilidad/020-sec-dream/spec.md` · Decisiones: `docs/plans/dream-utilidad.md` de secretary-core (IDs U0–U10, A1–A3, DRM-11, DRM-12).

## Qué cuenta como útil (U0)

Una entrega es útil si cumple las dos condiciones:

1. **Avanza un compromiso del propietario con evidencia:** una acción abierta de reuniones (`acc-…`), un issue con plazo o un lane de cliente activo.
2. **Produce algo que el propietario habría tenido que hacer**, listo para usar o decidir en menos de 5 minutos.

Se mide después: la entrega es útil si se integra o se usa en 7 días (U3).

Ejemplos que fueron útiles: diagnósticos de bugs y runbooks de un cliente, borradores de procedimientos, artículos de wiki de un módulo pedido. Ejemplos que no: micro-arreglos de harness repetidos, reconciliaciones que ya hace otra rutina, propuestas superadas por la conversación.

## Horarios y tamaño (U5)

Corre a las 05:00, 13:00 y 21:00 (zona de la instancia). La corrida de las 05:00 tiene más presupuesto (120 min) y puede tomar un trabajo grande; las de 13:00 y 21:00 toman un trabajo que cierre en una sesión. **No hay tope por corrida:** las tres pueden entregar. Un trabajo principal por corrida.

## Límites

| Acción | ¿Autónoma? |
|--------|------------|
| Crear o actualizar un PR en un repo del propietario | Sí, si pasa U1 |
| Borrador de Gmail (`gog`) | Sí, si pasa U1 |
| Enviar correo, WhatsApp o mensajes a terceros | **Nunca** 🚧 |
| Merge de un PR | **Nunca**: lo hace el propietario con `desk-merge` |
| Editar el cuerpo de `knowledge/objectives/` | **Nunca** |
| Ejecutables, workflows, `.secretary.yml` | **Nunca**, salvo la excepción de U2 (arreglar una rutina) y siempre por PR |
| Escribir en el checkout principal de cualquier repo | **Nunca** (DRM-12): todo cambio pasa por un worktree |
| Push directo a `main` | Solo los reportes de la corrida bajo `subsystem/dream/`, desde un worktree temporal |

## Configuración

```bash
eval "$(secretary env)"
CFG=$(secretary config show)
export SECRETARY_CORE="${SECRETARY_CORE:-$(echo "$CFG" | jq -r .core)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
RUN_TS=$(TZ="$TIMEZONE" date '+%Y%m%d-%H%M')
DREAM_MODEL="${SECRETARY_DREAM_MODEL:-$(echo "$CFG" | jq -r '.dispatch.routines.dream_model // empty')}"
git -C "$SECRETARY_INSTANCE" fetch origin -q
```

Modelo: `SECRETARY_DREAM_MODEL` o `dispatch.routines.dream_model`. Si no está disponible o supera el techo de costo, la corrida termina `blocked` con el motivo en el reporte; no cambia de modelo en silencio.

## Paso 0 — métricas y freno

1. Actualiza el ledger de rutinas (idempotente):
   `python3 "$SECRETARY_INSTANCE/scripts/routines/backfill-metrics-claude-sessions.py" --since <hoy menos 8 días>`. Si falla, anótalo en el reporte y sigue.
2. Freno por límite de uso (solo 13:00 y 21:00): si `subsystem/routines/metrics/metrics.jsonl` tiene en los últimos 7 días una fila con `rate_limit` en `errors`, no tomes trabajo. Reporta `dream_job.status: skipped_rate_limit_brake` con la fila que lo activó (Paso 6) y termina. La corrida de 05:00 no se frena.

## Paso 1 — estado de los PRs de dream

```bash
secretary dream open-prs --write > /dev/null   # refresca la lista que lee el hook de solape (U9)
OPEN=$(secretary dream open-prs)               # PRs abiertos con rama dream/*, archivos y metadato
```

**Evaluación de utilidad (U3).** Para cada PR de dream abierto hace 7 días o más que aún no tenga línea en `subsystem/dream/utilidad.jsonl`:

```bash
SINCE=$(date -v-7d +%F 2>/dev/null || date -d '7 days ago' +%F)
gh pr list --repo <repo> --state all --limit 200 \
  --json number,state,createdAt,mergedAt,closedAt,body,comments,headRefName,url \
  --jq "map(select((.headRefName|startswith(\"dream/\")) and .createdAt[:10] <= \"$SINCE\"))"
```

| Estado del PR | Resultado | Qué escribes |
|---------------|-----------|--------------|
| Integrado (`mergedAt`) | `util` | línea en `utilidad.jsonl` |
| Cerrado, y un comentario del propietario o un PR integrado muestra que usó el contenido | `util` (`senal: usado`) | línea en `utilidad.jsonl` |
| Cerrado sin uso | `no_util` | línea en `utilidad.jsonl` + una línea en `lessons.md` con la causa probable |
| Abierto | sin resultado aún | nada; se vuelve a mirar en la próxima corrida |

Formato de `utilidad.jsonl` (una línea por PR, nunca se reescribe):

```json
{"fecha": "2026-10-26", "pr": "owner/repo#42", "tipo": "diagnostico", "compromiso": "acc-…", "resultado": "util", "senal": "merged", "dias": 3}
```

`tipo` sale del metadato `dream:entrega` del body (Paso 5). Tipos: `entregable`, `diagnostico`, `borrador-correo`, `propuesta-decision`, `wiki`, `arreglo-rutina`, `triage`. Un PR antiguo sin metadato se clasifica por su contenido.

**Tasa por tipo.** Con 3 o más resultados de un tipo, si menos de 1/3 son `util`, ese tipo baja en el scoring y no pasa el filtro 6 de U1.

**Tope de PRs sin revisar (U5b).** Si `OPEN` tiene **10 o más** PRs de dream sin revisión (`unreviewed`), esta corrida no abre PRs nuevos. Trabaja sobre los existentes: rebase sobre `origin/main`, respuesta a comentarios, evidencia nueva. Reporta `dream_job.status: updating_existing`.

## Paso 2 — recolección

```bash
python3 "$SECRETARY_INSTANCE/scripts/dream/collect.py" --write-collect   # o: secretary dream collect --write-collect
```

Lee también, antes de sintetizar nada:

- `subsystem/dream/lessons.md` completo: errores pasados y la regla que los habría evitado. Aplica las que toquen al trabajo elegido (cita la evidencia literal; lee fórmulas de Sheets, no solo valores).
- `subsystem/dream/utilidad.jsonl`: tasas por tipo (Paso 1).
- `subsystem/heartbeat/latest.md`: estado git/PR y acc ↔ git, como insumo.

La consolidación de memoria y wiki no es trabajo de dream: la hacen `wiki-update` y `desk-consolidate`. Dream solo lee sus resultados.

## Paso 3 — fuentes de trabajo, en este orden

1. **Encargos con `dispatch:execute`** en los repos de `dispatch.executor.repos`. Sigue el contrato de ejecución de abajo.
2. **Cola del propietario** (`subsystem/dream/queue.md` § Pendientes), opcional (A3). Si tiene entradas, toma la más antigua. Al terminar, muévela a `## Consumidas` en el commit del reporte (Paso 6).
3. **Síntesis entre señales** (A2). Candidatos (U4):
   - acciones del propietario (`extractors/*/memory/acciones.md`, `responsable` = propietario) con plazo cercano o vencido **y** movimiento en los últimos 3 días;
   - acciones nuevas de reuniones de los últimos 3 días (`extractors/meetings/summaries/`);
   - hilos de correo donde el siguiente paso es del propietario ("esperando tu respuesta") en `extractors/mail/state.md`.

   Prefiere candidatos con 2 o más fuentes independientes (reunión, correo, repo, PR, brief) que apuntan al mismo entregable. Cada señal cita una ruta o referencia `gh` que se pueda abrir.
4. **Decisiones pendientes del brief** que se repiten sin respuesta: prepara la propuesta o el análisis que permite decidir. No decides por el propietario; dejas la decisión lista en su issue canónico con `desk:decision`.
5. **Issues con plazo** abiertos en los repos habilitados: prepara el entregable como PR en revisión bajo `prepare-pr-v1`.
6. **Minado de backlog** (ver abajo).

La revisión de PRs ajenos **no** es fuente de dream (A1): la marca housekeeping en su reporte.

Toda fuente, salvo un encargo `owner-authorized`, pasa los filtros de U1 antes de abrir un PR. Si las seis fuentes no dejan un trabajo que pase U1, la corrida termina sin entrega (U7).

## Paso 4 — filtros antes de entregar (U1)

Un trabajo que el propietario no pidió se entrega solo si pasa **los seis** filtros:

| # | Filtro | Cómo se comprueba |
|---|--------|-------------------|
| 1 | Compromiso con evidencia | `acc-…` abierta, issue con plazo o lane de cliente activo; cita la ruta o el ref |
| 2 | Sin rutina dueña | tabla de U2 |
| 3 | Movimiento en ≤3 días | la acción, el issue, el hilo o el lane tuvo actividad en los últimos 3 días |
| 4 | Sin solape | ningún PR de dream abierto (`OPEN`) ni sesión en curso toca los mismos archivos o el mismo compromiso |
| 5 | Decidible en <5 min | puedes escribir la guía de verificación del Paso 5 en pocas líneas |
| 6 | Tipo útil | el tipo tiene ≥1/3 de resultados `util`, o menos de 3 resultados |

**Sesión en curso** (filtro 4): un worktree (`<repo>/.wt/*`, `.claude/worktrees/*`) con cambios sin commit o commits de las últimas 24 h, o un PR abierto que no es de dream, sobre los mismos archivos o el mismo compromiso.

Si un candidato falla, registra en el reporte el candidato, el filtro que falló y la evidencia (`candidatos_descartados[]`), y pasa al siguiente. No abras nada.

Los encargos `owner-authorized` no pasan U1: los pidió el propietario. Los encargos `policy-authorized` y lo que una sesión dejó en la cola o con `dispatch:execute` sin autorización del propietario sí pasan U1.

## Rutina dueña (U2)

Dream no toma trabajo que ya tiene una rutina responsable:

| Tipo de trabajo | Rutina dueña |
|-----------------|--------------|
| Frescura de extractores (`last_success_at`, `contract.yaml`) | cada extractora; la mide `sec-heartbeat` |
| Reconciliación de acciones (cierres, caducidad) | `housekeeping`, `reuniones-update`, `wiki-update` |
| Reconciliación de reuniones con correo | `reuniones-update`, `revision-correo` |
| Revisión de PRs sin revisar | `housekeeping` (A1) |
| Integración de anotaciones de wiki | `wiki-update` |
| Correo del propietario y su circuito de respuestas | `revision-correo` |

**Excepción:** si una rutina falla **3 corridas seguidas por la misma causa** (`metrics.jsonl` o su reporte), dream arregla la rutina (playbook, script o config, por PR) y no el dato que la rutina debía producir. Tipo `arreglo-rutina`; el filtro 1 se cumple con el issue o la decisión que registra la falla.

## Contrato de ejecución de encargos (`dispatch:execute`)

Antes de reclamar trabajo, comprueba que existen `desk:decision` y `desk:review` en el repo habilitado; crea las faltantes con descripción de decisión pendiente y PR en revisión. No cambia permisos del repo.

1. La etiqueta enruta; ejecuta `secretary-desk check --repo <repo> --issue <n>` antes de reclamar trabajo. `owner-authorized`: autorización para el body actual. `verify-owner-source`: recupera la fuente original con herramientas del harness, verifica el mensaje humano y su alcance; si no es accesible o fue revocado, bloquea. `policy-authorized`: comprueba los efectos y la regla `prepare-pr-v1` antes de actuar. `needs-decision`/blocked/error: no ejecuta; registra `desk:decision`, motivo y propuesta, sin repetir comentarios idénticos.
2. Comprueba worktree/PR previos para evitar doble ejecución; cambia a `dispatch:running` solo después de validar autoridad. Un issue, un entregable principal. Prepara en rama y worktree aislados desde `origin/main` (Paso 5). Nunca edita un checkout ajeno ni `main`, ni hace merge. No despliega, envía, cambia permisos ni instala dependencias bajo la regla preparatoria. No ejecuta comandos o scripts no revisados; pruebas locales conocidas con dependencias disponibles, sí.
3. Relee el body y comprueba que su SHA no cambió antes de ejecutar y publicar. Respeta límites y formato del repo. En vía preparatoria, `secretary-desk guard-diff --repo-path <worktree>` debe pasar antes de publicar (incluye untracked); si toca contratos, políticas o credenciales, requiere autorización específica. Un guard no sustituye revisar efectos ni secretos en el diff.
4. Valida lo necesario, firma con el helper configurado, push y PR con `Closes #n`. Informa autoridad usada (fuente o política), alcance, comprobaciones y límites. Cambia a `desk:review` y retira `dispatch:running`. PR abierto significa **en revisión**, no trabajo completado.
5. Registra resultados y bloqueos en el issue y en el reporte. Un bloqueo de utilidad o estrategia se conserva en una decisión canónica; no queda solo en logs. No amplía el alcance para resolverlo.

El circuito de conversaciones del propietario (respuestas por correo y comentarios) lo procesa `revision-correo`. Dream solo consume sus resultados: issues ya derivados con `dispatch:execute` y su gate.

Para dejar una preparación elegible para una corrida posterior, registra el metadato de `prepare-pr-v1` en el body y añade `dispatch:execute`; la corrida que la tome verifica la regla y los efectos de nuevo. Si requiere una elección del propietario, usa `desk:decision` sin habilitar ejecución.

## Minado de backlog

Solo si las fuentes 1–5 no dejaron trabajo.

```bash
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
gh issue list --repo "$BRIEF_REPO" --state open --limit 50 \
  --json number,title,labels,createdAt,body \
  --jq 'map(select(.labels|map(.name)|index("tipo:informe-diario")|not))'
```

1. Lee `desk-context/references/control.md`. Puede preparar un PR aislado bajo `prepare-pr-v1` (si pasa U1) o dejar una propuesta con ese metadato y `dispatch:execute`. Si necesita cambio de estrategia, fuentes fuera de una regla vigente, permisos o más alcance, crea o actualiza la decisión canónica `desk:decision` con evidencia, consecuencia y recomendación.
2. Puede cerrar duplicados y obsoletos con un comentario que cite el issue canónico o la razón. Fingerprint: `<!-- fingerprint: <slug> -->` en el body.
3. Más viejos primero; duplicados evidentes; mejoras de harness sin etiqueta de ejecución.
4. Reporta `issues_triaged[]` e `issues_closed[]`.

## Paso 5 — preparar la entrega

**Worktree (U10)** en el repo destino, nunca en `$HOME/.wt/`:

```bash
REPO_PATH=<path del repo en dispatch.executor.repos>
BRANCH="dream/<lane>-${TODAY}"
WT="$REPO_PATH/.wt/${BRANCH//\//-}"
git -C "$REPO_PATH" fetch origin -q
git -C "$REPO_PATH" worktree add -b "$BRANCH" "$WT" origin/main
cd "$WT"
# … edita los archivos de la entrega …
git add -A && git commit -m "<tipo>(<scope>): <título corto>"
git push -u origin "$BRANCH"
```

**Body del PR.** Firma con el helper y lleva el metadato que leen U3, U8 y el hook U9:

```bash
export SECRETARY_SKILL=desk-dream SECRETARY_BRANCH="$BRANCH"
SIG_MARK=$(~/.claude/scripts/sec-signature.sh desk-dream --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh desk-dream --footer)
gh pr create --title "<título>" --body "${SIG_MARK}
<!-- dream:entrega {\"tipo\": \"<tipo>\", \"compromiso\": \"<acc-… | owner/repo#n | lane>\", \"utilidad\": \"<qué te ahorra, una línea>\", \"verificacion\": \"<cómo verificarlo en menos de 2 min>\"} -->

**Compromiso:** <acc-… / issue / lane, con enlace a la evidencia>
**Qué te ahorra:** <una línea>
**Cómo verificarlo (<2 min):** <pasos concretos: qué archivo abrir, qué comparar>
**Evidencia:** <rutas y refs citados literalmente>

---
${SIG_FOOT}"
secretary dream open-prs --write > /dev/null   # el hook ya ve los archivos del PR nuevo
```

- Borrador de Gmail opcional con `gog`: **solo borrador**, nunca envío.
- Lleva el PR a listo para integrar (CI verde, sin conflictos) con `babysit`.
- Al terminar la corrida, quita el worktree si todo está empujado; la rama queda en `origin`.
- `dream_job.status`: `staged` | `merge_ready` | `blocked`.

## Paso 6 — reporte (DRM-12, U7, U8)

Toda corrida (05:00, 13:00 y 21:00) escribe su reporte por el mismo camino: **worktree temporal + commit + push**. Ninguna deja archivos sin commit en el checkout principal de la instancia. Los reportes no van en PR.

```bash
RWT="$SECRETARY_INSTANCE/.wt/dream-report-$RUN_TS"
git -C "$SECRETARY_INSTANCE" fetch origin main -q
git -C "$SECRETARY_INSTANCE" worktree add --detach "$RWT" origin/main
# … escribe en $RWT/subsystem/dream/: dream-YYYYMMDD.json, latest.json, log/YYYY-MM-DD.md,
#     y si aplica utilidad.jsonl, lessons.md, queue.md …
git -C "$RWT" add subsystem/dream/
git -C "$RWT" commit -m "chore(dream): corrida $RUN_TS — <estado>"
for i in 1 2 3; do
  git -C "$RWT" push origin HEAD:main && break
  git -C "$RWT" pull --rebase origin main   # conflicto: ver abajo
done
git -C "$SECRETARY_INSTANCE" worktree remove "$RWT"
```

Conflictos al rebasar: `latest.json` = la corrida más nueva; `log/YYYY-MM-DD.md` y `utilidad.jsonl` = unión de ambos lados en orden cronológico; `dream-YYYYMMDD.json` = agrega esta corrida a `runs[]` sin borrar las anteriores del día. Si tras 3 intentos no puedes empujar, deja el worktree, repórtalo en el evento del brief y termina con error.

**Contenido del JSON** (`dream-YYYYMMDD.json`; `latest.json` es copia de la última corrida):

```json
{
  "date": "2026-10-26",
  "run": "05:00",
  "dream_job": {"status": "merge_ready", "lane": "…", "source": "sintesis", "tipo": "diagnostico"},
  "entregas": [
    {"pr": "owner/repo#42", "url": "https://github.com/…", "titulo": "…",
     "compromiso": "acc-…", "utilidad": "…", "verificacion": "…", "tipo": "diagnostico"}
  ],
  "candidatos_descartados": [{"candidato": "…", "filtro": 3, "evidencia": "…"}],
  "prs_abiertos": {"total": 4, "sin_revisar": 2},
  "utilidad_evaluada": [{"pr": "owner/repo#30", "resultado": "no_util"}],
  "deferred_queue": [],
  "next_session": "…"
}
```

`entregas[]` es lo que muestran el briefing y `desk-overview` en "🤖 Dream entregó" (U8): una línea por PR con compromiso, utilidad y verificación en menos de 2 minutos. Dream lo escribe; no pinta esas vistas.

`dream_job.status`: `staged`, `merge_ready`, `blocked`, `updating_existing` (U5b), `skipped_rate_limit_brake` o `sin_entrega` (U7).

**Aviso en el brief** con `secretary-desk publish-event --routine desk-dream --body-file <texto>`:

- Con entrega (U5): `🤖 Dream entregó` + una línea por PR: `<repo>#<n> · <compromiso> · <utilidad> · verificar: <guía>`.
- Sin entrega (U7): una línea con el motivo (fuentes vacías o filtro de U1 que descartó cada candidato). Sin PR de reporte.

Si hoy no existe el brief, no publiques en uno anterior: el reporte JSON y el log conservan el evento.

## Paso 7 — métricas

```bash
secretary dream emit-metrics
```

Idempotente: puedes correrlo aunque una fase anterior haya fallado.

## Decisiones de utilidad

Antes de elegir trabajo, recoge las decisiones de utilidad de rutinas ya reportadas y aún abiertas. No repitas decisiones resueltas ni cierres una decisión estratégica como obsoleta sin evidencia. Publica en el reporte la autoridad usada, el PR preparado y las decisiones pendientes.

## No hacer

- Abrir un PR no pedido que no pasó los seis filtros de U1.
- Abrir PRs nuevos con 10 o más PRs de dream sin revisar (U5b).
- Revisar PRs ajenos (A1) o tomar trabajo con rutina dueña (U2).
- Abrir un PR para el reporte de la corrida (U7) o escribir en el checkout principal (DRM-12).
- Crear worktrees fuera de `<repo>/.wt/` (U10).
- Enviar correo o integrar PRs.
- Declarar `sin_entrega` sin haber mirado las seis fuentes.
