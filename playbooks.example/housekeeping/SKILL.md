---
name: housekeeping
description: Revisión diaria de higiene del ecosistema — CLAUDE.md reviews, memoria, PRs pendientes, archivos sin commitear. Organiza lo seguro y reporta lo que necesita decisión humana.
---

# housekeeping — Mantenimiento diario del ecosistema de repos

Rutina que corre 1×/día (06:00 Lima) y revisa el estado de higiene de todos los repos y workspaces de User. Aplica cambios seguros automáticamente y reporta todo lo que requiere decisión humana como PR en `~/.secretary`.

## Repos a revisar

```bash
REPOS=(
    # Productos técnicos (Dev/)
    "$HOME/Dev/doc2struct"
    "$HOME/Dev/doc2struct/doc2struct-go"
    "$HOME/Dev/doc2struct/aliantza-compras-python"
    "$HOME/Dev/doc2struct/doc2struct_eval"
    "$HOME/Dev/Company-agents-web"
    "$HOME/Dev/sideproject-agents/sideproject-agents-core"
    "$HOME/Dev/sideproject-agents/ruta-web"
    "$HOME/Dev/secretary-core"
    "$HOME/Dev/clab-erp"
    "$HOME/Dev/workwatch"
    "$HOME/Dev/cowork-drivesync"

    # Workspaces de gestión (Cowork/)
    "$HOME/.secretary"
    "$HOME/Cowork/Company"
    "$HOME/Cowork/sideproject"
)
```

## W. WORKTREE AISLADO (hacer ANTES que nada)

