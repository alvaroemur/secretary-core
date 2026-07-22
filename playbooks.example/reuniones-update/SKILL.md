---
name: reuniones-update
description: >-
  Process new Tactiq transcriptions from Google Drive, generate structured summaries,
  and leave evidence in meetings memory for wiki-update to integrate.
---

Read instance `CLAUDE.md` at `SECRETARY_INSTANCE` before starting. Instance appendix:
`operational/briefing.md` (Google accounts, calendar reconciliation). Doctrine:
`rules/skills-contract.md`.

# reuniones-update — meeting processing orchestrator

The owner's meetings are auto-transcribed with Tactiq and appear as Google Docs in a Drive folder
(`TACTIQ_ROOT` — resolved from `$WT/extractors/meetings/memory/_drive_layout.json` →
`tactiq_root_id`). This routine collects new transcripts, groups fragments of the same call,
launches one subagent per meeting for isolated processing, consolidates results, and archives files
in Drive. Run output is delivered as a **Pull Request** that acts as the report: the owner reads it
on GitHub and merges.

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
WORK_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.inspiro // .accounts.work // empty')
MEETINGS_MEMORY="$(secretary config path meetings.memory)"
```

## W. Isolated worktree (do this first)

This run does **not** write to the main working copy. Work in an ephemeral worktree from
`origin/main` and open a PR at the end.

```bash
set -euo pipefail
REPO="$SECRETARY_INSTANCE"
cd "$REPO"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=reuniones
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
git worktree add -b "$BRANCH" "$WT" origin/main
MEETINGS_MEMORY="$WT/extractors/meetings/memory"
TACTIQ_ROOT=$(jq -r '.tactiq_root_id // empty' "$MEETINGS_MEMORY/_drive_layout.json" 2>/dev/null || true)
if [ -z "$TACTIQ_ROOT" ]; then
  echo "ERROR: tactiq_root_id missing in $MEETINGS_MEMORY/_drive_layout.json — seed from instance data before running."
  exit 1
fi
echo "WT=$WT  BRANCH=$BRANCH  TACTIQ_ROOT=$TACTIQ_ROOT"
```

**Path map:** wherever this document says `$MEETINGS_MEMORY` or `extractors/meetings/`, resolve
under `$WT/`. All writes (summaries, `memory/`, bookkeeping) go to `$WT/extractors/meetings/`.
Wiki context reads come from `$WT/knowledge/wiki/articulos/...` (fresh `main` checkout). When
preparing `resumen_path` for subagents, use absolute paths inside `$WT` (e.g.
`$WT/extractors/meetings/summaries/YYYY-MM-DD-slug.md`). Google Drive and Calendar are external;
Drive moves happen regardless.

> Operations: bookkeeping (`_procesados.jsonl`) lives in the PR, not on `main`. Merge PRs daily.
> Drive moves are persistent: even if a PR is not merged, moved files are not reprocessed.

## Strict write boundary

**Write only under `$WT/extractors/meetings/`** (the worktree). Never touch
`$WT/knowledge/wiki/`, `$WT/extractors/mail/`, or any other module folder. What reaches wiki is
decided by `wiki-update` consuming `$WT/extractors/meetings/memory/`.

Do not modify calendar entries or send mail.

## File layout

```
$WT/extractors/meetings/
├── memory/
│   ├── reuniones.md          ← consolidated log, one section per meeting, append-only
│   ├── personas.md           ← detected people (pendiente_wiki: false by default if new; true if enriching existing wiki entry)
│   ├── _glosario.md          ← owner-maintained ground truth (routine does NOT modify)
│   ├── organizaciones.md     ← detected orgs
│   ├── entidades.md          ← enriched topics/projects
│   ├── acciones.md           ← new actions + updates on existing actions
│   ├── _procesados.jsonl     ← bookkeeping: processed drive_ids
│   └── _drive_layout.json    ← cache of Drive subfolder IDs (includes tactiq_root_id)
└── summaries/
    └── YYYY-MM-DD-<slug>.md  ← one file per processed meeting
