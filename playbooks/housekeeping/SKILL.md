---
name: housekeeping
description: Revisión diaria de higiene del ecosistema — CLAUDE.md reviews, memoria, PRs pendientes, archivos sin commitear. Organiza lo seguro y reporta lo que necesita decisión humana.
---

# housekeeping — Mantenimiento diario del ecosistema de repos

Rutina que corre 1×/día (06:00 Lima) y revisa el estado de higiene de todos los repos y workspaces de Álvaro. Aplica cambios seguros automáticamente.

> **Spec 024:** separa **nada urgente** (sin PR / ambient) de **hay algo que decidir** (PR).
> No uses `--allow-empty`. Un run en verde sin decisión no abre PR — mismo patrón que
> `tidy-up` / `revision-correo`.

## Repos a revisar

```bash
# Lista de la instancia (`.secretary.yml` → housekeeping.repos); `$HOME` se expande aquí.
REPOS=()
while IFS= read -r r; do REPOS+=("${r/\$HOME/$HOME}"); done < <(secretary config get housekeeping.repos | jq -r '.[]')
```

## W. WORKTREE AISLADO (hacer ANTES que nada)

Trabaja en un worktree de `~/.secretary` (es donde vive el reporte). Los cambios a CLAUDE.md de otros repos se hacen directamente en esos repos (son safe: solo documentación).

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
git worktree prune
git fetch origin main
# Checkout principal al día (playbook versionado, symlinks y lecturas vivas dependen de él).
# Solo si está en main y sin cambios en archivos rastreados; si no, seguir sin tocarlo.
if [ "$(git branch --show-current)" = "main" ] && [ -z "$(git status --porcelain --untracked-files=no)" ]; then
  git merge --ff-only origin/main || echo "⚠️ checkout principal no avanzó (ff-only falló)"
