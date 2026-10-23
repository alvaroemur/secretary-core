---
name: desk-dream
description: >-
  Overnight / on-demand completion loop — one substantial dream job per run: cross-signal synthesis
  from meetings, mail, and repo WIP into a staged deliverable (PR and/or Gmail draft). Consolidates
  memory as input, reports in subsystem/dream/. Triggers: "/desk-dream", "/desk-dream soul",
  "/desk-dream --job lane", scheduled headless 05:00 (large job, budget 120 min), 13:00 and 21:00
  (medium job) in the instance timezone.
---

# desk-dream — overnight completion

**What this does:** finish **one** stalled owner lane overnight (or on demand) by crossing the latest signals
(meeting, mail, repo), synthesizing a real deliverable, staging it merge-ready, and reporting durable
artifacts for `desk-drone`, `desk-overview`, and optional briefing embed. Memory consolidation is **input** for
the job — not the headline output.

Doctrine: `rules/skills-contract.md` · Output: `rules/sec-output.md` · Spec: instance
`_diseño/specs/L5-observabilidad/020-sec-dream/spec.md` · Recurrence/escalation + main-only skip:
`_diseño/specs/L5-observabilidad/024-recurrencia-escalacion/spec.md`

## Principles

- **One job per run.** Max one primary `dream_job`; `deferred_queue` max 3 — no parallel suggestions.
- **Owner lanes first.** Harness hygiene informs scoring only — not the default primary job.
- **Cross-signal.** Prefer lanes with ≥2 independent sources (meeting, mail, repo, open PR, brief
  `sec-status`) within 7d pointing at the same deliverable.
- **Gates:** PR create/update OK · Gmail **draft** OK (`gog`) · **send never** · **merge never**
  (surface merge-ready; owner invokes `desk-merge` next session).
- **Decision B:** soul/harness autonomous edits → **worktree → PR** — never direct push to `main`.
  **Excepción (spec 024):** si el run termina en `skipped_no_owner_job` **y**
  `soul_harness_fallback: null` (tras agotar queue → scoring → minado), commit+push
  **directo a `main`** solo bajo `subsystem/dream/` (tier ambient, precedente `desk-heartbeat`).
- **Forked context** for scheduled and default on-demand runs — not the routine default model.

## Model selection

Long-context, multi-step completion — distinct from heartbeat / light routine triage.

```bash
CFG=$(secretary config show)
DREAM_MODEL="${SECRETARY_DREAM_MODEL:-$(echo "$CFG" | jq -r '.dispatch.routines.dream_model // empty')}"
ROUTINE_MODEL=$(echo "$CFG" | jq -r '.dispatch.routines.model // empty')
```

| Source | Key |
|--------|-----|
| Env override | `SECRETARY_DREAM_MODEL` |
| Instance config | `delegate.routines.dream_model` in `.secretary.yml` |
| Baseline only | `delegate.routines.model` — document in log if used as emergency fallback |

**Degraded run:** if dream model unavailable or over cost ceiling → consolidate + update
`deferred_queue` + `dream_job.status: blocked` with reason in JSON/log — no silent switch to
expensive default without log entry.

**Pre-v1 live overnight:** model evaluation harness (spec FR-9) should gate production scheduled
runs; v1 ships collect + skill contract without requiring a live LLM overnight pass.

## Store (write destination)

```
$SECRETARY_INSTANCE/subsystem/dream/
├── latest.json
├── dream-YYYYMMDD.json
└── log/YYYY-MM-DD.md
```

Resolve: `secretary config path subsystem.dream` · Schema: `subsystem/dream/README.md`

Collect debug (gitignored): `subsystem/dream/collect/collect-*.json`

## Guardrails

| Action | Autonomous? |
|--------|-------------|
| Create/update PR (owner repo) | Yes — primary deliverable |
| Gmail draft (`gog`) | Yes |
| Gmail send / WhatsApp / third party | **Never** 🚧 |
| Merge PR | **Never** — `desk-merge` next session |
| Edit `knowledge/objectives/` body | **Never** — 💡 delegate suggestion |
| Executable / workflow / `.secretary.yml` | **Never** 🚧 |
| Soul `memory` prune / harness typo | Fallback only — worktree → PR (decision B) |
| Soul `purpose` / drone `objectives` | `--soul` → proposal until OK → PR |
| Skip puro (`skipped_no_owner_job`, sin fallback) | ✅ main-only ambient (spec 024) |