```

## Available tools

- **Google Drive**: MCP tools `search_files`, `read_file_content`, `get_file_metadata` (prefer `gog`
  CLI for listing and file ops when cheaper).
- **Calendar**: MCP `list_events` to enrich metadata. ⚠️ For Inspiro / Norte Compartido meetings
  (Arturo, Jorge), also scan the shared work calendar (`WORK_ACCOUNT`): `list_events` without
  `calendarId` only reads primary and will miss them. First `list_calendars`, then iterate relevant
  calendars (include `WORK_ACCOUNT`, reachable as owner from the personal account). See
  `operational/briefing.md` § Calendar reconciliation.
- **`gog` CLI**: `gog drive ls --parent=ID --json`, `gog drive mkdir NAME --parent=ID --json`,
  `gog drive move FILEID --parent=NEWPARENT --json`. Use `--json` for stable parsing.
- **Bash, Read, Write, Edit**: local files.
- **Agent tool**: launch subagents in parallel (`subagent_type: general-purpose`).

## Execution phases

### Phase 0 — Bootstrap and state

1. Read `$MEETINGS_MEMORY/_procesados.jsonl` (may not exist → treat as empty). Each line:
   `{"drive_id": "...", "group_key": "...", "processed_at": "...", "resumen_path": "..."}`.
2. Read `$MEETINGS_MEMORY/_drive_layout.json` (may not exist → `{}`). Expected shape:
   ```json
   {
     "tactiq_root_id": "...",
     "procesadas_id": "...",
     "descartadas_id": "...",
     "subcarpetas": { "procesadas/2026-05": "...", "descartadas/2026-05": "..." }
   }
   ```
3. If `procesadas_id` or `descartadas_id` are missing from layout: list `TACTIQ_ROOT` with
   `gog drive ls --parent="$TACTIQ_ROOT" --json`. If `procesadas` and `descartadas` subfolders
   already exist at top level, record their IDs. If not, create with
   `gog drive mkdir procesadas --parent="$TACTIQ_ROOT" --json` and
   `gog drive mkdir descartadas --parent="$TACTIQ_ROOT" --json`. Persist in `_drive_layout.json`.
4. Load current `acciones.md` for open actions (`estado: abierta` or `en-curso`; closed are `hecha`,
   `cancelada`, or `caducada`). Pass these to subagents for close/update detection. Schema and
   lifecycle: `$WT/_diseño/specs/007-modelo-acciones/` (or `$SECRETARY_INSTANCE/_diseño/specs/007-modelo-acciones/`).

### Phase 1 — Scout: list, filter, group

1. List immediate contents of `TACTIQ_ROOT` with `gog drive ls --parent="$TACTIQ_ROOT" --json`.
   Exclude folder entries (`procesadas/` and `descartadas/` are not processed).
2. Filter:
   - **Already processed**: `drive_id` in `_procesados.jsonl` → skip (except "extended group" case
     below).
   - **Unstable**: `modifiedTime` within last 10 minutes → skip (Tactiq may still be writing). Report
     as "awaiting stability" in final log.
   - **Empty shell**: `fileSize < 3000` bytes → aborted Tactiq start, not a meeting; register for
     discard (moved to `descartadas/` in Phase 4).
3. Group remaining files by `group_key = (YYYY-MM-DD from title, normalized_title)`.
   Normalization: lowercase, no accents, normalized spaces/separators. Example:
   "2026-05-06 Luna / Álvaro" → `2026-05-06|luna/alvaro`.
4. Within each group, sub-group by `createdTime` proximity: files whose `createdTime` are <90 minutes
   apart belong to the same session (reconnect / multi-device continuations). Gap >90min → separate
   sessions processed independently even with same title.
   - **CAVEAT (validated 2026-06-11): `createdTime` is an imperfect PROXY — always cross-check
     content before splitting.** Tactiq sets each doc's `createdTime` when it *closes/saves* the
     fragment, not when the call starts; one continuous call can produce a short fragment saved early
     and the long fragment hours later, with >90min `createdTime` gap but one session. Before treating
     two same-title+day fragments as separate sessions, open transcripts and check **internal
     timestamps** (`HH:MM AM/PM`) and **highlights**: if time ranges are contiguous/overlapping or
     highlights identical, it is ONE session → merge (principal = most complete; secondaries to
     `descartadas/`). Real example: 2026-06-11 "Claude" (Roger/owner) in 3 docs with `createdTime`
     21:35Z / 23:25Z / 00:35Z (110 and 70 min gaps) but transcripts covered 4:18→4:21pm, 4:29→6:13pm
     and 4:29→7:22pm Lima — one continuous call. `createdTime` gap would have split wrongly; content
     ruled.
5. **Extended group**: if a session has new fragments this run but some `drive_id` in the group was
   already in `_procesados.jsonl`, mark the group for **full reprocessing**. Covers Tactiq uploading a
   late fragment after another was processed. New summary version replaces prior; memory items merge.
   - **Same-day sibling (distinct session, NOT extended group)**: if a new group shares date+title
     with an already-processed summary but `drive_id` differs and `createdTime` gap is >90min, they
     are **two separate meetings the same day** (e.g. 2026-05-19: work session Greg/owner + social
     session that night). NOT reprocessing. Validated 2026-05-20. Actions: (a) give new summary a
     distinct slug (e.g. `-starcraft-social` vs `-secretary-y-esmio`); (b) **tell the subagent for
     the new session** the path of the already-processed sibling summary in its prompt, so it does
     NOT flag false "wiki/calendar misalignment" when transcript topics actually occurred in the
     other session.
6. If no new groups remain after filters and no shells to discard: update `_procesados.jsonl` with
   `last_run_at` (separate line `{"_meta":"last_run","ts":"..."}`) and exit reporting "No new
   meetings".

### Phase 2 — Subagent dispatch

For each group to process, launch **one subagent in parallel** via Agent tool
(`subagent_type: general-purpose`). Invoke all subagents in one message with multiple simultaneous
Agent calls.

#### Context the orchestrator prepares once before Phase 2

- Read `$WT/knowledge/wiki/articulos/personas/_index.md`,
  `$WT/knowledge/wiki/articulos/organizaciones/_index.md`,
  `$WT/knowledge/wiki/articulos/temas/_index.md` (read-only).
- Read the owner's persona article from `$WT/knowledge/wiki/articulos/personas/` (resolve slug from
  `_index.md` or instance wiki; this instance: `alvaro-mur.md`).
- Read `$MEETINGS_MEMORY/acciones.md` filtering open-state items.
- Read `$MEETINGS_MEMORY/_glosario.md` — **critical ground truth**. Clarifications wiki does not
  yet capture. Any person/org/relationship encoded there overrides subagent inference: if transcript
  seems to contradict glosario, assume transcription error and apply glosario correction.

Include this content literally in each subagent prompt.

#### Validation rules the subagent MUST follow (anti-hallucination gate)

1. **Default `pendiente_wiki: false` for new entities.** Any person/org/topic NOT already in wiki
   registers with `pendiente_wiki: false`. Owner reviews and flips to `true` later. Exception: if
   glosario explicitly names the entity, may enter with `pendiente_wiki: true`.
2. **Enrichments to existing entities**: may enter with `pendiente_wiki: true` (low risk: slug
   already validated).
3. **Do not infer surnames** from context. If transcript says "Miriam" without surname and glosario
   does not name her, register as "Miriam (apellido por confirmar)". Same for ambiguous org names.
4. **Do not create new entities from suspicious fragments**. If a word sounds like a proper name but
   could be bad transcription ("ex-X", "pre-Y") or a descriptor, mark `# duda:` and leave
   `pendiente_wiki: false`.