fi
TS=$(date +%Y%m%d-%H%M)
SCOPE=housekeeping
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
git worktree add -b "$BRANCH" "$WT" origin/main
SCRATCH="$(dirname "$WT")"          # scratch de esta corrida (no /tmp compartido)
HK="$WT/subsystem/housekeeping/scripts"
echo "WT=$WT  BRANCH=$BRANCH  SCRATCH=$SCRATCH"
```

## Fase 1 — Recopilar estado de todos los repos (una sola pasada paralela)

Las Fases 1.1, 1.2, 4.2 y 4.4 comparten **una** recolección paralela (8 repos a la vez, ~20 s en total
en vez de ~5 min en serie). No iterar repo por repo con `gh pr view` / `git cherry`.

```bash
"$HK/hk-scan.sh" "$SCRATCH/scan" "$WT/subsystem/housekeeping/memory/comentarios-vistos.jsonl"
# por repo en $SCRATCH/scan/<slug>/ (slug = ruta relativa a $HOME con / → __):
#   git.tsv          rama, ahead, behind, dirty, stashes
#   prs.json         PRs open + cerrados (una llamada gh por repo, --limit 200)
#   gone.tsv         ramas [gone] ya clasificadas (subsumida | wip | revisar)   → Fase 4.2
#   comentarios.json comentarios humanos NUEVOS vs ledger, desde la última corrida → Fase 4.4
```

**Contar siempre desde los JSON, nunca a ojo:** p. ej. PRs abiertos =
`jq '[.[]|select(.state=="OPEN")]|length' "$SCRATCH"/scan/*/prs.json .../.secretary/prs.json`
(el glob `*/` no incluye `.secretary`; pasar esa ruta explícita). En el reporte, cada número sale de
un comando; si un dato no se pudo medir, escribir "no medido", no una cifra aproximada.

### 1.1 Estado git

Sale de `git.tsv` (rama, ahead/behind, dirty, stashes). Con `git fetch --prune` ya hecho por el script.

### 1.2 PRs abiertos

Sale de `prs.json`, filtrando `state=="OPEN"`.

Clasificar cada PR:
- **PRs automáticos** (rama matchea `^(correo|reuniones|whatsapp|wiki|housekeeping)/auto-`): ¿tiene comentarios sin resolver? ¿está listo para merge? ¿hace cuánto se creó?
- **PRs manuales**: listar para visibilidad.
- **PRs stale** (>7 días sin actividad): flaggear.

### 1.3 CLAUDE.md existentes

Verificar si existe `CLAUDE.md` en la raíz del repo. Si no existe y el repo tiene >10 archivos de código, marcar como "candidato para CLAUDE.md".

### 1.4 `.gitignore` existente

Verificar si existe `.gitignore` en la raíz. Detectar si hay directorios típicos de build artifacts sin ignorar (`build/`, `dist/`, `output/`, `node_modules/`, `__pycache__/`, `*.pyc`, binarios Go).


## Fase 2 — Procesar CLAUDE.md reviews

Leer todos los archivos en `~/.claude/reviews/claudemd-review-*.md`.

Para cada review:
1. **Leer el contenido** del review.
2. **Si dice "Sin cambios necesarios"** → **antes de borrar**, registrar una línea de auditoría (archivo[s] de CLAUDE.md revisado[s] + veredicto + razón en ≤1 frase) para incluirla en el reporte (ver Fase 5, sección "CLAUDE.md — reviews sin cambios"). Luego borrar el archivo y continuar. El review en sí es scratch efímero; lo que debe persistir es el rastro de *que se revisó X y se decidió no tocar*, porque `~/.claude/reviews/` no está bajo git y un conteo agregado no responde "¿se revisó esto o nunca se miró?".
3. **Si propone cambios**, evaluar cada propuesta:
   - **Cambios seguros** (agregar convención nueva, actualizar estructura documentada, corregir info obsoleta): **aplicar directamente** al CLAUDE.md correspondiente. Estos son cambios de documentación, no de código.
   - **Cambios que requieren juicio** (eliminar una convención, cambiar una regla de negocio, reorganizar secciones): **no aplicar**, reportar para Álvaro.
4. **Borrar el archivo de review** tras procesarlo (aplicado o reportado).

**Regla de oro**: ante la duda, no aplicar — reportar. Es preferible que un cambio espere a que se aplique mal.

## Fase 3 — Consolidar memorias

Leer `~/.claude/projects/-Users-alvaromur-Cowork/memory/MEMORY.md` y todos los archivos `.md` referenciados.

Chequeos:
1. **Memorias duplicadas**: ¿hay dos archivos que dicen esencialmente lo mismo? → mergear en uno, borrar el otro, actualizar MEMORY.md.
2. **Memorias stale**: ¿alguna hace referencia a archivos/funciones/estados que ya no existen? → verificar contra el estado actual del código. Si está obsoleta, actualizar o borrar.
3. **MEMORY.md desactualizado**: ¿hay archivos `.md` en el directorio de memoria que no están indexados en MEMORY.md? → agregar. ¿Hay entradas en MEMORY.md cuyo archivo no existe? → borrar la entrada.
4. **Líneas >150 chars en MEMORY.md**: truncar o reformular.

Solo aplicar cambios que sean claramente correctos. Reportar los ambiguos.

## Fase 3.5 — Reconciliación de acciones (spec 007)

Barrido diario de `extractors/*/memory/acciones.md` contra evidencia externa. **Solo se aplican por sí mismos los tres casos de "Aplicación automática acotada" (abajo), vía `secretary acc fold` en el worktree del PR de housekeeping — nunca directo a `main`.** Todo lo demás se reporta como propuesta en el PR y, si aplica, en `subsystem/housekeeping/memory/acc-reconciliation-YYYYMMDD.md`.

> No hardcodear la ruta ni la forma de `acciones.md`: resolverla con `secretary config path` / `secretary acc fold` (el archivo se está partiendo en piezas más pequeñas y su layout cambiará). Las cerradas fuera de retención viven en `acciones/archivo/YYYY-MM.md`: para consultar un id que no está en el activo usa `secretary acc show <acc-id>`; `secretary acc fold` sobre un id archivado falla a propósito.

### Alcance

Acciones con `estado` ∈ `{abierta, en-curso, pendiente}` y `dueño` ∈ `{mía, compartida}` en los últimos **45 días** de `detectado` (ignorar backfill histórico salvo flag explícito).

### Reglas de caducidad (proponer `caducada`)

| Condición | `evidencia_cierre` propuesta |
|-----------|------------------------------|
| `deadline` < hoy − 14 días, sin `[update]` ni `sec-status` en brief reciente | `manual:housekeeping-caducidad` |
| `deadline` < `detectado` (nació muerta) | `manual:housekeeping-nacio-muerta` |
| `tipo: idea` con deadline vencido >30d | `manual:housekeeping-idea-stale` |

### Aplicación automática acotada

Housekeeping **aplica** (no solo propone) exactamente estos tres casos, dentro de su PR diario:

| Caso | Condición |
|------|-----------|
| **Nació muerta** | `deadline` < `detectado` |
| **Idea vencida** | `tipo: idea` con `deadline` vencido >30 días |
| **Evento-sesión vencido** | Acción atada a una sesión/reunión/entrevista con `deadline` vencido >30 días, sin `[update]` ni `sec-status` en ningún brief |

Antes de aplicar un **evento-sesión**, verificar que el evento **no ocurrió**: carpeta en
`Cowork/*/proyectos/**/entrevistas/` o resumen en `extractors/meetings/summaries/` (±2 días del
deadline). Si hay rastro de que ocurrió → no caducar; pasa a "Proponer cerrar".

Si una acción cita un PR como evidencia (cualquier regla), **comprobar que el título del PR
corresponde a la acción** (`gh pr view <n> --json title`). Un número de PR que aparece en un brief no
prueba nada si el tema es otro (error real del 2026-09-20: una acción citaba el número de un PR de otro tema).

**Guard (obligatorio, por acción):** leer el `estado:` actual del bloque canónico en el worktree y
llamar a `fold` **solo** si es `abierta`, `en-curso` o `pendiente`. Si ya está cerrada, saltarla sin
error (no es un candidato).

**Tope: máximo 10 aplicaciones por corrida.** Del candidato 11 en adelante no se aplica: pasa a
"Proponer caducar" con la nota `tope de 10 alcanzado`, y el tope alcanzado va a "🔴 Atención primero"
como 🟡. Si `fold` devuelve error, no cuenta para el tope y la acción se reporta como "Conflicto".

```bash
# desde $WT; una llamada por acc-id; candidatos ya verificados
export SECRETARY_INSTANCE="$WT" SEC_ACC_ESTADO=caducada
ACC="$(secretary config path meetings.memory)/acciones.md"   # no hardcodear: el layout cambiará
APLICADAS=0
for entry in "<acc-id> <etiqueta-evidencia> [YYYY-MM-DD]" ...; do
  set -- $entry; id=$1
  actual=$(awk -v h="## $id" '$0==h{f=1;next} f&&/^- estado:/{sub(/^- estado: */,"");print;exit} /^## /{f=0}' "$ACC")
  case "$actual" in abierta|en-curso|pendiente) ;; *) continue ;; esac      # guard
  [ "$APLICADAS" -ge 10 ] && { echo "tope alcanzado: $id → propuesta"; continue; }   # tope
  if secretary acc fold "$@"; then APLICADAS=$((APLICADAS+1)); else echo "fold falló: $id → conflicto"; fi
