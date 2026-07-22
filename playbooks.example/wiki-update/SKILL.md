---
name: wiki-update
description: Actualizar la wiki desde las distintas fuentes disponibles
---

---
name: sync-wiki
description: Recolecta información de todas las fuentes conectadas (correo, reuniones, calendario, drive, job-search) y actualiza la wiki personal en secretary/knowledge/wiki/. Úsalo cuando el usuario pida "sincronizar la wiki", "actualizar la wiki", cuando una tarea programada lo invoque, o cuando haya que reconciliar la wiki con las fuentes tras cambios en cualquiera de ellas.
---

# sync-wiki — Sincronizador de la wiki personal

La wiki personal vive en `secretary/knowledge/wiki/`. Es el **destino de agregación**: las fuentes no viven aquí, sino que cada una tiene su propio pipeline/app que deja datos en lugares conocidos. Este skill recorre esos lugares, consolida la información en artículos Markdown bajo `articulos/`, y regenera el HTML.

Lee `secretary/knowledge/wiki/README.md` antes de modificar nada para respetar el contrato de escritura (frontmatter, wikilinks, registro de cambios).

## W0. Mergear PRs pendientes de extractores y de la wiki anterior (ANTES del worktree)

`wiki-update` es el cierre del día y el **auto-merger central** de las rutinas automáticas. Mergea a `main`: (1) los PRs de los extractores que alimentan la wiki (correo / reuniones / whatsapp) **y el PR de wiki de la corrida anterior** (`wiki/auto-*`), para que la evidencia se integre **en esta misma corrida** (sin lag de un día) y los PRs de wiki **no se le acumulen a Álvaro**; y (2) los PRs de las rutinas que **no** alimentan la wiki pero igual deben llegar a `main` sin apilarse (housekeeping / job-search / drive). Para estas últimas el merge sólo **sincroniza `main` / limpia el backlog** — no integran nada a la wiki —, pero pasan por el mismo gate de comentarios, así que Álvaro conserva la ventana para frenar un cambio con un comentario antes del cierre del día.

> **Rutinas que encadenan (job-search, drive).** Ambas mantienen **un único** PR auto abierto que engordan corrida a corrida (reemplazan al anterior). En el caso normal hay 1 abierto y se mergea como cualquier candidato. Si por algún motivo hay **más de uno** abierto del mismo prefijo, mergear **sólo el más reciente** (mayor timestamp en la rama) y **cerrar** los `…/auto-*` más viejos con un comentario (`> 🤖 **wiki-update**` — "superado por #N, cierro para evitar conflicto"). housekeeping NO encadena: cada corrida abre un PR independiente y todos son candidatos (el loop los mergea en orden; si alguno choca, va a `$NO_MERGE` y queda abierto, no es fatal).

**Gate estricto — solo PRs de agentes automáticos.** El único criterio es que la rama matchee EXACTAMENTE el patrón que generan las rutinas: `^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$`. En W0 nunca existe todavía el PR de wiki de *esta* corrida (se crea recién en el Paso 7.5), así que `wiki/auto-*` sólo matchea el de la corrida anterior. Cualquier otra cosa NO se mergea: PRs que Álvaro trabaja a mano (reuniones históricas / backfill, fixes, consolidaciones, PRs de wiki con otro nombre, etc.), o cualquier rama que no calce el patrón. Ante la mínima duda, no mergear.

**Antes de mergear hay que revisar comentarios sin resolver.** Un PR auto puede tener feedback de Álvaro (ej. "renombrá esto", "corregí ese dato"). NO se mergea a ciegas: primero se atiende el comentario; si no se puede atender con seguridad, se deja abierto para Álvaro. Mergear pisando un comentario sin resolver pierde su feedback — eso no debe pasar.

**Paso 1 — listar candidatos** (ramas auto; nada manual matchea el patrón):

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
OWNER=$(gh repo view --json owner -q .owner.login); NAME=$(gh repo view --json name -q .name)
CANDIDATES=$(gh pr list --state open --json number,headRefName \
    --jq '.[] | select(.headRefName | test("^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$")) | .number')
echo "Candidatos: ${CANDIDATES:- ninguno}"
```

**Paso 2 — por cada `$N` en `$CANDIDATES`, revisar comentarios ANTES de decidir.** Trae los dos tipos (inline con estado resolved/unresolved + hilo general):

```bash
# Threads inline y si están resueltos:
gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{isResolved comments(first:20){nodes{path line body author{login}}}}}}}}' -F o="$OWNER" -F r="$NAME" -F n="$N"
# Comentarios del hilo general del PR:
gh api "repos/$OWNER/$NAME/issues/$N/comments" --jq '.[] | {author: .user.login, body: .body}'
```

Clasifica el PR:
- **Sin comentarios sin resolver** (no hay `reviewThreads` con `isResolved:false`, ni comentarios del hilo general que pidan un cambio aún no aplicado) → **mergear con SQUASH**: `gh pr merge "$N" --squash --delete-branch`. **El repo NO permite merge commits** (`--merge` falla con "Merge commits are not allowed on this repository" — aprendizaje 2026-06-12); usar siempre `--squash`. Suma a `$MERGED`.
- **Con comentarios sin resolver** → NO mergear todavía. Para cada comentario:
  - Si el pedido es **claro y acotado** (renombrar, corregir un dato, ajustar un campo): hacer checkout de la rama del PR en un worktree temporal, **aplicar el cambio**, commit (`fix(<scope>): atiende comentario PR #$N — <qué>`) y push. Cuando TODOS los comentarios del PR queden atendidos: resolver el/los review thread(s) (GraphQL `resolveReviewThread`) o responder al comentario indicando qué se hizo, y entonces mergear. Suma a `$MERGED` con nota "(comentarios aplicados)".
  - Si el pedido es **ambiguo, amplio, requiere criterio o toca muchos archivos**: NO adivinar, NO mergear. Dejar el PR abierto y sumarlo a `$NEEDS_REVIEW` con una línea de qué pide el comentario.