5. **Question new terms that do not fit semantically.** If transcript introduces a word that makes no
   sense in context (especially as document, tool, company, or product name) — before using it
   verbatim, try phonetic resolution: what English or Spanish word sounds similar and would fit?
   Tactiq makes systematic phonetic errors, especially English words with Spanish accent. Documented
   examples:
   - `"chip"` → `"Sheet"` (Google Sheets with Spanish accent: "sh" → "ch", "eet" → "ip")
   - `"AutoMae"` / `"AutoMai"` → `"Automy"` (company name mis-segmented)
   If resolved with high confidence, apply correction and note
   `<!-- tactiq-fix: "<original>" → "<corrected>" — fonético -->`. If uncertain, keep original with
   `# duda-fonetica:` for human review.
6. **If glosario contradicts transcript**: glosario wins. Apply correction and note
   `<!-- glosario aplicó corrección: <what> -->` in the summary.

#### Subagent prompt (template)

```
You are a subagent processing **one meeting** for the instance owner from Tactiq transcripts. You
produce a structured Markdown summary and return JSON with memory items for the orchestrator to
consolidate. **Do not write to instance `wiki/`** or modify consolidated memory files — only write
the summary file at the absolute path the orchestrator gives you and return JSON. **Never build paths
starting with a bare module prefix** — use only the absolute `resumen_path` provided.

## Group data
- group_key: {group_key}
- fecha: {fecha}
- original title: {titulo_original}
- group drive_ids (read in ascending createdTime order):
{lista_drive_ids_con_metadata}
- associated calendar event (may be null): {calendar_event}

## Output paths
- resumen_path: {resumen_path}  ← write final .md here.

## Wiki context (read-only, for wikilink anchoring)

### Personas index
{contenido_personas_index}

### Organizaciones index
{contenido_orgs_index}

### Temas index
{contenido_temas_index}

### Owner persona article
{contenido_alvaro_mur}

## Current open actions (check if any close/update in this meeting)
{contenido_acciones_abiertas}

## Your task

1. Read each drive_id with MCP `read_file_content` (Drive). Tactiq format:
   `**HH:MM Speaker:** text` per line.
2. If multiple docs (same `group_key`), build unified transcript: order by `createdTime`, dedupe
   overlapping dialogue (same speaker + identical or ≥85% similar text within ±60s window).
3. Identify principal doc (most complete/longest) and secondaries (continuations or duplicates).
4. Write `{resumen_path}` with this exact structure:

```markdown
---
fecha: YYYY-MM-DD
titulo: <título descriptivo>
tipo: <1:1 operativo | equipo | externo | cliente | otro>
duracion_min: <int>
participantes:
  - "[[wikilink]] o nombre"