Trabaja en un worktree de `~/.secretary` (es donde vive el reporte). Los cambios a CLAUDE.md de otros repos se hacen directamente en esos repos (son safe: solo documentación).

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=housekeeping
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
git worktree add -b "$BRANCH" "$WT" origin/main
echo "WT=$WT  BRANCH=$BRANCH"
```

## Fase 1 — Recopilar estado de todos los repos

Para cada repo en `$REPOS`:

### 1.1 Estado git

```bash
cd "$dir"
git fetch --quiet 2>/dev/null
AHEAD=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
BEHIND=$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "?")
DIRTY=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
BRANCH_NAME=$(git branch --show-current 2>/dev/null)
STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')
```

Registrar: nombre del repo, rama actual, ahead/behind, dirty count, stashes.

### 1.2 PRs abiertos

Para repos con remote en GitHub:

```bash
cd "$dir"
gh pr list --state open --json number,title,headRefName,updatedAt,createdAt,labels,reviewDecision 2>/dev/null
```

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
   - **Cambios que requieren juicio** (eliminar una convención, cambiar una regla de negocio, reorganizar secciones): **no aplicar**, reportar para User.
4. **Borrar el archivo de review** tras procesarlo (aplicado o reportado).

**Regla de oro**: ante la duda, no aplicar — reportar. Es preferible que un cambio espere a que se aplique mal.

## Fase 3 — Consolidar memorias

Leer `~/.claude/projects/-Users-username-Cowork/memory/MEMORY.md` y todos los archivos `.md` referenciados.

Chequeos:
1. **Memorias duplicadas**: ¿hay dos archivos que dicen esencialmente lo mismo? → mergear en uno, borrar el otro, actualizar MEMORY.md.
2. **Memorias stale**: ¿alguna hace referencia a archivos/funciones/estados que ya no existen? → verificar contra el estado actual del código. Si está obsoleta, actualizar o borrar.
3. **MEMORY.md desactualizado**: ¿hay archivos `.md` en el directorio de memoria que no están indexados en MEMORY.md? → agregar. ¿Hay entradas en MEMORY.md cuyo archivo no existe? → borrar la entrada.
4. **Líneas >150 chars en MEMORY.md**: truncar o reformular.

Solo aplicar cambios que sean claramente correctos. Reportar los ambiguos.

## Fase 3.5 — Reconciliación de acciones (spec 007)

Barrido diario de `extractors/*/memory/acciones.md` contra evidencia externa. **No mutar `acciones.md` desde housekeeping** (dominio de reuniones/whatsapp + `wiki-update`) — reportar propuestas en el PR y, si aplica, en `subsystem/housekeeping/memory/acc-reconciliation-YYYYMMDD.md`.

### Alcance

Acciones con `estado` ∈ `{abierta, en-curso, pendiente}` y `dueño` ∈ `{mía, compartida}` en los últimos **45 días** de `detectado` (ignorar backfill histórico salvo flag explícito).

### Reglas de caducidad (proponer `caducada`)

| Condición | `evidencia_cierre` propuesta |
|-----------|------------------------------|
| `deadline` < hoy − 14 días, sin `[update]` ni `sec-status` en brief reciente | `manual:housekeeping-caducidad` |
| `deadline` < `detectado` (nació muerta) | `manual:housekeeping-nacio-muerta` |
| `tipo: idea` con deadline vencido >30d | `manual:housekeeping-idea-stale` |

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

- **Proponer caducar** (acc-id, motivo, deadline)
- **Proponer cerrar** (acc-id, evidencia path)
- **Conflicto** (acc-id, fuente A vs fuente B — para heartbeat/briefing)

User o una sesión de `reuniones-update` / `sec-status` / **`sec-acc-fold`** (post-merge en
`sec-merge`) aplica los cierres. Housekeeping solo propone.

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

Sección **📎 Issues vs specs (backstop 3.6)**: tabla `issue | spec referenciado | último update issue | último cambio spec | acción sugerida`. User o la sesión que retome el tema decide (comentar/cerrar/dejar así), igual que en 3.5.

## Fase 4 — Acciones seguras de organización

### 4.1 Archivos sin commitear en repos de gestión

Para `.secretary`, `Cowork/Company`, `Cowork/sideproject`:
- Si hay archivos dirty que son claramente output de una routine (en `memory/`, `summaries/`, etc.) y la routine debería haberlos commiteado: **reportar como anomalía** (la routine falló en su cierre).
- Si hay archivos dirty que parecen trabajo manual de User (borradores, notas): **no tocar**, solo listar.

### 4.2 Ramas huérfanas

Para cada repo, listar ramas locales que:
- No tienen remote tracking (`gone`)
- Fueron mergeadas a main
- Tienen >30 días sin commits

**Clasificar cada rama `[gone]` por CONTENIDO, no por SHA** — `git branch --merged` miente cuando el PR se mergeó por *squash* (el commit aplastado tiene otro SHA, así que la rama parece "no mergeada" aunque su contenido ya esté en main). Para cada rama `[gone]`:

```bash
# Commits de la rama que NO están en main por contenido (no por SHA):
git cherry -v origin/main <rama>          # '-' = contenido ya en main; '+' = revisar
# Para los '+', verificar por contenido real (el squash deja '+' aunque esté en main):
for c in <shas-con-+>; do
  git show --name-only --format="" "$c" | while read -r f; do
    [ -n "$f" ] && git diff --quiet origin/main <rama> -- "$f" || echo "WIP no en main: $f"
  done
done
```

- **Subsumida** (todo `-`, o los `+` resultan idénticos a main por contenido) → segura de podar. Dar el comando listo: `git branch -D <rama>` (force, porque el squash impide `-d`).
- **Con WIP sin salvar** (algún archivo difiere de main) → **reportar con urgencia**: hay trabajo huérfano sobre una rama muerta. Acción: abrir rama nueva desde `origin/main` + PR para ese WIP ANTES de podar. Nunca proponer borrarla sin rescatar.

No borrar automáticamente en ningún caso — solo clasificar y proponer (las ramas con WIP pueden tener trabajo no pusheado).

### 4.3 PRs auto acumulados

Si hay PRs automáticos (correo/reuniones/whatsapp) con >3 días sin mergear y sin comentarios, **reportar con urgencia**: se acumulan y las routines pueden reprocesar trabajo.

### 4.4 Comentarios sueltos en PRs (sobre todo cerrados/mergeados)

Los comentarios en PRs **ya mergeados o cerrados** se pierden de vista, y a veces contienen feedback para mejorar una rutina o trabajo pendiente que hay que continuar en ese repo. Escanearlos.

Para cada repo GitHub:

```bash
cd "$dir"
# PRs cerrados/mergeados de los últimos 45 días + PRs abiertos
gh pr list --state all --limit 60 --json number,state,title,closedAt,url --jq \
  '.[] | select(.state=="OPEN" or (.closedAt and (.closedAt | fromdateiso8601) > (now - 45*86400)))'
# Para cada PR, traer comentarios de issue y de review:
gh pr view <N> --json comments --jq '.comments[] | {author:.author.login, body:.body, url:.url}'
gh api repos/{owner}/{repo}/pulls/<N>/comments --jq '.[] | {author:.user.login, body:.body, url:.html_url}'
```

Reglas de filtrado:
1. **Excluir los comentarios generados por el agente**: marcas `<!-- agent-generated:... -->` o legacy `<!-- claude-generated:... -->`, o footers `🤖 _Generado por` / `🤖 _Secretary —`. No son feedback humano (ver `_firma.md` y `~/.claude/CLAUDE.md`).
2. De los humanos restantes, **surfacear** los que parezcan feedback accionable: contienen señales como `TODO`, `FIXME`, `pendiente`, `falta`, `continuar`, `mejorar`, `revisar`, `ojo`, `para la próxima`, una pregunta sin responder, o cualquier comentario sustantivo en un PR **mergeado/cerrado** (donde ya nadie lo va a ver).
3. **No repetir**: cruzar contra el ledger `~/.secretary/subsystem/housekeeping/memory/comentarios-vistos.jsonl` (un objeto por línea: `{"id":<comment_id>,"pr":<n>,"repo":"...","fecha_visto":"..."}`). Reportar solo los que no estén en el ledger; tras reportar, **agregar sus IDs al ledger** (ese archivo sí va en el commit del PR de housekeeping).

Reportar los nuevos en la sección correspondiente de Fase 5. Si encuentras feedback claramente sobre una rutina, indicarlo (`→ feedback para rutina X`).

## Fase 5 — Reporte como PR

El reporte sigue el **contrato de output expresivo** de User
(`~/.secretary/rules/sec-output.md`): cabecera con emoji+label, **lead con lo
urgente primero**, flags de estado de set cerrado, campos marcados. No es un volcado de tablas:
se abre con lo que requiere decisión tuya y recién después el detalle escaneable.

- **Cabecera:** `🩺 **Housekeeping — YYYY-MM-DD** · salud del ecosistema`
- **Flags de estado (set cerrado, no inventar):** 🔴 bloqueado/urgente · 🟡 atención/pendiente ·
  🟢 ok/activo · ⚠️ stale/cuidado · 🔎 gap/falta · ✅ hecho · → acción sugerida
- **Un marcador por fila como máximo.** El emoji marca, no decora.

**Firma:** antes de escribir el reporte, genera marca y footer con `_firma.md` / `sec-signature.sh housekeeping`.

Escribir el reporte a `/tmp/pr-housekeeping.md` con esta estructura:

```markdown
<!-- primera línea: salida de sec-signature.sh housekeeping --mark -->
🩺 **Housekeeping — YYYY-MM-DD** · salud del ecosistema

## 🔴 Atención primero

Lo que requiere decisión o acción tuya, ordenado por urgencia — esto es lo primero que User
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

- `~/Dev/Company-agents/CLAUDE.md` — agregada sección de estructura de directorios
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
- `Company/clientes/mi-fondo/borrador.md`

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

## Cierre — Commit + PR

```bash
cd "$WT"
if [ -z "$(git status --porcelain)" ]; then
  echo "Sin cambios en secretary — PR solo con reporte."
fi
git add -A
git commit -m "chore(housekeeping): revisión diaria $(date +%Y-%m-%d)" --allow-empty
git push -u origin "$BRANCH"
gh label create "hilo:housekeeping" --description "Mantenimiento diario del ecosistema" --color E6E6FA 2>/dev/null || true
gh pr create --title "chore(housekeeping): revisión diaria $(date +%Y-%m-%d)" \
  --label "hilo:housekeeping" --body-file /tmp/pr-housekeeping.md
cd "$REPO" && git worktree remove "$WT" --force
```

- Usar `--allow-empty` porque a veces los únicos cambios son a CLAUDE.md de otros repos (fuera de este worktree) y el reporte es lo que importa.
- Si hay cambios en memorias dentro de secretary (consolidación), esos sí van en el commit.
- El body del PR (y **cualquier comentario** que postee la rutina) lleva firma vía `sec-signature.sh housekeeping` (ver `_firma.md`).
- Devolver la **URL del PR** al final.
- **Haptics** (ver `~/.secretary/rules/sec-haptics.md`): al entregar el PR, dejar
  señal `📬 _secretary entregó — housekeeping <fecha>, <n> ítems en "Atención primero"_`. Si la
  corrida detectó algo que reclama decisión (rama con WIP huérfano, PR auto acumulado, anomalía
  de rutina), súbelo a tier **notice**: `💡 _secretary detectó — <qué>_`. El brief diario es
  quien rutea esos hallazgos a tu lista; housekeeping solo los marca con su flag y los señala.

## Qué NO hacer

- No commitear archivos en repos ajenos a secretary — los cambios a CLAUDE.md se hacen directamente en cada repo (son su propia rama `main`, documentación safe).
- No borrar ramas sin confirmación explícita de User.
- No mergear PRs automáticamente en esta routine (eso lo hace wiki-update en su W0).
- No modificar código, solo documentación (CLAUDE.md, .gitignore, memorias).
- No tocar archivos que parezcan trabajo en progreso de User.
- No inventar contenido para CLAUDE.md — solo aplicar lo que los reviews proponen, o reportar la ausencia.