- **Conflicto/checks rojos al intentar mergear** → en general queda abierto, suma a `$NO_MERGE` (no es fatal). **PERO** los PRs de `reuniones/auto-*` y `drive/auto-*` chocan de forma rutinaria contra el PR de wiki anterior (#wiki que flipeó `pendiente_wiki: true→false` mientras el extractor apiló items nuevos en el mismo `*/memory/*.md`). Ese conflicto es **trivial de resolver y vale la pena** porque la evidencia de reuniones alimenta la wiki esta misma corrida: checkout de la rama en worktree temporal, `git merge origin/main`, y en cada bloque conflictivo **conservar el flip-to-false de `origin/main`** (el item ya integrado) **+ todos los items nuevos del lado HEAD** (los enriquecimientos/acciones del extractor). Commit, push, `gh pr merge --squash`. Aprendizaje 2026-06-12: así se rescataron #243 (reuniones) y #244 (drive) que habrían quedado sin integrar.

**Aprendizaje 2026-07-15 — overlapping `reuniones/auto-*`:** si mergeás varios PRs de reuniones el mismo día, el árbol conflictivo puede **truncar bloques `acc-*` a mitad de línea** y empalmar campos Alma↔ERP (p.ej. `acc-20260715-001` con título Alma pero `contexto:` de erp-clab). Tras resolver markers, **re-validá** los `## acc-YYYYMMDD-*` nuevos contra el **primer commit del PR** (`gh pr view N --json commits` → `git show <oid>:extractors/meetings/memory/acciones.md`) y reemplazá bloques corruptos antes de integrar a la wiki. No confíes sólo en el resultado del merge-file heurístico.


**Regla de oro:** ante la mínima duda sobre qué pide un comentario, **no mergear** — dejarlo en `$NEEDS_REVIEW` para Álvaro. Es preferible que un PR espere a que se aplique mal un cambio.

Guarda `$MERGED`, `$NO_MERGE` y `$NEEDS_REVIEW` para el reporte (Paso 7). Si un PR queda sin mergear, su evidencia simplemente no se integra esta corrida; no es un error fatal.

### Firma en comentarios de GitHub

Todos los comentarios que wiki-update deje en GitHub (respuestas a feedback, confirmaciones, reportes de acción tomada) deben llevar este header al inicio:

```
> 🤖 **wiki-update**
```

Esto permite distinguir respuestas del agente de comentarios de Álvaro. La firma va en **todos** los comentarios, sin excepción.

### Regla de respuesta obligatoria

Cada comentario detectado en un PR (sea review thread o comentario general) **debe recibir respuesta en GitHub**, haya sido atendido o no. Opciones:

- Atendido → responder con qué se hizo y en qué commit.
- No atendible esta corrida (ambiguo, requiere criterio) → responder explicando por qué queda para Álvaro.
- Ya obsoleto o no aplica → responder indicando por qué se considera resuelto.

Nunca dejar un comentario sin respuesta. Si Álvaro ve un comentario sin reply del agente, es un bug.

### Paso 2.5 — Revisar comentarios en PRs auto ya mergeados/cerrados (últimos 7 días)

**Por qué.** Álvaro puede mergear un PR él mismo y luego dejar un comentario de feedback. Ese feedback se pierde si solo miramos PRs abiertos. Este paso barre PRs auto recientes que ya se cerraron para capturar ese feedback.

```bash
# PRs auto mergeados/cerrados en los últimos 7 días (no abiertos, esos ya se cubrieron en Paso 1-2):
RECENT_CLOSED=$(gh pr list --state merged --json number,headRefName,mergedAt \
    --jq "[.[] | select(.headRefName | test(\"^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$\")) | select(.mergedAt > (now - 7*86400 | strftime(\"%Y-%m-%dT%H:%M:%SZ\")))] | .[].number")
# Añadir cerrados sin merge (si hubiera):
RECENT_CLOSED="$RECENT_CLOSED $(gh pr list --state closed --json number,headRefName,closedAt \
    --jq "[.[] | select(.headRefName | test(\"^(correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$\")) | select(.closedAt > (now - 7*86400 | strftime(\"%Y-%m-%dT%H:%M:%SZ\")))] | .[].number" 2>/dev/null)"
echo "PRs cerrados recientes a revisar: ${RECENT_CLOSED:- ninguno}"
```

Para cada `$N` en `$RECENT_CLOSED`:
1. Traer review threads no resueltos y comentarios generales (misma query GraphQL + REST del Paso 2).
2. Filtrar solo comentarios **sin respuesta del agente** (no tienen `🤖 **wiki-update**` en replies del mismo thread).
3. Para cada comentario sin respuesta:
   - Si pide un cambio **claro y acotado**: aplicarlo en el worktree de esta corrida (ya que el PR está mergeado, el cambio entra como parte del diff de wiki-update). Responder en GitHub con qué se hizo.
   - Si es **feedback general, ambiguo o ya no aplica**: responder en GitHub reconociendo el feedback y explicando qué se hizo (o por qué no aplica). Registrar en `$FEEDBACK_APPLIED`.
   - Si pide algo **amplio o que requiere criterio**: responder en GitHub indicando que queda para la próxima intervención manual. Registrar en `$NEEDS_REVIEW`.
4. Sumar `$FEEDBACK_APPLIED` al reporte (Paso 7) en una sección "Feedback de PRs cerrados".

**Paso 3 — Mapa de procedencia de los items de memory (para un reporte honesto)**

**Por qué.** En el Paso 1 integras el **estado consolidado** de `*/memory/` (todo item presente = pendiente de integrar), no sólo lo que aportaron los PRs auto de esta corrida. Eso es deseado: si Álvaro dejó trabajo real en `main` por fuera del pipeline (un commit/wave manual, un backfill, una consolidación a mano), igual debe integrarse. **Pero el reporte no debe atribuir ese trabajo a los PRs auto de la corrida.** Hay que distinguir "item nuevo de un extractor de hoy" de "item que ya estaba en `main` por otra vía". (Caso real: las 10 acciones de Nativas `acc-20260520-*` venían del commit manual `697071f` "wave may-2026"; el PR de reuniones de esa corrida integró **0 acciones** y aun así el reporte las reclamó como propias.)

Tras el merge (Paso 2), construí el mapa. `gh pr diff` funciona aunque el PR ya esté mergeado y la rama borrada:

```bash
PROV=/tmp/wiki-provenance.tsv
: > "$PROV"
for N in $MERGED; do
  gh pr diff "$N" 2>/dev/null | awk -v n="$N" '
    /^\+\+\+ b\// { f=$2; sub("^b/","",f) }
    /^\+## / && f ~ /memory\// { h=$0; sub(/^\+/,"",h); print f "\t" h "\tPR#" n }' >> "$PROV"
done
echo "Procedencia capturada: $(wc -l < "$PROV") items aportados por PRs auto."
```

Cada línea es `ruta-memory <TAB> "## header" <TAB> PR#N`. Regla para el Paso 1: cualquier item de memory que integres y **no** aparezca en `$PROV` es **pre-existente en `main`** (no vino de un PR auto de hoy). Para esos, sacá el commit de origen al reportarlos:

```bash
# F = ruta del archivo de memory; H = header exacto ("## acc-…" o "## Nombre")
git -C "$WT" log -1 --format='%h %s' -S "$H" -- "$F"
```

## W. WORKTREE AISLADO (hacer ANTES que nada)

Tras mergear, crea un worktree efímero desde `origin/main` (ya actualizado), **despliega el HTML de inmediato** y al final abre un PR que sirve de reporte.

```bash
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=wiki
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
git worktree add -b "$BRANCH" "$WT" origin/main
echo "WT=$WT  BRANCH=$BRANCH"
```

**Mapa de rutas:** donde el documento dice `secretary/...`, interprétalo como `$WT/...`. Todas las escrituras —artículos en `$WT/knowledge/wiki/`, la limpieza de consolidados integrados en `$WT/{mail,meetings,whatsapp}/memory/`, y el marcado de items de `$WT/extractors/drive/memory/` como `pendiente_wiki: false` (no se borran, ver sección 1.6)— van al worktree. Lees los consolidados de las fuentes desde `$WT/...`: como el worktree parte de `origin/main` **tras el merge del Paso W0**, ves la evidencia de los extractores que se acaba de mergear (sin lag). Lo único que no ves es lo de PRs que W0 no pudo mergear (conflicto/checks).

> Modelo: **PR + deploy inmediato.** El HTML se publica a Cloudflare en esta misma corrida (Paso 6.5) reflejando el contenido de este worktree, y además se abre un PR (Paso 7.5) como reporte legible y para sincronizar `main`. **No hace falta que Álvaro lo mergee a mano**: la siguiente corrida lo absorbe automáticamente en su Paso W0 (`wiki/auto-*`). Igual puede mergearlo antes si quiere cerrar el ciclo de inmediato.

## Paso W.5 — Integrar anotaciones pendientes (`sec-sys-integrate`)

Antes de procesar fuentes, integra los bloques `<!-- sec:pending -->` que `sec-write` haya podido dejar en artículos del worktree. Esto garantiza que el prose ya esté al día antes de que el Paso 1 añada nueva información encima.

```bash
# Ejecutar sec-sys-integrate apuntando al worktree
WIKI_ARTICLES="$WT/knowledge/wiki/articulos"
# Escanear y procesar todos los artículos con bloques pending
grep -rl 'sec:pending' "$WIKI_ARTICLES" || echo "Sin bloques pending — continuar."
```

Invoca el skill `sec-sys-integrate` con el worktree como raíz. El skill:
1. Detecta todos los artículos con `<!-- sec:pending ... -->`.
2. Integra cada señal en el prose de la sección correspondiente.
3. Elimina el bloque una vez integrado (o lo marca `sec:conflict` si hay contradicción).
4. Registra los cambios en `$WT/knowledge/wiki/memory/indice.md`.

Si no hay bloques pending, este paso no produce ningún cambio (es idempotente). Si el skill reporta `sec:conflict` en algún artículo, inclúyelo en la sección "Dudas para Álvaro" del reporte (Paso 7).

**No continúes hacia el Paso 0 si `sec-sys-integrate` falla** — los artículos quedarían en estado inconsistente.

## Principios

1. **No inventes datos.** Si una fuente no aporta un campo, déjalo como `[por rellenar]`. Nunca alucines nombres, fechas, relaciones o atributos.
2. **Idempotencia.** Ejecutar el skill dos veces seguidas sin cambios en las fuentes no debe producir diffs distintos de `ultima_actualizacion`.
3. **Merge, no sobrescritura.** Si un artículo ya existe y tiene secciones editadas a mano por el usuario, preserva su contenido; añade/actualiza sólo lo que venga de las fuentes. Distingue las secciones auto-generadas con un marcador HTML al inicio: `<!-- auto:fuente-X -->`.
4. **Cita siempre la fuente.** Cada dato agregado debe acabar referenciado en `fuentes:` del frontmatter (ver formato abajo).
5. **Todo en español.**

## Paso 0 — Preparación

1. Abrir `secretary/knowledge/wiki/README.md` y `secretary/knowledge/wiki/memory/indice.md` para tener presente el contrato y el historial.
2. Listar los artículos actuales: `ls secretary/knowledge/wiki/articulos/**/*.md`.
3. Inicializar un *changelog* de esta corrida (se volcará al final en `memory/indice.md`).
4. Fijar la **fecha actual** (`date +%Y-%m-%d`) en una variable — úsala en todos los campos `agregado:`, `ultima_actualizacion:` y líneas de `indice.md` de esta corrida. No uses la fecha de ejemplo de este documento.
5. Si encuentras copias antiguas del skill (p. ej. `secretary/.claude/skills/sync-wiki/SKILL.md`), están obsoletas: repórtalas para borrar. Este archivo (`~/.claude/scheduled-tasks/wiki-update/SKILL.md`) es la única fuente de verdad.

## Paso 1 — Recorrer fuentes registradas

Procesa en este orden. Si una fuente no existe o está vacía, sáltala sin fallar.

### Procedencia de cada item (clasificación obligatoria)

Antes de integrar/borrar un item de cualquier `*/memory/*.md`, clasifícalo con el mapa `$PROV` (Paso 3 de W0):

- **De extractor de esta corrida**: su header está en `$PROV` → atribuible al `PR#N` que lo aportó.
- **Pre-existente en `main`**: no está en `$PROV` → llegó por otra vía (commit/wave manual, backfill, consolidación a mano). **Intégralo igual** (el modelo no cambia), pero anota su commit de origen (`git log -1 -S`) para el reporte.

Lleva, por fuente, dos contadores separados (extractor-de-hoy vs pre-existente) y, para acciones, las listas de IDs `acc-*` de cada grupo. Esto alimenta el bucket de "items integrados por procedencia" del Paso 7.

### 1.1 Correo (`secretary/extractors/mail/`)

App externa que procesa Gmail y mantiene memorias consolidadas en:

- `secretary/extractors/mail/memory/personas.md`
- `secretary/extractors/mail/memory/organizaciones.md`
- `secretary/extractors/mail/memory/entidades.md`
- `secretary/extractors/mail/memory/suscripciones.md`

Cada archivo es **append-only por la rutina del correo**: contiene items con frontmatter mínimo y `pendiente_wiki: true` para los aún no integrados. Formato esperado por item:

```markdown
## <Nombre completo>
- email: <correo si aplica>
- contexto: <descripción del descubrimiento>
- fuentes: gmail:<message-id>, ...
- detectado: YYYY-MM-DD
- pendiente_wiki: true
```

**Contrato de integración (responsabilidad de sync-wiki):**

1. Para cada item con `pendiente_wiki: true`:
   - Buscar si el artículo correspondiente ya existe en la wiki.
   - Si existe → añadir/actualizar **sólo los datos nuevos** (no duplicar lo ya presente). Si descubres que el item del consolidado está mal (typo, nombre incompleto, mal categorizado) **corrige también el consolidado** antes de borrarlo, o repórtalo si requiere juicio (igual que en el Paso 3.5).
   - Si no existe → crear el artículo siguiendo las convenciones de slug y frontmatter.
2. Personas → `articulos/personas/<slug>.md` (`tipo: persona`). Organizaciones → `articulos/organizaciones/<slug>.md` (`tipo: organizacion`). Suscripciones / entidades temáticas → `articulos/temas/<slug>.md`.
3. **Limpieza obligatoria**: una vez integrado, **flipea el item a `pendiente_wiki: false`** con un comentario inline (`pendiente_wiki: false  # integrado YYYY-MM-DD (wiki-update)`). NO borres el bloque: la convención real del repo (verificada 2026-06-10) es **flip-to-false, no borrado** — `extractors/mail/memory/personas.md` y `extractors/meetings/memory/*.md` acumulan cientos de items en `false` como ledger. Borrar perdería el registro y rompería la idempotencia. Las plantillas/ejemplos dentro de fences ` ``` ` NO se tocan. Si quedan dudas (datos ambiguos, líneas `# duda: ...`), deja el item con `pendiente_wiki: true` y añade una nota propia explicando por qué no se integró.
4. Si tras la corrida un consolidado queda sin items, déjalo con sólo el encabezado y una línea `# última limpieza: YYYY-MM-DD`. Nunca borres el archivo.

Cada entrada en `fuentes:` del artículo wiki para datos provenientes de correo:
```yaml
- tipo: correo
  ref: secretary/extractors/mail/memory/<archivo>.md
  agregado: YYYY-MM-DD
```

Si el item cita un message-id concreto, usar `ref: gmail:<message-id>`.

**Memos diarios** (`memory/YYYY-MM-DD.md`) son log histórico de la rutina del correo; no los consumas directamente. Sólo léelos como contexto adicional si un item del consolidado es ambiguo y necesitas desambiguar.

### 1.2 Reuniones (`secretary/extractors/meetings/`)

App externa (Murmur) que procesa transcripciones de Meet (y otras grabaciones) y deja **memorias consolidadas** en disco — análogo a `correo/`. **No proceses las transcripciones crudas**; la wiki sólo consume los archivos de `memory/`.

Estructura esperada (a medida que la app evolucione, los archivos pueden ampliarse — descúbrelos con `ls secretary/extractors/meetings/memory/` cada corrida):

- `secretary/extractors/meetings/memory/personas.md` — personas detectadas en reuniones
- `secretary/extractors/meetings/memory/organizaciones.md`
- `secretary/extractors/meetings/memory/entidades.md` — temas/proyectos enriquecidos por reuniones
- `secretary/extractors/meetings/memory/reuniones.md` — registro de reuniones procesadas (fecha, título, participantes, link a `resumen_path` en `secretary/extractors/meetings/summaries/`)
- `secretary/extractors/meetings/memory/acciones.md` — acciones nuevas y items `[update]` sobre acciones existentes
- `_procesados.jsonl` y `_drive_layout.json` — bookkeeping interno del módulo, **no consumir**.

#### Acciones — manejo especial

Cada item con encabezado `## acc-YYYYMMDD-NNN` (sin sufijo) es una acción nueva. Integrarla a la wiki así:
- Si `responsable` matchea con [[alvaro-mur]] (Álvaro Mur o variantes) → añadirla a la sección *Acciones abiertas* en `articulos/alvaro-mur.md`.
- Si responsable es otra persona con artículo en wiki → añadirla a sección *Acciones pendientes* en su artículo de `articulos/personas/`.
- Cualquiera que sea el responsable, también añadir un cross-link desde el artículo del tema/proyecto referenciado en `contexto`. Sección *Acciones abiertas* del tema.
- Formato sugerido para una acción en wiki: `- **acc-YYYYMMDD-NNN** — <accion> · responsable: [[wikilink]] · deadline: YYYY-MM-DD · origen: [resumen](path)`

Items con encabezado `## acc-YYYYMMDD-NNN [update]` son cambios a acciones que ya están en la wiki:
- `estado_nuevo: completado | cancelado` → marcar la línea correspondiente con `~~tachado~~` o moverla a sección *Acciones cerradas* del mismo artículo (preferir mover, anota fecha de cierre y link al resumen evidencia).
- `estado_nuevo: reagendado` con `deadline_nuevo` → actualizar el deadline in-place.
- `cambio_responsable: <nueva_persona>` → migrar el item al artículo del nuevo responsable, mantener el ID estable.

Tras integrar tanto un item nuevo como un `[update]`, **flipea su `pendiente_wiki: true → false`** con comentario inline (NO lo borres; igual contrato flip-to-false que personas/orgs — ver 1.1 §3). `acciones.md` mantiene un ledger de cientos de acciones en `false`. Si un `[update]` apunta a una acción que **no está registrada como abierta en la wiki** (p.ej. completar algo que nunca se integró), igual flipea el item a `false` y repórtalo: el update queda procesado sin mover ninguna línea de artículo.

Mapeo, idéntico a correo:
- Personas → `articulos/personas/<slug>.md`.
- Organizaciones → `articulos/organizaciones/<slug>.md`.
- Temas/proyectos recurrentes → `articulos/temas/<slug>.md`.
- Cada reunión nueva en `reuniones.md` → línea en *Actividad reciente* de `alvaro-mur.md` con fecha + título + participantes (wikilinks).

Cada entrada en `fuentes:` para datos provenientes de reuniones:
```yaml
- tipo: reuniones
  ref: secretary/extractors/meetings/memory/<archivo>.md
  agregado: 2026-04-30
```

Si la memoria cita un meeting-id concreto, usar `ref: reuniones:<meeting-id>`.

**Estado:** la carpeta `secretary/extractors/meetings/memory/` puede no existir aún; si está vacía o ausente, sáltala sin fallar (igual que las demás fuentes ausentes).

### 1.3 Calendario (MCP `dc4398fd-...`)

Usar los MCP tools `list_calendars` y `list_events` disponibles. Obtener eventos de los últimos 14 días y próximos 30.

> ⚠️ **Barre TODOS los calendarios, no solo el primary.** `list_events` sin `calendarId` se salta los
> compartidos — incluido el de **Inspiro** (`your.work.email@company.com`, donde viven las reuniones de Norte
> Compartido / Inspiro 3.0). Tras `list_calendars`, itera `list_events` por cada calendario relevante
> (mínimo `your.personal.email@gmail.com` y `your.work.email@company.com`). El MCP de la cuenta personal ya alcanza el
> de Inspiro como owner — no hace falta cambiar de cuenta.

- Participantes recurrentes → artículos en `personas/`.
- Títulos recurrentes → temas o proyectos en `temas/` / `organizaciones/`.
- En `alvaro-mur.md`, sección *Actividad reciente*: eventos destacados.

Fuente: `tipo: calendario, ref: <event-id>`.

### 1.4 Gmail directo (MCP `a9767862-...`)

Sólo si el usuario explícitamente lo habilita (por defecto la app de correo ya cubre esto; evita duplicar trabajo). Útil para búsquedas puntuales tipo "amplía contexto sobre esta persona" durante un merge.

### 1.5 Drive — carpetas/archivos registrados

Álvaro irá proporcionando links/paths de Drive. Manténlos en un archivo de registro:

`secretary/knowledge/wiki/memory/fuentes-drive.md` — formato:
```markdown
- https://drive.google.com/...  | tema: <slug o tipo> | notas: ...
```

Para cada entrada:
- Si es carpeta, listar contenidos y decidir a qué artículo/s alimenta.
- Si es archivo, extraer texto (usar MCP de Drive si está disponible, o el skill adecuado según tipo: `anthropic-skills:pdf`, `:docx`, `:xlsx`, `:pptx`).
- Incorporar hechos al artículo objetivo; nunca pegar el documento completo, sólo síntesis con cita.

Fuente: `tipo: drive, ref: <url>, titulo: <nombre>`.

### 1.6 Drive — consolidados del crawler (`secretary/extractors/drive/memory/`)

El crawler `drive-crawler` produce consolidados pre-procesados en `secretary/extractors/drive/memory/`. A diferencia de la sección 1.5 (que maneja links manuales a documentos del Drive), esta sección consume los consolidados del crawler — análogo a como se consumen correo y reuniones.

**Archivos a consumir:**

- `extractors/drive/memory/personas.md` → `articulos/personas/`
- `extractors/drive/memory/organizaciones.md` → `articulos/organizaciones/`
- `extractors/drive/memory/entidades.md` → `articulos/temas/` o `pendiente_wiki: true` en el módulo que más la cita
- `extractors/drive/memory/proyectos.md` → `articulos/temas/` (proyectos son temas; si el contenido es reducido puede absorberse en el artículo de la org principal)

**NO consumir directamente:**
- `documentos-clave.md` — índice de referencia de documentos, no lista de items wiki. Solo leerlo como contexto si un item de otro consolidado es ambiguo.
- `YYYY-MM-DD.md` — memos históricos del crawler (análogos a los diarios en `extractors/mail/memory/`). Leerlos solo para desambiguar, nunca como fuente primaria.

**Contrato de integración (diferencia clave respecto a correo/reuniones):**

Los consolidados de drive son **acumulativos** — los items **no se borran** tras integrar. En su lugar:

1. Si un item tiene `pendiente_wiki: false` (marcado por una corrida anterior): saltarlo, ya está integrado.
2. Si un item tiene `pendiente_wiki: true` o no tiene campo `pendiente_wiki`: integrarlo en el artículo wiki correspondiente (misma lógica que correo: buscar si existe, crear si no).
3. Tras integrar, **marcar el item** añadiendo `- pendiente_wiki: false  # integrado YYYY-MM-DD (<resumen brevísimo de qué se hizo>)`. No borrar el item.
4. Si quedan dudas (datos ambiguos, reconciliaciones pendientes): dejar `pendiente_wiki: true` y añadir nota explicando el bloqueo.

Si el item describe datos adicionales para un artículo wiki **ya existente** (no requiere artículo nuevo, solo enriquecimiento), integrar el dato nuevo en el artículo y marcar igualmente `pendiente_wiki: false`.

**Mapeo:**
- Personas → `articulos/personas/<slug>.md` (`tipo: persona`)
- Organizaciones → `articulos/organizaciones/<slug>.md` (`tipo: organizacion`)
- Entidades/proyectos → `articulos/temas/<slug>.md` (`tipo: tema`)

**Formato `fuentes:` para datos de drive:**
```yaml
- tipo: drive
  ref: secretary/extractors/drive/memory/<archivo>.md
  agregado: YYYY-MM-DD
```
Si el item cita un id de documento concreto (`id: 1ABC...`), usar `ref: drive:<id>`.

**Estado:** si `secretary/extractors/drive/memory/` no existe o está vacía, saltarla sin fallar.

### 1.7 WhatsApp — captura atendida vía Axon (`secretary/extractors/whatsapp/`)

**Actualización 2026-07-02 (Feature 007 pivote local-first, ver `_diseño/specs/007-axon-secretary-relay/`):** el extractor `whatsapp-monitor` (Baileys, headless) está **jubilado** — `auth/` ausente desde ~2026-05-20. La fuente actual es **Axon** (extensión Chrome que Álvaro usa para leer WhatsApp Web): cuando lee un chat, hace `POST /capture` contra el daemon local `secd`, que escribe en los mismos archivos consolidados que usaba Baileys. La estructura del archivo no cambió; lo que cambió es **quién escribe** y **qué tan sintetizado llega el contenido** (ver más abajo).

**Archivos a consumir:**

- `secretary/extractors/whatsapp/memory/chats.md` — una sección `## YYYY-MM-DD — <chat>` por tanda de mensajes nuevos capturados.
- `secretary/extractors/whatsapp/memory/acciones.md` — mismo esquema `acc-YYYYMMDD-NNN` que reuniones (ver 1.2 §Acciones — manejo especial); aplica el mismo contrato de integración y flip-to-false.
- `secretary/extractors/whatsapp/summaries/<archivo>.md` — el contenido que `resumen_path` referencia. **Léelo siempre antes de integrar** un item de `chats.md`: no es opcional como en correo/reuniones.

**Diferencia clave respecto a correo/reuniones/drive — resumen NO sintetizado.** Los consolidados de correo/reuniones/drive ya traen el hecho extraído y redactado por su propio pipeline; aquí solo `mensajes_procesados`, `categoria`, `periodo` y el puntero a `resumen_path` vienen prearmados — el archivo en `summaries/` es una **transcripción cruda** (`tipo: captura-axon (transcripción cruda, sin sintetizar)` en su frontmatter), no un memo. Axon captura en JS sin pasar por un subagente, así que la síntesis —qué pasó, qué implica, si hay un compromiso o dato nuevo— es trabajo de **esta** rutina al integrar, no del extractor. Si el chat no aporta nada nuevo al artículo (charla trivial, saludo, coordinación ya reflejada), es válido flipear a `pendiente_wiki: false` sin escribir nada nuevo en el artículo — no fuerces una línea de "Actividad reciente" vacía de contenido.

**Contrato de integración (mismo mecanismo flip-to-false que 1.1/1.2/1.6):**

1. Para cada item de `chats.md` con `pendiente_wiki: true`: leer el `resumen_path`, extraer qué es relevante (acuerdos, datos nuevos, próximos pasos, cambio de estado de una relación/proyecto).
2. `categoria: persona` → integrar en `articulos/personas/<slug>.md` (buscar por nombre del chat / entidad ya resuelta en `temas:`; crear el artículo si no existe, igual que correo).
3. `categoria: proyecto` (chats de grupo) → integrar en `articulos/temas/<slug>.md` si el grupo representa un proyecto/iniciativa con entidad propia; si el contenido es acotado y el grupo pertenece claramente a una organización con artículo, puede absorberse ahí en vez de crear un tema nuevo (mismo criterio que `proyectos.md` en 1.6).
4. `categoria: radar` → no debería aparecer en capturas nuevas de Axon (ese modo era de la rutina Baileys retirada, monitoreo pasivo sin lectura atendida); si aparece un item legado con esta categoría, trátalo como *señal de baja prioridad* — una línea corta en el artículo si aporta algo, o flip directo a `false` si es ruido.
5. Si `temas:` ya trae un wikilink (`[[personas/slug]]` u `[[organizaciones/slug]]`) — lo escribe `secd` solo cuando el chat resolvió a una entidad *ya existente* en la wiki, nunca como forward-ref — úsalo para confirmar el artículo destino sin tener que re-resolver el nombre.
6. Tras integrar (o decidir que no aporta nada), **flipea `pendiente_wiki: true → false`** con comentario inline (`# integrado YYYY-MM-DD (wiki-update)` o `# sin novedad, YYYY-MM-DD`). No borres el bloque — mismo ledger append-only que el resto.
7. Cada chat nuevo relevante en `chats.md` → línea en *Actividad reciente* de `alvaro-mur.md` o del artículo de la persona/tema, igual que reuniones (1.2 §Mapeo, último punto).

**Formato `fuentes:` para datos de whatsapp:**
```yaml
- tipo: whatsapp
  ref: secretary/extractors/whatsapp/summaries/<archivo>.md
  agregado: YYYY-MM-DD
```

**`acciones.md` — manejo idéntico a reuniones** (ver 1.2 §Acciones — manejo especial): responsable → *Acciones abiertas* de su artículo; cross-link al tema/proyecto en `contexto`; `[update]` para cambios de estado; flip-to-false tras integrar. La única diferencia es `origen:` apunta a `extractors/whatsapp/summaries/<archivo>.md` en vez de un resumen de reunión — y, como con chats.md, ese origen es transcripción cruda: si el `contexto` de la acción no basta para redactarla en el artículo, léelo antes de integrar.

**Estado:** el módulo ya no corre por schedule (ver `contract.yaml`: `freshness.sla` marcado *event-driven*, `health: paused` porque no hay rutina programada que auditar) — puede haber cero items nuevos en corridas donde Álvaro no usó Axon. Sáltalo sin fallar si `chats.md`/`acciones.md` no tienen items con `pendiente_wiki: true`.

## Paso 2 — Consolidar el artículo principal

Tras procesar todas las fuentes, actualizar `articulos/alvaro-mur.md`:

- *Actividad reciente*: últimas ~15 entradas ordenadas por fecha descendente.
- *Red de contactos*: enlace a cada persona creada/actualizada en esta corrida.
- *Organizaciones y proyectos*: idem.
- *Temas e intereses*: idem.
- Actualizar `ultima_actualizacion` sólo si cambió algo sustantivo.

## Paso 3 — Actualizar los índices de categoría

Para cada categoría (`personas`, `organizaciones`, `temas`), regenerar la sección *Listado* de `_index.md` con enlaces a todos los artículos de esa carpeta, agrupados alfabéticamente. Mantener el resto del archivo intacto.

## Paso 3.5 — Tidy-up de la wiki

Antes de registrar cambios y rebuild, pasada de limpieza sobre *todos* los artículos (no sólo los tocados en esta corrida). El objetivo es que la wiki no acumule inconsistencias menores entre corridas. Es el momento en el que el agente actúa como editor, no sólo como ingestor.

Chequeos a ejecutar:

1. **Consistencia `titulo` ↔ `Nombre`/`Apellido` ↔ `_index.md`.**
   - Si el infobox tiene `Nombre` + `Apellido` separados, `titulo` debe ser `Nombre Apellido` completo. Si en el `_index.md` de la categoría aparece con nombre completo pero el `titulo` del archivo está incompleto, actualizar `titulo`. Caso real: `personas/arturo.md` tenía `titulo: Arturo` mientras `_index.md` lo listaba como "Arturo González del Valle".
   - No inventar apellidos: si el `_index.md` también está en corto, dejar como está y reportarlo al final para que Álvaro lo provea.

2. **Enlaces rotos (`[[slug]]`).** Se delega en el validator de CI, que es la fuente de verdad (también lo corre GitHub Actions en cada PR). Ver Paso 3.7 para el procedimiento auto-mejorable; aquí basta con saber que el validator agrupa por target y reporta:
   - **FAIL** — targets nuevos con ≥2 referencias rotas (acción obligatoria esta corrida).
   - **GRANDFATHERED** — targets ya listados en `scripts/ci/wikilinks_known_broken.txt` (achicar progresivamente).
   - **WARN** — targets con 1 sola ref (tolerados como deuda transitoria/typo; no actuar salvo que sean evidentemente arreglables).
   - **INFO de obsoletos** — slugs listados en known_broken que ya no aparecen rotos: removerlos del archivo.

3. **Categoría incorrecta.** Detectar artículos con `tipo: persona` cuyo contenido describe una organización (o viceversa). Ejemplo en el repo actual: `personas/norsac.md` es realmente una organización cliente de Inspiro. **No mover archivos automáticamente** (rompe wikilinks en cadena); reportarlo al final para que Álvaro decida.

4. **Campos `[por rellenar]` acumulados.** Grep por `[por rellenar]` en el infobox de todos los artículos y reportar cuántos campos siguen sin poblar por artículo. Útil para que Álvaro vea qué hay que enriquecer manualmente o con nuevas fuentes.

5. **Frontmatter mal formado.** Verificar que todos los artículos tengan `titulo`, `tipo`, `ultima_actualizacion` (YYYY-MM-DD) y `categorias` como lista. Si falta algo, reportar.

6. **Fechas `ultima_actualizacion` en el futuro o con formato incorrecto.** Si alguna fecha es posterior a hoy o no matchea `^\d{4}-\d{2}-\d{2}$`, reportar.

Criterio general: **arregla sin preguntar lo que sea puramente cosmético/consistencia** (titulo desactualizado, frontmatter con typo, enlace a slug con prefijo incorrecto). **Reporta y no toques** lo que implique juicio (recategorizar, rebautizar slugs, inventar datos). Cada arreglo automático debe loguearse en `indice.md` igual que los del Paso 4.

## Paso 3.7 — Auto-mejora de wikilinks rotos (consume el validator de CI)

La política de wikilinks (introducida 2026-05-29) tolera 1-off pero exige que cualquier slug con **≥2 referencias** rotas o tenga artículo, o esté registrado como `pendiente_wiki: true` en un `*/memory/entidades.md`. La rutina es la responsable de ir achicando esta deuda — el validator sólo señala.

**Paso 3.7.1 — Ejecutar el validator y parsear su salida**

```bash
python3 "$WT/scripts/ci/validate_wikilinks.py" > /tmp/wikilinks.out 2>&1 || true
cat /tmp/wikilinks.out
```

La salida tiene cuatro grupos relevantes (cada uno con sus targets agrupados):

- `FAIL — targets NUEVOS con ≥2 referencias rotas` → deuda no prevista; actuar siempre.
- `GRANDFATHERED — targets con ≥2 refs ya listados en known_broken` → deuda heredada; cada corrida atacar al menos los **3 de más refs**, no es necesario vaciarla de golpe.
- `WARN — targets con 1 referencia rota` → no actuar salvo arreglo obvio (typo de slug que sabes corregir).
- `INFO — entradas en known_broken ya resueltas` → quitar del archivo.

**Paso 3.7.2 — Resolver cada target accionable**

Para cada target `T` en `FAIL` (todos) y los top 3 de `GRANDFATHERED` por nº de refs:

1. **¿Es un slug bien formado de una entidad real que merece artículo?**  
   → crear el artículo en la categoría correcta con el contrato del Paso 1 (frontmatter, `## Resumen` con `[por rellenar]` si no hay datos, `fuentes:` apuntando al primer resumen que lo cita). Si estaba en `known_broken`, **remover la línea**. Si era un FAIL nuevo, listo.

2. **¿Es una entidad real pero todavía no hay material suficiente para un artículo?**  
   → registrarla como `pendiente_wiki: true` en el `*/memory/entidades.md` del módulo que más la cita (reuniones / whatsapp / correo). El validator la deja de marcar al detectar el forward-ref. Si estaba en `known_broken`, remover la línea.

3. **¿Es un slug mal formado, typo compartido entre dos resúmenes, o un wikilink que el transcriptor inventó (p.ej. `[[acc-20260511 detracciones]]` con espacio, `[[alvaro-mur\]]` con bracket escapado)?**  
   → corregir el slug en los resúmenes que lo emiten (el validator imprime la ruta:línea de cada ref). Si era una sola ref es WARN, pero si son varias suele ser el extractor emitiendo mal — corregir y, si hace falta, dejar nota en el módulo origen (whatsapp/reuniones-update) para que ajuste su plantilla.

4. **¿Es una referencia a una acción (`[[acc-…]]`) o a un resumen (`[[extractors/meetings/summaries/…]]`)?**  
   → no son artículos. Si son típicos y se repiten, añadir el slug a `known_broken` **con comentario inline** justificando ("no es artículo: ID de acción", "no es artículo: ruta a resumen"). El validator deja de marcarlos.

**Paso 3.7.3 — Limpiar entradas obsoletas**

Por cada slug en el bloque `INFO — entradas en known_broken ya resueltas`, borrar su línea de `$WT/scripts/ci/wikilinks_known_broken.txt`. Esto evita que el archivo crezca con deuda fantasma.

**Paso 3.7.4 — Re-ejecutar el validator**

```bash
python3 "$WT/scripts/ci/validate_wikilinks.py" || { echo "Wikilinks: aún hay FAIL — atender antes de continuar."; exit 1; }
```

Debe salir con `OK` o `OK con deuda`. Si todavía hay `FAIL`, no continúes hacia el build: el PR saldría rojo. Reporta al final qué quedó pendiente.

**Reporte (Paso 7)** debe incluir un bucket *Wikilinks*:
- targets resueltos esta corrida (artículo nuevo / pendiente_wiki nuevo / slug corregido).
- nº de targets aún grandfathered, y cuántos bajó respecto a la corrida anterior (`git diff HEAD origin/main -- scripts/ci/wikilinks_known_broken.txt | grep -c '^-[^-]'`).
- targets en WARN que el agente decidió ignorar (si los hay, una línea explicando por qué).

## Paso 4 — Panel de módulos en la wiki

La wiki no sólo agrega *contenido* (personas, orgs, temas) sino que **funciona también como tablero de navegación** hacia el procesamiento de cada submódulo de `secretary/`. Cada submódulo activo (`mail/`, `meetings/`, `loops/job-search/`, etc., además de la integración de calendario y drive) tiene un artículo bajo `articulos/modulos/` que actúa como índice de:

- ruta del módulo en disco
- archivos de memoria/reportes que produce (con su path absoluto, para que Álvaro pueda hacer click/abrirlos desde el HTML)
- estado del módulo (activo, en desarrollo, archivado)
- última sincronización contra la wiki
- enlaces a los artículos derivados (personas/orgs/temas) que ese módulo alimenta

Convenciones:

- Categoría: `modulos`. Slug: nombre del submódulo (`correo`, `reuniones`, `calendario`, `drive`, `job-search`) o del agente de infraestructura (`wiki-update`, `sec-heartbeat`, `dispatch`, `housekeeping`).
- `tipo: modulo`.
- Sección obligatoria *Reportes y memorias*: lista con cada archivo relevante del módulo (path absoluto + breve descripción). Mantén esta lista regenerada cada corrida — si aparecen archivos nuevos en `memory/` o equivalente, agrégalos; si desaparecieron, márcalos como inactivos en lugar de borrarlos.
- Sección *Historial de ejecución y métricas* — auto-inyectada, ver Paso 4.2.
- Sección *Ramas y PRs* — auto-inyectada, ver Paso 4.3.
- Sección *Última sincronización con la wiki* — auto-inyectada, ver Paso 4.4. Reemplaza al llenado a mano que tenían `correo.md`/`reuniones.md` desde 2026-05; a partir de esta corrida las tres secciones se generan igual **para todos** los artículos de módulo (lectores e infraestructura), no sólo esos dos.
- Mantén `articulos/modulos/_index.md` como portal: tabla con módulo, estado, última sincronización, enlace.

El **calendario** y **drive**, aunque no son carpetas en `secretary/`, también tienen su artículo bajo `modulos/` (calendario referencia el MCP y la cuenta usada; drive referencia `secretary/knowledge/wiki/memory/fuentes-drive.md`). Calendario no tiene rutina propia (lo corre `wiki-update` directo vía MCP) — sus secciones 4.2/4.3 se marcan `N/A` (ver mapeo abajo).

Si un módulo nuevo aparece en `secretary/` y no está documentado aquí, **no lo proceses como fuente de datos** (regla del Paso 0/Paso 1) pero **sí crea su artículo en `modulos/`** con `Estado: candidata, pendiente de confirmación` para que Álvaro lo vea desde la wiki.

### Paso 4.1 — Mapeo módulo → rutina(s) / rama / repo

Antes de leer métricas o ramas necesitas saber, por cada artículo de `modulos/`, qué `routine_id` lo alimenta (para `latest-*.meta.json` y `metrics.jsonl`) y qué prefijo de rama/repo usar para PRs. La fuente de verdad del `routine_id` es el campo `routine:` de `extractors/<módulo>/contract.yaml` o `loops/<módulo>/contract.yaml` cuando ese archivo existe (Paso 0/015-module-contract); para los agentes de infraestructura (sin contract.yaml) usa esta tabla fija:

| Artículo (`modulos/<slug>`) | `routine_id` (metrics/latest) | Prefijo de rama | Repo de PRs |
|---|---|---|---|
| `correo` | `revision-correo` (contract.yaml) | `correo/auto-` | instancia (`$OWNER/$NAME`) |
| `reuniones` | `reuniones-update` (contract.yaml); también `reuniones-scheduler` (poller mecánico, sin PR propio) | `reuniones/auto-` | instancia (`$OWNER/$NAME`) |
| `drive` | `drive-crawler` (contract.yaml) | `drive/auto-` | instancia (`$OWNER/$NAME`) |
| `whatsapp` | `whatsapp-monitor` (contract.yaml) — **pausado**, ver nota abajo | `whatsapp/auto-` | instancia (`$OWNER/$NAME`) |
| `job-search` | `job-search-crawler` (contract.yaml) | `loops/job-search/auto-` | instancia (`$OWNER/$NAME`) |
| `calendario` | — (sin rutina propia, corre inline en wiki-update vía MCP) | N/A | N/A |
| `wiki-update` | `wiki-update` | `wiki/auto-` | instancia (`$OWNER/$NAME`) |
| `sec-heartbeat` | `sec-heartbeat` | N/A (main-only, nunca abre PR — ver su propio artículo) | — |
| `housekeeping` | `housekeeping` (contract.yaml si existe) + `tidy-up` (poller mecánico) | `housekeeping/auto-` | instancia (`$OWNER/$NAME`) |
| `dispatch` | `dispatch-executor` | sin prefijo fijo — cada PR vive en el repo destino del issue `dispatch:execute`, rama la que ese repo use | allowlist de `dispatch.executor.repos` en `$REPO/.secretary.yml` (lista `{repo, path}`) |

**whatsapp — nota:** el `contract.yaml` documenta la rutina retirada (`whatsapp-monitor`, Baileys, sin `auth/` desde ~2026-05-20); la captura actual es event-driven vía Axon→`secd` y no genera `latest-whatsapp-monitor.meta.json` nuevo. Si no hay meta reciente (`mtime` > 30 días o inexistente), la sección 4.2 debe decir explícitamente "sin corridas programadas — captura event-driven vía Axon" en vez de reportar datos viejos como si fueran actuales.

Si `contract.yaml` no existe para un módulo lector y la tabla tampoco lo cubre, no inventes un `routine_id`: deja las secciones 4.2/4.3 con "routine_id no determinado — revisar mapeo en Paso 4.1 de este SKILL" y repórtalo al final (Paso 7).

### Paso 4.2 — Historial de ejecución y métricas (última corrida + acumulado mensual)

**Importante:** `subsystem/routines/latest/` y `subsystem/routines/metrics/metrics.jsonl` están en `.gitignore` (bookkeeping local, no versionado) — no existen en `$WT` (que parte de `origin/main`). Léelos siempre de `$REPO` (la instancia principal, `~/.secretary`), nunca del worktree.

**Última corrida** — por cada `routine_id` de la tabla 4.1:

```bash
META="$REPO/subsystem/routines/latest/latest-<routine_id>.meta.json"
[ -f "$META" ] && jq '{status, started_at, ended_at, duration_ms, cost: .cost.estimated_usd, trigger, exit_code}' "$META" || echo "sin latest-*.meta.json aún"
```

**Acumulado mensual** — filtra `metrics.jsonl` por `routine_id` y por el mes en curso (`YYYY-MM`, según la fecha fijada en Paso 0):

```bash
MES="2026-07"  # usar la variable de fecha del Paso 0, no hardcodear
jq -s --arg rid "<routine_id>" --arg mes "$MES" '
  [.[] | select(.routine_id == $rid and (.started_at // "" | startswith($mes)))] as $runs |
  {
    ejecuciones: ($runs | length),
    exitosas: ([$runs[] | select(.status == "success")] | length),
    costo_usd: ([$runs[].cost.estimated_usd] | add // 0 | (. * 1000 | round / 1000)),
    duracion_prom_ms: (if ($runs | length) > 0 then ([$runs[].duration_ms] | add / length | round) else null end)
  }' "$REPO/subsystem/routines/metrics/metrics.jsonl"
```

Con ambos resultados, escribe/actualiza la sección del artículo:

```markdown
## Historial de ejecución y métricas

<!-- auto:metrics -->
**Última corrida** (YYYY-MM-DD HH:MM): `status` · duración `Xs` · costo estimado `$X.XX` · trigger `launchd|manual|cron`.

**Acumulado de MES 2026**: N ejecuciones, N exitosas (X% éxito), costo total estimado $X.XX, duración promedio Xs.
```

Si no hay `latest-*.meta.json` ni entradas en `metrics.jsonl` para ese `routine_id` (rutina nueva o pausada), escribe "Sin corridas registradas todavía" (o la nota de whatsapp del Paso 4.1) — nunca inventes cifras.

### Paso 4.3 — Ramas y PRs activos

Para los módulos con prefijo de rama definido en la tabla 4.1 (repo de la instancia, mismo `$OWNER`/`$NAME` calculados en W0):

```bash
PREFIJO="correo/auto-"   # de la tabla 4.1
gh pr list --repo "$OWNER/$NAME" --state open --json number,headRefName,createdAt \
  --jq --arg p "$PREFIJO" '[.[] | select(.headRefName | startswith($p))]'
gh pr list --repo "$OWNER/$NAME" --state merged --json number,headRefName,mergedAt --limit 5 \
  --jq --arg p "$PREFIJO" '[.[] | select(.headRefName | startswith($p))] | sort_by(.mergedAt) | reverse | .[0]'
```

Para **dispatch** (sin prefijo fijo, multi-repo): recorre `dispatch.executor.repos` de `$REPO/.secretary.yml` y por cada `repo` cuenta issues abiertos con label `dispatch:execute` + PRs abiertos que referencien `Closes #` de esos issues:

```bash
for R in $(yq -r '.dispatch.executor.repos[].repo' "$REPO/.secretary.yml"); do
  echo "== $R =="
  gh issue list --repo "$R" --label dispatch:execute --state open --json number,title
  gh pr list --repo "$R" --state open --json number,title,headRefName --search "Closes in:body"
done
```

Para **calendario** y **sec-heartbeat** (sin PRs, ver tabla 4.1): la sección se escribe como una línea fija, sin ejecutar `gh` — "N/A — módulo sin PRs propios (ver Paso 4.1)".

Escribe/actualiza la sección:

```markdown
## Ramas y PRs

<!-- auto:branches -->
**Abiertos**: PR #N (`rama`, abierto YYYY-MM-DD) — o "ninguno".
**Último mergeado**: PR #N (`rama`, mergeado YYYY-MM-DD) — o "sin mergeados registrados".
```

### Paso 4.4 — Última sincronización con la wiki

Cierra las tres secciones con la línea de sincronización de **esta** corrida (formato ya usado en `correo.md`/`reuniones.md`, ahora aplicado a todos los artículos de `modulos/`):

```markdown
## Última sincronización con la wiki

<!-- auto:sync -->
YYYY-MM-DD — PR #N (wiki) mergeado/abierto esta corrida. <resumen 1 línea: items integrados de este módulo, o "sin ítems nuevos">.
```

Antepón la línea nueva a las anteriores (no las borres — es el mismo historial append-only que ya llevaban `correo.md`/`reuniones.md`); si el archivo crece demasiado, es aceptable truncar entradas de más de ~6 meses a un resumen de una línea por mes, nunca borrar sin dejar rastro.

## Paso 5 — Registrar cambios

Añadir una línea al final de `secretary/knowledge/wiki/memory/indice.md` por cada artículo creado o modificado:

```
YYYY-MM-DD | sync-wiki | <ruta> | <breve resumen del cambio>
```

Si no hubo cambios, añadir una única línea:
```
YYYY-MM-DD | sync-wiki | — | sin cambios
```

## Paso 6 — Rebuild HTML (desde el worktree)

El build debe leer los artículos **del worktree** (los que editaste en esta corrida), no los del instance principal. Para eso se pasa `SECRETARY_DATA="$WT"`. El symlink `wiki/build` no existe en el worktree (está en `.gitignore`), así que se invoca el `build.py` del engine directamente:

```bash
SECRETARY_DATA="$WT" python3 ~/Dev/secretary-core/wiki/build/build.py
```

Lee artículos y fuentes (`estado.md`, `acciones.md`, conteos de resúmenes) desde `$WT/...` y escribe el HTML en `~/Dev/secretary-core/wiki/output` (el repo de deploy). Debe imprimir `Generados N artículos en .../output`. Si falla, **no** silencies el error: no registres los cambios en `indice.md` y reporta el fallo.

**Bug conocido 2026-07-02 — `ARTICULOS` de `build.py` apunta a una ruta obsoleta.** El engine (`~/Dev/secretary-core/wiki/build/build.py`) resuelve `ARTICULOS = SECRETARY_DATA / "wiki" / "articulos"`, pero tras la migración a `.secretary` los artículos viven en `knowledge/wiki/articulos` (no `wiki/articulos`). Con `SECRETARY_DATA="$WT"` el build imprime `Generados 0 artículos` sin error — parece éxito pero está vacío. Afecta también al repo principal (`SECRETARY_DATA=~/.secretary` da el mismo resultado). **Workaround temporal (aplicado esta corrida) que no requiere tocar el engine:** crear un symlink efímero **dentro del worktree**, `ln -s "$WT/knowledge/wiki" "$WT/wiki"`, correr el build, y luego `rm "$WT/wiki"` antes de comitear (no está en `.gitignore` porque no debería existir; no lo dejes en el diff). **Arreglo real pendiente:** corregir `ARTICULOS` en `build.py` a `SECRETARY / "knowledge" / "wiki" / "articulos"` — vive en `~/Dev/secretary-core`, fuera del alcance de un worktree de `.secretary`; repórtalo/hazlo en una sesión de ese repo. Verifica primero con `SECRETARY_DATA="$WT" python3 build.py` si imprime `0 artículos` — si ya fue arreglado, el workaround del symlink deja de ser necesario (no falla si el symlink ya no hace falta, simplemente sería redundante).

## Paso 6.5 — Deploy inmediato (push a Cloudflare)

Si el build fue exitoso, publicar el output (refleja el contenido de este worktree) al repo remoto que Cloudflare Pages despliega. El deploy está centralizado en un único script (`~/Dev/secretary-core/wiki/deploy-output.sh`), registrado en `~/.claude/settings.json`:

```bash
~/Dev/secretary-core/wiki/deploy-output.sh "sync-wiki $(date +%Y-%m-%d)"
```

El script entra a `wiki/output`, hace `git add -A` + commit + push, e inicializa el remote (`git@github.com:yourusername/wiki.git`) la primera vez. Si no hay cambios en el HTML (todo idéntico), no crea commit y sale 0. Si el push falla (red, auth), reportar el error pero no revertir la corrida — los artículos Markdown ya están correctos en el worktree y entrarán al PR. Mantener el deploy en este único script (no reintroducir el push inline).

## Paso 7 — Reporte final (cuerpo del PR)

Este reporte (resumen + "Dudas para Álvaro") se escribe a un archivo temporal en Markdown y se pasa como **cuerpo del PR** (Paso 7.5). Contenido:
- **PRs auto mergeados en W0** (`$MERGED`; marca cuáles llevaron "comentarios aplicados"), los que quedaron sin mergear por conflicto/checks (`$NO_MERGE`), y los que **tienen comentarios sin resolver que requieren a Álvaro** (`$NEEDS_REVIEW`, con qué pide cada uno) — todos a revisar a mano.
- Artículos creados, actualizados, sin cambios.
- **Items integrados, separados por procedencia** (acciones, personas, orgs, temas), usando los contadores del Paso 1:
  - **De extractores de esta corrida**: cuántos por fuente, citando el `PR#N` que los aportó.
  - **Pre-existentes en `main`** (NO de un PR de esta corrida): cuántos, citando el commit de origen y su mensaje (p.ej. `697071f "wave may-2026"`). Para acciones, lista los IDs `acc-*` de este grupo.
  - **Nunca** presentes como "integrado de esta corrida" algo que ya estaba en `main` por fuera del pipeline; si no podés determinar la procedencia de un item, repórtalo como "procedencia indeterminada", no como propio.
- Fuentes consultadas y cuáles estaban vacías/no disponibles.
- Cualquier dato dudoso que quedó como `[por rellenar]` y por qué.
- Confirmación del deploy (Paso 6.5): si se publicó HTML nuevo o quedó idéntico.
- Dudas resueltas esta corrida y backlog vigente (Paso 7.4).

### Dudas para Álvaro (acumuladas — ver Paso 7.4)

Las dudas no se reportan sólo "de esta corrida": se mantienen en un **archivo persistente** `$WT/knowledge/wiki/memory/dudas-pendientes.md` que se arrastra entre corridas (Paso 7.4). El reporte/PR incluye la **lista completa vigente** (arrastradas + nuevas), no sólo las de hoy, para que ninguna duda se pierda si Álvaro no la resuelve en una corrida.

Qué cuenta como duda (mismo criterio de siempre):

1. **Items con `pendiente_wiki: false` por gate** (temas nuevos que requieren validación): slug, resumen de una línea, y qué decisión se espera (¿crear artículo propio o absorber en otro?).
2. **Items con `# duda:`** en los consolidados: copiar la duda textual y la fuente.
3. **Inconsistencias del tidy-up que requieren juicio** (recategorizar, rebautizar, datos ambiguos): describir el problema y las opciones.
4. **Personas/entidades mencionadas en reuniones pero no creadas** (los `<!-- No crear artículo aún -->` del consolidado de personas): listar nombres y contexto mínimo para que Álvaro diga si merecen artículo.

## Paso 7.4 — Mantener `dudas-pendientes.md` (backlog que se acumula)

Archivo: `$WT/knowledge/wiki/memory/dudas-pendientes.md` (versionado, entra al PR). Una entrada por duda:

```markdown
- [ ] `slug-o-nombre` — descripción del bloqueo. Opciones: A / B. _(detectada: YYYY-MM-DD, fuente: <archivo/ref>)_
```

Procedimiento cada corrida:

1. **Leer** el archivo (si no existe, créalo con un encabezado `# Dudas pendientes` y nada más).
2. **Resolver/depurar**: para cada duda ya listada, verificar si esta corrida la resolvió o si dejó de aplicar (la entidad ya se creó, el dato ya está en wiki, Álvaro la decidió). Si está resuelta, **quitarla** y anotar una línea en el reporte ("resueltas esta corrida: …").
3. **Agregar** las dudas nuevas detectadas en esta corrida (criterios 1-4 de arriba), con su fecha de detección y fuente. No duplicar una que ya esté listada (mergear si hay contexto nuevo).
4. **Conservar** las que siguen sin resolver, intactas (no reescribir su fecha de detección original).
5. El bloque "### Dudas para Álvaro" del reporte/PR = **el contenido completo y vigente** de este archivo tras los pasos 2-4. Si quedó vacío, escribir "Ninguna pendiente.".

## Paso 7.5 — Cierre: Commit + Pull Request (este PR es el reporte)

El deploy a Cloudflare ya ocurrió (Paso 6.5). Ahora se versionan los cambios de Markdown del worktree y se abre el PR como reporte y para sincronizar `main`.

**Firma del body del PR:** `/tmp/pr-wiki.md` debe incluir marca/footer de `sec-signature.sh wiki-update` (`_firma.md`).

```bash
cd "$WT"
if [ -z "$(git status --porcelain)" ]; then
  echo "Sin cambios versionados — no se abre PR."
  cd "$REPO" && git worktree remove "$WT" --force && git branch -D "$BRANCH" 2>/dev/null || true
else
  git add -A
  git commit -m "chore(wiki): corrida automática $(date +%Y-%m-%d)"
  git push -u origin "$BRANCH"
  gh label create "hilo:wiki" --description "Hilo de trabajo: wiki" --color FEF2C0 2>/dev/null || true
  # Escribe el reporte (Paso 7, Markdown) con la herramienta Write a /tmp/pr-wiki.md
  gh pr create --title "chore(wiki): corrida automática $(date +%Y-%m-%d)" \
    --label "hilo:wiki" --body-file /tmp/pr-wiki.md
  cd "$REPO" && git worktree remove "$WT" --force
fi
```

- El reporte (`/tmp/pr-wiki.md`) lo creas con la herramienta Write, no con `echo`/heredoc.
- El PR de wiki suele tocar también `$WT/{mail,meetings,whatsapp}/memory/` (limpieza de consolidados integrados) y `$WT/extractors/drive/memory/` (marcado de items como `pendiente_wiki: false`): es parte de su trabajo, no lo evites.
- Si `gh pr create` falla, no revertir: la rama ya está pusheada (y el HTML ya desplegado); reporta el error.
- Devuelve al final la **URL del PR**.

## Convenciones de slug

- Minúsculas, sin acentos, espacios → `-`.
- Personas: `nombre-apellido` (`juan-perez`).
- Organizaciones: nombre corto (`acme`, `cowork`).
- Temas: sustantivo o frase corta (`ia-generativa`, `jiu-jitsu`).
- Módulos: nombre exacto del submódulo en `secretary/` (`correo`, `reuniones`, `job-search`) o etiqueta clara para integraciones externas (`calendario`, `drive`).

## Mantenimiento de este SKILL.md — el agente puede (y debe) editarlo

**Permiso explícito:** tienes permiso para editar este archivo (`~/.claude/scheduled-tasks/wiki-update/SKILL.md`) al final de cada corrida, sin preguntar, cuando tengas aprendizajes que lo mejoren. Este archivo es tu propia memoria operativa; déjalo mejor de como lo encontraste.

Qué tipo de ediciones hacer tras cada corrida:

- **Aprendizajes de mapeo**: si descubriste que cierto tipo de archivo/sección alimenta mejor una categoría distinta a la documentada, actualiza la regla.
- **Patrones observados**: si notas que una fuente siempre trae ruido de cierto tipo (p. ej. firmas de correo confundidas con personas nuevas), añade una regla de filtrado en la subsección correspondiente.
- **Heurísticas de deduplicación** que funcionaron (o fallaron) en esta corrida.
- **Errores comunes** que debes recordar no repetir — añádelos a "Qué NO hacer".
- **Atajos**: comandos o consultas que aceleraron el trabajo.
- **Nuevas fuentes**: si Álvaro te indica durante la corrida una fuente que quiere activar, añade su subsección completa en el Paso 1 (ruta, estructura, mapeo, principios, formato de `fuentes:`).

Reglas al editarse:

1. **Integridad primero**: nunca dejes el archivo en estado inconsistente. Si una edición es grande, hazla al final, tras el rebuild exitoso.
2. **Preserva estructura**: frontmatter intacto, orden de pasos intacto, formato de subsecciones consistente con las existentes.
3. **Registra el cambio** en `secretary/knowledge/wiki/memory/indice.md` con una línea extra: `YYYY-MM-DD | sync-wiki | SKILL.md | <resumen del aprendizaje incorporado>`.
4. **No borres fuentes** aunque estén vacías o inactivas; márcalas con `Estado: inactiva — <motivo>` en su encabezado.
5. **No inventes reglas especulativas**: sólo codifica aprendizajes observados en esta corrida o anteriores. Si tienes una idea no validada, déjala como comentario HTML (`<!-- idea: ... -->`) dentro de la subsección, no como regla activa.
6. **No modifiques** el bloque de frontmatter YAML (`name`, `description`) sin que un cambio de alcance lo justifique.

Fuentes históricas / de referencia (sistemas que Álvaro ha mencionado pero **no están activos** como fuente del skill) se registran en `secretary/knowledge/wiki/memory/fuentes-historicas.md`, no aquí. Si Álvaro decide activar alguna, se traslada su descripción al Paso 1 de este archivo.

Si durante una corrida descubres una carpeta o sistema que **parece una fuente nueva** no listada aquí y Álvaro no lo ha mencionado, **no la proceses**: regístrala en `fuentes-historicas.md` con una nota "candidata, pendiente de confirmación" y reporta el hallazgo al final.

## Qué NO hacer

- No crear artículos con contenido inventado sólo porque una categoría esté vacía.
- No borrar artículos existentes aunque la fuente ya no los mencione — márcalos como inactivos en el infobox (`Estado: inactivo desde YYYY-MM-DD`).
- No tocar archivos fuera de `secretary/knowledge/wiki/` excepto para **leer** de las rutas de fuentes listadas arriba.
- No ejecutar el build si hubo errores al escribir artículos — arregla primero.
- **Forward-refs de wikilinks van SOLO en `*/memory/entidades.md`** (heading = slug, o campo `slug_existente: categoria/slug`), nunca en `personas.md`/`organizaciones.md`. El validator (`load_pending`) sólo lee `entidades.md`; marcar `pendiente_wiki: true` en un item de `personas.md` **no exime** el wikilink y CI falla igual. Aprendizaje 2026-06-12: `[[personas/jose-zuniga]]` referenciado en ≥2 artículos seguía rojo hasta registrarlo como bloque con `slug_existente: personas/jose-zuniga` en `extractors/meetings/memory/entidades.md`.
- **Nunca escribas `[[algo]]` literal dentro de comentarios o notas en archivos de `*/memory/`** (ni en notas inline de `pendiente_wiki: false  # …`). El validator parsea CUALQUIER `[[…]]` del repo como wikilink y lo cuenta como roto. Aprendizaje 2026-06-12: una nota que decía "el crawler no debería emitir `[[project_*]]/[[wiki_*]]`" creó 3 wikilinks rotos y volvió roja la CI. Describe los slugs con prefijos en texto plano (`project-…`, `wiki-…`), sin dobles corchetes.
- **No flipees a `false` un item de `extractors/drive/memory/entidades.md` cuyo slug el crawler emite como wikilink en sus memos** (`project_*`, `wiki_*`): esos `[[…]]` viven en `extractors/drive/memory/*.md` y el `pendiente_wiki: true` es lo único que los exime. Flipearlos rompe CI. Déjalos `true` y reporta que el arreglo va en el crawler. Aprendizaje 2026-06-12.
- **Si delegas la integración a sub-agentes (útil cuando hay muchos items): nunca dejes el path del worktree sin sustituir en el prompt.** Pasa el `$WT` absoluto ya expandido (no un placeholder tipo `WTPATH_PLACEHOLDER`), y dile a cada sub-agente explícitamente "todos tus paths empiezan con `<$WT absoluto>`; NO escribas en `~/.secretary` ni en ningún path que no empiece con esa raíz". Aprendizaje 2026-06-11: con el placeholder sin sustituir, un sub-agente resolvió la raíz como el repo principal y escribió 5 archivos en `~/.secretary` en vez del worktree; hubo que recuperarlos al worktree y revertir el working tree principal. Partición de archivos sin solape entre agentes (cada artículo lo posee 1 solo agente; `_index.md`, `alvaro-mur.md` y los `*/memory/` los maneja el orquestador) sigue siendo la regla para evitar conflictos de escritura.