mencionados:
  - <nombres>
organizaciones:
  - "[[wikilink]] o nombre"
temas:
  - "[[wikilink]] o tema nuevo"
fuentes:
  - tipo: tactiq
    drive_id: <id principal>
    url: https://docs.google.com/document/d/<id>/edit
    agregado: YYYY-MM-DD
ultima_actualizacion: YYYY-MM-DD
---

## Contexto

<3-6 líneas que respondan: por qué ocurrió esta reunión. Anclar a tema/proyecto vía wikilinks. Si no hay contexto previo en la wiki para este tema/personas, decirlo explícitamente. Cuando haya historia (otras reuniones del mismo tema), tejer con ellas.>

## Resumen

<3-6 líneas con qué pasó concretamente y qué cambió tras la reunión.>

## Cronología

<Bloques `**MM:SS–MM:SS — etiqueta.** descripción` cubriendo los principales tramos de la conversación. Apuntar a 6-12 bloques. Cada bloque debe ser autosuficiente: alguien que no leyó la transcripción puede entender el flujo.>

## Decisiones

<Bullets con las decisiones acordadas. Citar literalmente cuando la frase es contundente y útil para fundamentar decisión futura.>

## Acciones / pendientes

| # | Quién | Acción | Deadline | Estado |
|---|-------|--------|----------|--------|
| 1 | <persona> | <acción concreta> | <YYYY-MM-DD o —> | abierta |

## Temas tratados

<Bullets con los grandes temas, especialmente los que enriquecen el conocimiento sobre proyectos/clientes existentes.>

## Quotes (opcional)

> "frase literal" — Persona, MM:SS

<Sólo incluir si hay frases especialmente útiles. Sección puede omitirse.>

## Notas para la wiki

<Qué personas/orgs/temas detectados son nuevos vs ya existen. Si no hay nada nuevo, decirlo.>

<!-- Si hubo múltiples docs en el grupo, listar al final: -->
## Docs procesados (si hubo grupo)