done
#   etiquetas: manual:housekeeping-nacio-muerta | manual:housekeeping-idea-stale | manual:housekeeping-evento-vencido
```

Todo lo demás (caducidad por deadline >14d en acciones que no son evento-sesión, cierres `hecha`,
conflictos) **sigue como propuesta**. Lo aplicado se lista en el reporte como "Aplicado".

### Reglas de cierre (proponer `hecha`)

| Evidencia | Condición |
|-----------|-----------|
| Brief `sec-status` ✅ para el `acc-id` | Cerrar — `sec-status` |
| Calendario | Acción de scheduling (agendar/coordinar/confirmar reunión) con evento match en ±2d (`gog calendar`, barrido multi-calendario) — misma lógica que briefing Fase 2.1 |
| Correo | Ítem en `extractors/mail/state.md` o PR `correo/auto-*` marca enviado/cancelado para el mismo hilo |
| PR mergeado | `acc-id` en body del PR o heartbeat `🔗 linked` — aplicar vía `sec-acc-fold.sh` (sec-merge / sesión) |
| Reunión posterior | Resumen en `extractors/meetings/summaries/` posterior al `detectado` cierra explícitamente el `acc-id` |

### Salida en reporte (Fase 5)

Sección **🔄 Reconciliación acciones (007)** con tablas:

- **Aplicado** (acc-id, caso, evidencia) — lo de "Aplicación automática acotada"
- **Proponer caducar** (acc-id, motivo, deadline)
- **Proponer cerrar** (acc-id, evidencia path)
- **Conflicto** (acc-id, fuente A vs fuente B — para heartbeat/briefing)

**Solo delta:** listar únicamente las acciones que entraron a "vencidas" desde el último
`acc-reconciliation-*.md` (comparar acc-id contra el más reciente). Las que ya estaban en ese
archivo se resumen en una línea con el conteo y el enlace al archivo previo; no repetir la tabla
completa cada día. Si el delta es 0, el bloque queda en una línea y no cuenta como "algo que decidir".

Álvaro o una sesión de `reuniones-update` / `sec-status` / **`sec-acc-fold`** (post-merge en
`sec-merge`) aplica el resto de cierres. Housekeeping aplica solo el bloque acotado de arriba.

> **Nota (2026-07-27):** el automatismo de `knowledge/catalog/automatismos.md` (proyecto+persona,
> enviar/actualizar-acta/enviar-resumen/compartir-transcripcion) vivió acá brevemente por
> conveniencia de código adyacente (esta fase ya tocaba `acciones.md`) — se movió a
> `secretary-briefing` § "Automatismos de catálogo" porque el bounded context de housekeeping es
> higiene del ecosistema de repos, no seguimiento de comunicaciones/reuniones. No reintroducir aquí.

## Fase 3.6 — Issues de backlog vs specs (rules/issues-relacionados.md)

Backstop periódico: issues abiertos que referencian un spec bajo `_diseño/specs/` pueden quedar
stale en silencio si el spec avanzó (merge de un PR) pero nadie volvió a tocar el issue. Caso
origen: #433 quedó abierto 2 días después de que PR #459 resolviera la mayoría de sus checkboxes.

### Alcance

Issues abiertos hace **>7 días** cuyo body menciona un path `_diseño/specs/**/spec.md`.

### Detección

```bash
gh issue list --repo <owner/repo> --search "_diseño/specs in:body" --state open --json number,title,updatedAt,body
# para cada match: extraer el path del spec referenciado y comparar
git log -1 --format=%cI -- "<path-del-spec>"   # última modificación del spec
```

Si la última modificación del spec es **posterior** al último comentario/update del issue →
flaggear como candidato a revisión (no cerrar automáticamente — housekeeping solo propone).

### Salida en reporte (Fase 5)

Sección **📎 Issues vs specs (backstop 3.6)**: tabla `issue | spec referenciado | último update issue | último cambio spec | acción sugerida`. Álvaro o la sesión que retome el tema decide (comentar/cerrar/dejar así), igual que en 3.5.

## Fase 4 — Acciones seguras de organización

### 4.1 Archivos sin commitear en repos de gestión

Para `.secretary`, `Cowork/inspiro`, `Cowork/ennui`:
- Si hay archivos dirty que son claramente output de una routine (en `memory/`, `summaries/`, etc.) y la routine debería haberlos commiteado: **reportar como anomalía** (la routine falló en su cierre).
- Si hay archivos dirty que parecen trabajo manual de Álvaro (borradores, notas): **no tocar**, solo listar.

### 4.2 Ramas huérfanas

Ya clasificadas por `hk-scan.sh` → `gone.tsv` de cada repo (rama \t clase \t detalle). No reimplementar
con `git cherry` (el squash cambia el SHA y los shas multilínea rompían el bucle).

Cómo clasifica `hk-gone.py`:
1. PR **mergeado** cuyo `headRefOid` == tip local → **subsumida** (definitivo, sin diff).
2. PR mergeado con otro tip → un archivo cuenta como WIP solo si difiere de `main` **y** `main` no lo
   modificó después de `mergedAt` (los archivos de estado —`state.md`, `latest.json`, `_procesados.jsonl`—
   los reescribe cada rutina; que difieran es evolución, no WIP).
3. Sin PR / PR cerrado sin merge → comparación por contenido de todos los archivos.

- **subsumida** → segura de podar. Dar el comando listo: `git branch -D <rama>` (force, porque el squash impide `-d`).
- **wip** → hay contenido que `main` no tiene. Reportar con el detalle de `gone.tsv`; acción: abrir rama nueva desde `origin/main` + PR para ese WIP ANTES de podar. Es "candidata a revisar", no urgencia, salvo que el archivo sea de trabajo manual de Álvaro.
- **revisar** → sin merge-base u otro caso raro; mirar a mano.

Reportar **conteos por clase y por repo** + solo las `wip`; listar las subsumidas como un bloque `git branch -D` (o el `.tsv` en `subsystem/housekeeping/memory/ramas-podables-YYYYMMDD.tsv`), no una a una en el cuerpo.

No borrar automáticamente en ningún caso — solo clasificar y proponer (las ramas con WIP pueden tener trabajo no pusheado).


### 4.3 PRs auto acumulados

Si hay PRs automáticos (correo/reuniones/whatsapp) con >3 días sin mergear y sin comentarios, **reportar con urgencia**: se acumulan y las routines pueden reprocesar trabajo.

### 4.4 Comentarios sueltos en PRs (sobre todo cerrados/mergeados)

Los comentarios en PRs **ya mergeados o cerrados** se pierden de vista y a veces contienen feedback para
mejorar una rutina o trabajo pendiente. `hk-scan.sh` ya los trajo: 2 llamadas por repo
(`issues/comments?since=` + `pulls/comments?since=`), no 2 por PR. `since` = última corrida − 2 días
(tope 45 días), excluye marcas del agente (`agent-generated`, `claude-generated`, footers `🤖 _Generado por`
/ `🤖 _Secretary —`) y ya descuenta lo que está en el ledger → `comentarios.json` de cada repo es la lista
de **nuevos**.

Sobre esa lista, **surfacear** los que parezcan feedback accionable (`TODO`, `FIXME`, `pendiente`, `falta`,
`continuar`, `mejorar`, `revisar`, `ojo`, `para la próxima`, pregunta sin responder, o cualquier comentario
sustantivo en un PR **mergeado/cerrado**). Los que son notas de sesión sin marca ("Rebase sobre origin/main…",
"Superado por #N") no son feedback: registrarlos en el ledger sin reportarlos.

**Ledger** `subsystem/housekeeping/memory/comentarios-vistos.jsonl` (`{"id","pr","repo","fecha_visto"}`):
tras reportar, **agregar** los IDs nuevos y **podar a 60 días** (la ventana de escaneo es ≤45 d, así que
más antiguo no vuelve a aparecer). Va en el commit del PR de housekeeping.

```bash
jq -c --arg c "$(date -v-60d +%Y-%m-%d)" 'select(.fecha_visto>=$c)' "$LEDGER" > "$LEDGER.tmp" && mv "$LEDGER.tmp" "$LEDGER"
```

Reportar los nuevos en la sección correspondiente de Fase 5. Si encuentras feedback claramente sobre una rutina, indicarlo (`→ feedback para rutina X`).


## Fase 5 — Reporte como PR

El reporte sigue el **contrato de output expresivo** de Álvaro
(`~/.secretary/rules/sec-output.md`): cabecera con emoji+label, **lead con lo
urgente primero**, flags de estado de set cerrado, campos marcados. No es un volcado de tablas:
se abre con lo que requiere decisión tuya y recién después el detalle escaneable.

- **Cabecera:** `🩺 **Housekeeping — YYYY-MM-DD** · salud del ecosistema`
- **Flags de estado (set cerrado, no inventar):** 🔴 bloqueado/urgente · 🟡 atención/pendiente ·
  🟢 ok/activo · ⚠️ stale/cuidado · 🔎 gap/falta · ✅ hecho · → acción sugerida
- **Un marcador por fila como máximo.** El emoji marca, no decora.

**Firma:** antes de escribir el reporte, genera marca y footer con `_firma.md` / `sec-signature.sh housekeeping`.

Escribir el reporte a `$SCRATCH/pr-housekeeping.md` con esta estructura:

```markdown
<!-- primera línea: salida de sec-signature.sh housekeeping --mark -->
🩺 **Housekeeping — YYYY-MM-DD** · salud del ecosistema