## Triggers

| Mode | Invocation |
|------|------------|
| Scheduled | 05:00 instance timezone (large job) — finishes before portal aggregate (07:00), pre-brief heartbeat (07:10), and briefing. 13:00 and 21:00 (medium job), paused by the rate-limit brake in the routine playbook |
| On-demand | `/desk-dream` |
| Soul review | `/desk-dream soul` |
| Force lane | `/desk-dream --job <lane>` |
| Consolidate only | `/desk-dream --consolidate-only` |

Indirect: portal (spec 019) · `desk-overview` reads `latest.json`

---

## Skill chain

| Need | Delegate |
|------|----------|
| Owner-approved job queue (checked first) | `subsystem/dream/queue.md` — written only by `desk-overview` § 6.5 |
| Deterministic gather | `scripts/dream/collect.py` |
| Wiki pending integrate | `desk-sys-integrate` (Consolidate phase) |
| Memory dedupe | `desk-consolidate` (when backlog) |
| PR hygiene on dream job PR | `babysit` (Stage phase, job worktree) |
| Next-session merge | route note → `desk-drone` → owner `desk-merge` |
| Mail draft deliverable | `gog` draft (never send) |
| Fundamental soul edit | `--soul` proposal → owner OK → PR |

---

## Procedure — phases 0–5

### Instance setup

```bash
eval "$(secretary env)"
CFG=$(secretary config show)
export SECRETARY_CORE="${SECRETARY_CORE:-$(echo "$CFG" | jq -r .core)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
DREAM_ROOT=$(secretary config path subsystem.dream)
DREAM_MODEL="${SECRETARY_DREAM_MODEL:-$(echo "$CFG" | jq -r '.dispatch.routines.dream_model // "dream"')}"
OBJECTIVES_ROOT=$(secretary config path knowledge.objectives.root 2>/dev/null || echo "")
DRONE_SOUL=$(secretary config path subsystem.drone)/soul.md
git -C "$SECRETARY_INSTANCE" fetch origin -q
```

### Phase 0 — Aggregate

Reuse portal aggregate when fresh (<30m):

```bash
PORTAL_LIVE="$SECRETARY_INSTANCE/subsystem/portal/live-data.json"
# If missing or stale → skip; heartbeat/collect still run in Phase 1
```

Read `subsystem/heartbeat/latest.md` for loose-git / acc↔git context (input to scoring, not output).

### Phase 1 — Discover + Gather

**Deterministic collect** (required):

```bash
python3 "$SECRETARY_INSTANCE/scripts/dream/collect.py" --write-collect
# Or stdout only:
python3 "$SECRETARY_INSTANCE/scripts/dream/collect.py" --format json
```

Buckets: objectives lanes · heartbeat summary · soul memory recent · module memory paths · open PRs
on delegate allowlist · brief `sec-status` · `contract_health` · `validate_status` ·
`job_candidates[]` with cross-signal score hints.

**Lessons (required, before synthesizing anything):** read
`$SECRETARY_INSTANCE/subsystem/dream/lessons.md` in full — append-only log of concrete past
failures + the rule that would've prevented each. Apply every rule that's relevant to the chosen
lane's job (issue cowork-secretary#509). Notably: cite evidence literally in the deliverable
(never assert "confirmed in the data" without quoting the cell/formula) and read Sheet **formulas**
(`--render FORMULA`), not just values, when interpreting a client's numeric observation.

**Discover (LLM + rules) — orden fijo antes de skip (spec 024):**

When run as the scheduled routine, the routine playbook (`sec-dream`) defines the source order
(`dispatch:execute` work orders first, then this queue, brief decisions, issues with a deadline
and unreviewed PRs) and the work-order execution contract absorbed from work-runner. The steps
below apply inside that order.