- principal: drive:<id> (<bytes>B, createdTime)
- secundario: drive:<id> ... (descartado/mergeado)
```

5. **Extract and classify new actions** (model: spec 007). Assign draft IDs (`DRAFT-1`, `DRAFT-2`, …;
   orchestrator replaces with stable IDs). Per new action define:
   - `titulo`: short action-oriented phrase (readable "what").
   - `tipo`: `compromiso` (must do, even if raised in a meeting) · `decisión` · `seguimiento`
     (ball in other's court) · `idea` (parking). **Do NOT extract pure events as actions** — calendar
     owns events; "attend X" is not an action (but "close proposal in meeting on the 16" is a
     *compromiso*).
   - `dueño`: `mía` (owner) · `compartida` · `tercero`.
   - `workspace`: `ennui · inspiro · personal · secretary · dev`.
   - `proyecto`: project slug (normalize `contexto`).
   - `estado`: starts `abierta`. **Anti-backfill (hard rule):** if `deadline` already passed vs.
     meeting date (historical action from old transcript), do NOT create `abierta` — create
     `caducada` (with `evidencia_cierre: manual:nace-vencida`) or omit. **Never birth an expired
     action.**

6. For each action in "Current open actions" above, evaluate if this meeting affects it:
   - **Explicitly closed**: someone says it is done → `update` with `estado_nuevo: hecha` (+ `evidencia`).
   - **Cancelled**: decided not to do → `estado_nuevo: cancelada`.
   - **Rescheduled**: deadline change → `deadline_nuevo` (state stays `abierta`/`en-curso`).
   - **Owner or scope change**: same.
   - **No clear mention**: do not generate update (weak guarantee in v1; strong closure now comes
     from brief reconciliation — calendar/mail/sec-status — and housekeeping sweep).

7. Return ONE JSON block at the end with this exact shape:

```json
{
  "resumen_path": "/absolute/path/in/WT/extractors/meetings/summaries/YYYY-MM-DD-slug.md",
  "drive_id_principal": "...",
  "drive_ids_secundarios": ["..."],
  "drive_ids_shells": [],
  "entrada_reuniones_md": "## YYYY-MM-DD — Título\n- participantes: ...\n- duracion_min: ...\n- tipo: ...\n- temas: ...\n- resumen_path: ...\n- fuente_drive_id: ...\n- detectado: YYYY-MM-DD\n- pendiente_wiki: true\n",
  "personas_detectadas": [
    {"nombre": "...", "ya_en_wiki": true, "slug_existente": "...", "contexto_nuevo": "...", "pendiente_wiki": false}
  ],
  "organizaciones_detectadas": [],
  "entidades_enriquecidas": [
    {"slug": "erp-clab", "ya_en_wiki": true, "contexto": "...", "pendiente_wiki": true}
  ],
  "nuevas_acciones": [
    {"draft_id": "DRAFT-1", "titulo": "...", "accion": "...", "tipo": "compromiso", "dueño": "mía", "responsable": "...", "workspace": "ennui", "proyecto": "erp-clab", "deadline": "YYYY-MM-DD o null", "estado": "abierta", "contexto_wikilinks": ["temas/erp-clab"]}
  ],
  "updates_acciones": [
    {"acc_id": "acc-20260506-001", "estado_nuevo": "hecha", "evidencia": "quote o paráfrasis del transcript", "evidencia_cierre": "manual:reunion", "deadline_nuevo": null, "responsable_nuevo": null}
  ]
}
```

End your response with that JSON block. Add nothing after the closing brace.
```

### Phase 3 — Consolidation

Orchestrator receives subagent JSONs (one per meeting) and consolidates:

1. **Assign stable IDs to new actions**. Per subagent, in processing order, generate
   `acc-YYYYMMDD-NNN` where NNN is sequential from (max existing NNN for that date in `acciones.md`)
   + 1. Replace `DRAFT-N` in:
   - The subagent JSON `nuevas_acciones` block.
   - The summary file that subagent wrote: read, find/replace `DRAFT-N` with stable ID, rewrite.

2. **Append to `acciones.md`** (spec 007 schema):
   - Per new action: `## acc-YYYYMMDD-NNN` block with fields `titulo, accion, tipo, dueño,
     responsable, estado (abierta, unless anti-backfill → caducada), workspace, proyecto, deadline,
     cerrado: null, evidencia_cierre: null, origen (resumen_path), detectado, contexto,
     pendiente_wiki: true`.
   - Per update: `## acc-YYYYMMDD-NNN [update]` with `estado_nuevo, evidencia, origen, detectado,
     pendiente_wiki: true`; if update **closes** the action (`hecha`/`cancelada`/`caducada`), add
     `cerrado: <date>` and `evidencia_cierre`. Change fields (`deadline_nuevo`, `responsable_nuevo`)
     if applicable.

3. **Append to `reuniones.md`**: each subagent's `entrada_reuniones_md` field, as-is.

4. **Append to `personas.md`**:
   - `ya_en_wiki: false` → `## Full Name` block with `contexto, fuentes (reuniones:<drive_id>),
     detectado, pendiente_wiki: true`.
   - `ya_en_wiki: true` with non-empty `contexto_nuevo` → similar block with `pendiente_wiki: <subagent
     bool>` (subagent decides if enriching existing entry is worthwhile).
   - `ya_en_wiki: true` with empty `contexto_nuevo` → write nothing.

5. **Append to `organizaciones.md`** and **`entidades.md`** with same logic.

6. **Before appending, check duplicates** in each file: if item with same name/slug and same origin
   exists, do not duplicate. Merge if context is new.

### Phase 4 — Move files in Drive

Per processed group:

1. Determine monthly destination subfolder: `procesadas/YYYY-MM/` (month of group date).
2. If that subfolder is missing from `_drive_layout.json`: list `procesadas/` with `gog drive ls`;
   if exists register it, else create with
   `gog drive mkdir YYYY-MM --parent=<procesadas_id> --json`. Persist in `_drive_layout.json`.