## 🔴 Atención primero

Lo que requiere decisión o acción tuya, ordenado por urgencia — esto es lo primero que Álvaro
lee; el resto del reporte es detalle de respaldo. Cada ítem: flag + qué + → acción sugerida.
Si no hay nada, una sola línea: `🟢 Nada urgente — todo en verde.`

- 🔴 [lo más urgente — bloqueante o con deadline] → [acción concreta]
- 🟡 [pendiente que conviene atender] → [acción]
- ⚠️ [stale / cuidado] → [acción]

## Estado de repos

| Repo | Rama | Ahead | Behind | Dirty | Stashes | CLAUDE.md | .gitignore |
|------|------|-------|--------|-------|---------|-----------|---------|
| ... | ... | ... | ... | ... | ... | ✅/❌ | ✅/❌ |

## PRs pendientes

### ⚠️ PRs auto acumulados (mergear pronto)
- [PR #N](url) — `correo/auto-...` — creado hace X días, sin comentarios

### PRs manuales abiertos
- [PR #N](url) — título — última actividad hace X días

### PRs stale (>7 días)
- ...

### 💬 Comentarios sueltos sin atender (nuevos)
Feedback humano en PRs (sobre todo cerrados/mergeados) que se pierde de vista. Excluye los generados por el agente. Solo nuevos vs. ledger.
- [repo #N](url-del-comentario) — *"<extracto del comentario>"* — @autor, PR mergeado hace X días → feedback para rutina Y / pendiente de continuar
- ...

## CLAUDE.md — cambios aplicados

- `~/Dev/inspiro-agents/CLAUDE.md` — agregada sección de estructura de directorios
- ...

## CLAUDE.md — cambios que requieren decisión

- `~/Dev/doc2struct/CLAUDE.md` — propuesta: eliminar convención X porque... → **decidir**

## CLAUDE.md — reviews sin cambios (rastro de auditoría)

Una línea por review "Sin cambios necesarios" procesado (el archivo de review ya fue borrado; esto es lo que persiste). Sirve para responder después "¿se revisó esto o nunca se miró?".

- `~/.secretary/extractors/whatsapp/*`, `memory/*` — review de salidas de `whatsapp-monitor` → sin cambios (datos generados, sin convención nueva)
- ...

## 🔄 Reconciliación acciones (007)

Propuestas de caducidad/cierre desde Fase 3.5 (no aplicadas automáticamente a `acciones.md`).

| acc-id | propuesta | evidencia |
|--------|-----------|-----------|
| acc-… | caducar / cerrar | regla 007 + path |

## 📎 Issues vs specs (backstop 3.6)

Candidatos detectados en Fase 3.6 — spec cambió después del último update del issue que lo trackea.

| issue | spec referenciado | último update issue | último cambio spec | acción sugerida |
|-------|--------------------|----------------------|----------------------|-----------------|
| #… | `_diseño/specs/.../spec.md` | fecha | fecha | revisar / comentar / cerrar |

## Repos sin CLAUDE.md (candidatos)

- `~/Dev/secretary-core/` — 19 archivos, repo activo → crear CLAUDE.md
- ...

## Repos sin .gitignore (con artifacts detectados)

- `~/.secretary/` — `wiki/build/`, `knowledge/wiki/output/` son generados
- ...

## Memoria

### Cambios aplicados
- Mergeado `memory_x.md` con `memory_y.md` (duplicados)
- Actualizado MEMORY.md: agregada entrada para `z.md`

### Requiere decisión
- `project_foo.md` referencia archivo que ya no existe → ¿borrar o actualizar?

## Archivos sin commitear

### Anomalías de routines
- `secretary/extractors/mail/memory/2026-05-20.md` — dirty pero debería estar en un PR

### Trabajo manual (no tocar)
- `inspiro/clientes/mi-fondo/borrador.md`

## Ramas candidatas a limpieza

- `doc2struct`: `fix/old-branch` (mergeada, 45 días sin actividad)
- ...

## Resumen ejecutivo

- 🟢/🟡/🔴 una línea de salud global del ecosistema
- X repos revisados · X PRs pendientes (Y 🔴 urgentes)
- X cambios de CLAUDE.md aplicados, Z pendientes de decisión
- X memorias consolidadas
- Próxima corrida: mañana 06:00

---
<!-- última línea: salida de sec-signature.sh housekeeping --footer -->
```

**Reglas del reporte expresivo:**
- **Lead con lo urgente.** La sección `## 🔴 Atención primero` va arriba de todo, antes de la
  tabla de estado. Es el resumen accionable; lo demás es respaldo.
- **Flags del set cerrado.** No inventar emojis ad-hoc para estados (ver lista en la cabecera de
  esta fase).
- **Procedencia inline** donde aplique: `` · `repo:rama` `` o link al PR/comentario.

## Cierre — PR solo si hay algo que decidir (spec 024)

Separa **nada urgente** (ambient / sin PR) de **hay algo que decidir** (PR).

**Hay algo que decidir** si ocurre al menos uno de:
- En `## 🔴 Atención primero` hay ≥1 ítem con flag 🔴 / 🟡 / ⚠️ (no la línea sola `🟢 Nada urgente — todo en verde.`).
- Hay cambios versionables en el worktree de secretary que Álvaro debe ver (ledger de comentarios, consolidación de memoria, propuesta de reconciliación escrita, etc.).

**Nada urgente** = lead en verde **y** sin diffs versionables (o solo ruido que no merece review). Entonces: **no** abrir PR, **no** usar `--allow-empty`. Echo de cierre + limpiar worktree/rama. Mismo criterio porcelain que `tidy-up` / `revision-correo` / `wiki-update`.

Si el único diff es un store de higiene ambient (p. ej. ledger `comentarios-vistos.jsonl` sin ítems nuevos que decidir): commit+push **directo a `main`** desde el checkout principal (tier ambient, precedente heartbeat / tidy-up), sin PR.

```bash
cd "$WT"
REPO=~/.secretary
HAY_DECIDIR=0
# Heurística: el body ya generado marca decisión
if ! grep -q '🟢 Nada urgente — todo en verde' "$SCRATCH/pr-housekeeping.md" 2>/dev/null; then
  HAY_DECIDIR=1
fi
# O hay archivos versionables más allá de scratch
if [ -n "$(git status --porcelain)" ]; then
  HAY_DECIDIR=1
fi

if [ "$HAY_DECIDIR" = "0" ]; then
  echo "Nada urgente / sin cambio de fondo — no se abre PR."
  cd "$REPO"
  git worktree remove "$WT" --force 2>/dev/null || true
  git branch -D "$BRANCH" 2>/dev/null || true
  exit 0
fi

git add -A
if [ -z "$(git status --porcelain)" ]; then
  # Solo reporte (cambios fuera de secretary, p. ej. CLAUDE.md ajenos) pero SÍ hay decisión
  # Escribe el body al worktree para que el PR tenga diff:
  mkdir -p subsystem/housekeeping/memory
  cp "$SCRATCH/pr-housekeeping.md" "subsystem/housekeeping/memory/housekeeping-$(date +%Y%m%d).md"
  git add subsystem/housekeeping/memory/
fi
git commit -m "chore(housekeeping): revisión diaria $(date +%Y-%m-%d)"
git push -u origin "$BRANCH"
gh label create "hilo:housekeeping" --description "Mantenimiento diario del ecosistema" --color E6E6FA 2>/dev/null || true
gh pr create --title "chore(housekeeping): revisión diaria $(date +%Y-%m-%d)" \
  --label "hilo:housekeeping" --body-file "$SCRATCH/pr-housekeeping.md"
cd "$REPO" && git worktree remove "$WT" --force
```

- **No** `--allow-empty`. Si no hay decisión y no hay diff → sin PR.
- Si hay cambios en memorias dentro de secretary (consolidación), esos van en el commit del PR (o ambient si no hay nada que decidir).
- El body del PR (y **cualquier comentario** que postee la rutina) lleva firma vía `sec-signature.sh housekeeping` (ver `_firma.md`).
- Devolver la **URL del PR** al final (solo si abriste uno).
- **Haptics** (ver `~/.secretary/rules/sec-haptics.md`): al entregar el PR, dejar
  señal `📬 _secretary entregó — housekeeping <fecha>, <n> ítems en "Atención primero"_`. Si la
  corrida detectó algo que reclama decisión (rama con WIP huérfano, PR auto acumulado, anomalía
  de rutina), súbelo a tier **notice**: `💡 _secretary detectó — <qué>_`. El brief diario es
  quien rutea esos hallazgos a tu lista; housekeeping solo los marca con su flag y los señala.
  Corrida en verde sin PR: haptic ambient opcional `🫧 _secretary housekeeping — nada urgente_`.

## Qué NO hacer

- No commitear archivos en repos ajenos a secretary — los cambios a CLAUDE.md se hacen directamente en cada repo (son su propia rama `main`, documentación safe).
- No borrar ramas sin confirmación explícita de Álvaro.
- No mergear PRs automáticamente en esta routine (eso lo hace wiki-update en su W0).
- No modificar código, solo documentación (CLAUDE.md, .gitignore, memorias).
- No tocar archivos que parezcan trabajo en progreso de Álvaro.
- No inventar contenido para CLAUDE.md — solo aplicar lo que los reviews proponen, o reportar la ausencia.