0. **Owner queue first.** Read `$SECRETARY_INSTANCE/subsystem/dream/queue.md` § Pendientes
   before touching `job_candidates`. This is work Álvaro explicitly approved during a `desk-overview`
   on-ramp (skill § 6.5) — it outranks scoring entirely, no ≥2-source requirement applies. If
   `## Pendientes` has one or more entries: take the **oldest** (topmost) one as the primary
   `dream_job` for this run, skip steps 1–4 below, and go straight to Gather/Synthesize/Stage
   using that entry's Contexto/Repo-lane as the job brief. On completion (Phase 4), remove that
   entry from `## Pendientes` and append a short line under `## Consumidas` (title +
   `dream-YYYYMMDD.json` ref) in the same commit as the job's staging — see `queue.md`'s own
   header for the exact format. If the queue is empty, continue with scoring below.
1. Read `job_candidates` from collect output — top row is a hint, not automatic selection.
2. Apply FR-4–FR-7: require ≥2 source types for primary job unless `--job <lane>` forces owner intent.
3. Pick **one** primary `dream_job` from scoring **or** continue to step 4 (do **not** skip yet).
4. **Minado de backlog ad-hoc** (solo si 0–3 no dieron job). Ver § Minado abajo. Si triagea ≥1
   issue (`delegate:execute` y/o cierre de duplicado/obsoleto), eso **es** el trabajo de la
   corrida: `dream_job` con lane `backlog-mine` (o equivalente) y status `staged`/`merge_ready`
   según lo hecho — **no** declares `skipped_no_owner_job`.
5. Solo si queue + scoring + minado salen vacíos → `dream_job.status: skipped_no_owner_job`.
6. Populate `deferred_queue` (max 3) from remaining scored lanes — not executed this run.
7. Every `signal` must cite a resolvable path or `gh` ref — no hallucinated lanes.

**Gather (cross-medium):** for the chosen lane, read fresh evidence:

- Meetings: `extractors/meetings/summaries/`, unmerged `reuniones/auto-*` PRs
- Mail: `extractors/mail/memory/`, stale draft hints via `desk-mail` step 0 if needed
- Repo WIP: host path from `dispatch.executor.repos` for the lane (worktree for edits in Phase 3)

### Minado de backlog ad-hoc (spec 024, pieza 4)

Corre **después** de `queue.md` y del scoring normal, **antes** de `skipped_no_owner_job`.

```bash
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
# Issues abiertos de harness/sistema (excluir briefings diarios)
gh issue list --repo "$BRIEF_REPO" --state open --limit 50 \
  --json number,title,labels,createdAt,body \
  --jq 'map(select(.labels|map(.name)|index("tipo:informe-diario")|not))'
```

Reglas:

1. **Clasifica y registra.** Lee `../desk-context/references/control.md`. Puede preparar un PR aislado bajo la regla vigente `prepare-pr-v1`, o registrar una propuesta con ese metadato y `dispatch:execute` para una corrida posterior. Verifica límites y efectos; la etiqueta no autoriza. Si necesita cambio de estrategia, fuentes fuera de una regla vigente, permisos o ampliación de alcance, crea/actualiza la decisión canónica `desk:decision` con evidencia, consecuencia y recomendación. No se autoriza a sí mismo ni ejecuta un merge.

2. **Autoridad de cierre** sobre duplicados y obsoletos encontrados en este minado — cerrar con
   comentario que cite el issue canónico o la razón de obsolescencia. Fingerprint ad-hoc = el
   issue mismo (`<!-- fingerprint: <slug> -->` en body; `desk-learn` ya busca por eso).