3. Move `drive_id_principal` with `gog drive move <id> --parent=<subcarpeta_id> --json`.
4. Move `drive_ids_secundarios` and group shells to `descartadas/YYYY-MM/` (same subfolder
   procedure).
5. If a move fails (network, permissions): do not abort the run. Log failure in final report and
   leave file in place; `_procesados.jsonl` still marks `drive_id` processed so next run does not
   reprocess.

### Phase 5 — Bookkeeping

1. Per processed `drive_id` (principal, secondaries, shells), write one line to `_procesados.jsonl`:
   ```json
   {"drive_id":"...","group_key":"...","rol":"principal|secundario|shell","processed_at":"<ISO>","resumen_path":"..."}
   ```
2. Write final line `{"_meta":"last_run","ts":"<ISO>","grupos_procesados":N,"shells_descartados":M}`.

### Phase 6 — Final report

The report (Markdown) is not printed standalone: write to a temp file and pass as **PR body**
(Phase 7). Content:
- Number of groups processed.
- Number of shell files discarded.
- List of summaries generated (paths).
- Drive move errors (if any).
- Files in "awaiting stability" state (modified <10min ago) for next run to pick up.

### Phase 7 — Close: Commit + Pull Request (this PR is the report)

**PR body signature:** `_firma.md` → `sec-signature.sh reuniones-update`.

```bash
cd "$WT"
if [ -z "$(git status --porcelain)" ]; then
  echo "No new meetings / no versioned changes — no PR opened."
  cd "$REPO" && git worktree remove "$WT" --force && git branch -D "$BRANCH" 2>/dev/null || true
else
  git add -A
  git commit -m "docs(reuniones): corrida automática $(date +%Y-%m-%d)"
  git push -u origin "$BRANCH"
  gh label create "hilo:reuniones" --description "Hilo de trabajo: reuniones" --color D4C5F9 2>/dev/null || true
  # Write report (Markdown) with Write tool to /tmp/pr-reuniones.md
  gh pr create --title "docs(reuniones): corrida automática $(date +%Y-%m-%d)" \
    --label "hilo:reuniones" --body-file /tmp/pr-reuniones.md
  cd "$REPO" && git worktree remove "$WT" --force
fi
```

- Create report (`/tmp/pr-reuniones.md`) with Write tool, not `echo`/heredoc.
- Drive moves (Phase 4) and `_procesados.jsonl` already happened in the worktree before this close.
- If `gh pr create` fails, do not revert: branch is pushed; report error.
- Return **PR URL** at the end.

## Golden rules

1. **Never** write to `$WT/knowledge/wiki/`. Read-only.
2. **Never** delete owner files. In Drive `gog drive move` reorganizes, does not destroy. Locally
   only `Edit`/`Write` on files under `$WT/extractors/meetings/`.
3. **Idempotency**: two consecutive runs with no new Drive input produce no diffs.
4. **Append-only memory**: `wiki-update` cleans integrated items; reuniones-update only appends.
5. **Do not invent content**: if a meeting does not mention something, do not write it. Mark
   `[por confirmar]` when info is missing.
6. If **`gog` fails on auth** (`gog auth ...`): do not ask for credentials; abort Drive move phase
   with clear report and leave the rest processed. Owner reauths manually.

## Maintaining this SKILL — agent may edit it

Explicit permission to edit this playbook file at the end of a run when you have learnings to encode:

- New Tactiq transcription patterns requiring parsing adjustments.
- Deduplication heuristics that worked or failed.
- Changes to subagent JSON format.
- Common errors to avoid.

Path: `${SECRETARY_SCHEDULED_TASKS:-$HOME/.claude/scheduled-tasks}/reuniones-update/SKILL.md`

Rules:
- Do not change frontmatter (`name`, `description`) without strong reason.
- Log any SKILL edit in stdout in the final report.
- If an idea is not validated, leave as `<!-- idea: ... -->` not an active rule.

## What NOT to do

- Do not process files `<3KB` as meetings (shells).
- Do not process files modified `<10 min` ago (Tactiq still writing).
- Do not group distinct meetings with same title and same day if `createdTime` are >90 min apart
  **without** content cross-check (see Phase 1 caveat).
- Do not create wiki articles or alter other modules' memory.
- Do not move Drive files before generating summary and memory items.
- Do not skip `_procesados.jsonl` update even if moves fail.