3. Priorizar: más viejos primero; duplicados evidentes (#814/#895 como caso de calibración);
   mejoras de harness sin label de ejecución.
4. Reportar en JSON/log la lista `issues_triaged[]` / `issues_closed[]` (baranda propuesta del
   spec — incluirla siempre que el minado toque issues).
5. Si no hay candidatos triageables → minado vacío → paso 5 del Discover (skip real).

### Phase 2 — Consolidate

Input processing **for the chosen job** and durable memory hygiene.

**1. Project milestone discovery (from merged PRs across all user repos):**
- Read `merged_prs_activity` from collect output.
- For each PR where `is_candidate_milestone == True`:
  - Identify the matching theme article: `knowledge/wiki/articulos/temas/<slug>.md` (mapping by repo name, e.g. `cowork-inspiro` → `soltrak` / `inspiro-agents`, `cowork-ennui` → `foro-bioeconomia-panamazonica` / `erp-clab`, `clab-erp` → `erp-clab`, `secretary-core` → `secretary`, or raw repo slug).
  - **If article exists**: check if the PR/milestone is already reflected. If not, append a `<!-- sec:pending ... -->` annotation in the article citing the date and PR link (`gh:<repo>#<N>`).
  - **If article does NOT exist**: create a concise project stub article in `knowledge/wiki/articulos/temas/<slug>.md` with canonical frontmatter (`tipo: tema`, `categorias: [temas]`) and document the first milestone.

**2. Annotation integration & dedupe:**
When wiki `sec:pending` backlog or module memory noise detected:
- Invoke `desk-sys-integrate` (integrates all pending milestone/entity annotations into article prose) and/or `desk-consolidate` (dedupe).
- Record actions in JSON `consolidation` block — e.g. `"wiki_integrate": "invoked"`, `"milestones_annotated": [...]`.
- Do **not** present consolidation as the primary human outcome if a `dream_job` completes.

### Phase 3 — Synthesize + Stage

**Synthesize (dream model):** produce deliverable content — doc, contract terms, structured markdown,
Gmail draft body, etc. Use consolidated + gathered signals only.

**Stage (worktree in target repo):**

```bash
# Example pattern — expand repo path from delegate allowlist
WT="$HOME/.wt/dream-${TODAY}-<lane>"
git worktree add -b "dream/<lane>-${TODAY}" "$WT" origin/main
cd "$WT"
# … edit deliverable files …
git add -A && git commit -m "feat(<scope>): dream job <short title>"
export SECRETARY_SKILL=desk-dream
export SECRETARY_BRANCH=$(git branch --show-current 2>/dev/null || true)
SIG_MARK=$(~/.claude/scripts/sec-signature.sh desk-dream --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh desk-dream --footer)
gh pr create --title "…" --body "${SIG_MARK}

Closes dream job …

---
${SIG_FOOT}"
```

- Optional Gmail draft: `gog` — **draft only**, never send.
- Run **`babysit`** on the dream PR until merge-ready (CI green, no conflicts, human comments triaged).
- Set `dream_job.status` → `staged` | `merge_ready` | `blocked`.

**Canonical reference scenario (US-1 — CLab contract terms):**

| Signal | Source |
|--------|--------|
| Meeting | Latest CLab/Juliana transcript or summary in meetings memory |
| Mail | Stale Gmail draft thread on contract terms |
| Repo | Scattered term drafts in Cowork ennui without integration |

**Dream job:** cross Jul 1 meeting terms → synthesize unified contract terms doc or mail draft →
open/update PR **merge-ready** in `cowork-ennui` → `next_session`: `desk-drone` surface PR →
`desk-merge` tier-low if owner confirms.

### Phase 4 — Report

Write committed artifacts:

```bash
# dream-YYYYMMDD.json — full schema (see spec)
# latest.json — copy/symlink of today's canonical file
# log/YYYY-MM-DD.md — prose: job outcome, PR links, consolidation as footnote, next session steps
```

JSON must include exactly one primary `dream_job` or explicit `skipped_no_owner_job`.

`next_session` field example: `desk-drone surface PR → desk-merge tier-low if green`

Haptics (scheduled): `📎 _secretary dream — <lane> · <status>_` (tier 🫧)

**Commit path (spec 024):**

| Resultado | Cómo versionar |
|-----------|----------------|
| `dream_job` real staged (owner lane o minado con triage) | Artefactos `subsystem/dream/` via worktree→PR **o** commit en la misma entrega del job en el repo destino; soul/harness fallback → siempre worktree→PR (decision B) |
| `skipped_no_owner_job` **y** `soul_harness_fallback: null` | **Main-only ambient:** escribir JSON/log en el checkout principal (`main`), `git add subsystem/dream/`, commit+push a `main`, **sin** PR. Precedente `desk-heartbeat`. |
| `soul_harness_fallback` no null | Decision B intacta — worktree → PR, nunca push directo |

```bash
# Skip puro — ejemplo
cd "$SECRETARY_INSTANCE"   # debe estar en main
git pull --ff-only origin main
# … escribir dream-YYYYMMDD.json, latest.json, log/YYYY-MM-DD.md …
git add subsystem/dream/
git commit -m "chore(dream): skip $TODAY (no owner job tras queue/scoring/minado)"
git push origin main
```

**Emit metrics (required, last step):** this run has no `invoke-*.sh` subprocess/JSONL
stream, so it can't forward to `parse-routine-metrics.py` the way api-cron/cursor-cron do —
emit it into the Corridas ledger explicitly:

```bash
secretary dream emit-metrics
```

Idempotent (skips if the session is already in `metrics.jsonl`) — safe to run even if a
prior phase failed partway. Issue: alvaroemur/secretary-core#24.

### Phase 5 — Fallback

Run **only** when no owner `dream_job` selected after queue+scoring+minado, run blocked, or `--soul` invoked.

| Path | Action |
|------|--------|
| `--soul` | Produce `soul_proposal` markdown diff for `purpose` / drone `objectives` — apply only after 🚧 OK → worktree → PR |
| Soul/harness fallback | Max **one** PR: memory prune, audit link fix, harness doc typo — **worktree → PR always** (decision B) |
| No qualifying job after minado | `dream_job.status: skipped_no_owner_job` + `deferred_queue` updated → **main-only** report (Phase 4) |

Never edit owner `knowledge/objectives/` body autonomously.

---

## Report (on-demand / session tail)

Header: `🌙 **desk-dream — <lane or skipped>** · <date>`

```markdown
🌙 **desk-dream — ennui / CLab terms** · 2026-07-03

**Job** · merge_ready · `job-20260703-clab-terms`

| | Field | Value |
|---|---|---|
| 🧵 | Lane | ennui |
| 📎 | PR | [cowork-ennui#42](https://github.com/…/pull/42) · babysit green |
| ✉️ | Mail | draft hint — reply thread CLab (not sent) |
| 🔄 | Consolidation | 2 wiki annotations integrated (input) |

**Deferred** (max 3) · job-search · doc2struct — lower cross-signal score

**→ Next session** · `desk-drone` surface PR #42 → `desk-merge` tier-low on confirm
```

If fallback only: lead with `skipped_no_owner_job` or soul proposal — do not fake a primary job.

---

## Automatic vs requires OK

| Action | Automatic | Requires OK |
|--------|-----------|-------------|
| `collect.py` | ✅ | |
| `dream emit-metrics` (ledger) | ✅ | |
| Job selection (LLM) | ✅ | `--job` forces lane |
| `desk-sys-integrate` / `desk-consolidate` | ✅ when backlog | |
| Open/update PR in owner repo | ✅ | |
| Gmail draft | ✅ | |
| Gmail send | | 🚧 never |
| Merge PR | | 🚧 never — desk-merge |
| Soul `purpose` / objectives apply | | 🚧 always |
| Dispatch issue creation | | 🚧 — draft in output only |

---

## When to use / not use

- **Use:** overnight completion of one stalled owner lane; cross-signal synthesis after intense days;
  `/desk-dream soul` after strategic pivot.
- **Not:** daily agenda → `secretary-briefing`; in-session git ordering → `desk-drone`; deterministic
  snapshot → `desk-heartbeat`; ecosystem health sweep → `housekeeping`.

## Do not

- Run multiple parallel dream jobs or quantity targets (3–5 suggestions).
- Send mail or merge PRs autonomously.
- Push soul/harness edits directly to `main` (**excepto** skip puro sin fallback — spec 024).
- Declare `skipped_no_owner_job` sin haber mirado `queue.md`, scoring **y** minado de backlog.
- Replace `wiki-update` HTML build or full routine extractors.


Antes de elegir trabajo, recoge decisiones de utilidad de rutinas ya reportadas y aún abiertas. No repitas decisiones resueltas ni cierres una decisión estratégica como obsoleta sin evidencia. Publica en su reporte la autoridad utilizada, PR preparado y decisiones pendientes.


work-runner se fusionó en esta rutina. Para dejar una preparación elegible para una corrida posterior, registra el metadato de prepare-pr-v1 en el body y añade `dispatch:execute` como enrutamiento; la corrida que la tome verificará la regla y los efectos de nuevo con el contrato de ejecución del playbook. Si la preparación requiere una elección del propietario, usa desk:decision sin habilitar ejecución.
