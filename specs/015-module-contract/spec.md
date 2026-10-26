---
id: "015"
slug: module-contract
layer: L0
status: implementado
last_reviewed: 2026-07-27
implemented:
  - $SECRETARY_INSTANCE/scripts/ci/validate_module_contract.py
  - $SECRETARY_INSTANCE/scripts/ci/contract_health.py
  - secretary/modules.py
  - secd/lib/modules.mjs
  - ~/.claude/skills/pulse/SKILL.md
  - ~/.claude/skills/sec-refresh/SKILL.md
---

# Feature 015 — Module contract: extractors vs loops

**Estado:** `IMPLEMENTADO` (fases 1–3, 2026-07-02) — Phase 1 [#415](https://github.com/<instance-repo>/pull/415); Phase 2 + decisiones §6 [#441](https://github.com/<instance-repo>/pull/441); Phase 3 secd + CLI en secretary-core  
**Origen:** sesión post-reunión a collaborator (2026-06-29) — Ralph loops, goal-driven agents vs pipeline secretary  
**Relacionado:** spec 012 (layout) · spec 007 (acciones) · spec 008 (heartbeat) · spec 013 (sec-refresh) · ``canon/rules/glossary.md`` (instance path) · ``canon/operational/sorting/sistemas-ordenamiento.md`` (instance path)

---

## 1. Problem statement

### 1.1 Semantic split is not enough

Today the distinction between **extractors** and **loops** is documented narratively:

| Plane | Constitución §2 | Glossary | Operational allowlist |
|-------|-----------------|----------|------------------------|
| Extractors | Capture external signals | Mirror a single external feed | `memory/`, `state.md`, module-specific |
| Loops | Closed personal workflows | Own state across runs (inbox, applications) | `inbox.md`, `applications.md`, `sources-web/` |

That split is **correct but not operational**. An agent or CI cannot answer:

- Is this module healthy right now?
- What is it *for* (purpose), vs what does it *measure* (freshness, coverage)?
- Does this module participate in a goal-driven iteration (Ralph loop), or only in ETL capture?

Without answers, `pulse`, `sec-refresh`, and future `secd` admin cannot audit readiness; new modules get invented ad hoc (`job-search` grew `sources-web/state.md` as an iteration ledger without a shared schema).

### 1.2 Ralph loop paradigm (external reference)

In goal-driven agent loops (colloquially **Ralph loops** — see reuniones 2026-06-29 con a collaborator), each iteration:

1. Reads a **goal** (mutable purpose).
2. Acts toward **success criteria** (measurable checkpoints).
3. Updates **state** and optionally **rewrites the goal** for the next iteration.

Secretary already has pieces of this on the loop side (`applications.md` weekly meta, `sources-web/state.md` run ledger) but no shared contract. Extractors deliberately **must not** carry a north-star goal — they mirror feeds and deposit evidence. The contract must encode that asymmetry so validation is mechanical, not interpretive.

### 1.3 Design goal

A **minimum auditable contract** that:

- Distinguishes extractor vs loop by **required fields**, not prose.
- Links every loop to a strategic **objective** in `knowledge/objectives/` via `objective_ref` (local `goal.title` operationalizes it).
- Supports self-updating goals on loops when the routine or session detects pivot/completion.
- Stays **additive in phase 0** — manifest stubs, no breaking moves.
- Eventually surfaces in **secd** for UI administration (read contract, report health).

---

## 2. Vocabulary proposal

### 2.1 Primary term for loop purpose: **Goal**

**Recommendation:** use **Goal** as the canonical contract field for *why a loop exists* (operational, module-local). Reserve **Objective** for the strategic knowledge plane (`knowledge/objectives/`, `secd` `GET/POST /objectives`, schema `_schema.md`).

| Term | Plane | Role |
|------|-------|------|
| **Goal** | Loop `contract.yaml` | Operational purpose; mutable between Ralph iterations |
| **Objective** | `knowledge/objectives/` | Durable L0/L1 strategic intent; **required** link via `objective_ref` |
| **Success criteria** | Loop `contract.yaml` | Measurable checkpoints toward the goal |

| Option evaluated | Verdict |
|------------------|---------|
| **Goal** | **Adopt** for loop contract — aligns with Ralph-loop literature ("goal-driven iteration"); distinct from strategic objectives. |
| **Objective** | **Reserved** — `knowledge/objectives/` and secd API only; do not reuse as loop schema key. |
| Outcome | Reject as primary — OK in prose ("desired outcome") but duplicates Goal without YAML alignment. |
| North star | Reject as primary — evocative but not machine-stable; reserve for L0 strategy prose. |
| Signal | **Extractor-only** — raw capture unit; never the purpose of an extractor module. |

**Layered model (loops):**

```
goal               → why (operational intent; Ralph: mutable between iterations)
objective_ref      → required link to knowledge/objectives/obj-*.md (strategic plane)
success_criteria   → measurable checkpoints (Ralph: "done enough to stop / pivot")
state              → current snapshot (progress, blockers, last run)
iteration_ledger   → append-only run history (optional file or section)
```

**Extractor model (no goal):**

```
source             → identity of external feed(s)
coverage           → what the module is expected to see (accounts, chats, folders)
freshness          → SLA + last_success_at (operational, not strategic)
sink               → where evidence lands (memory/, summaries/, paths in YAML)
```

Extractors answer *"is the mirror current?"* Loops answer *"are we advancing toward the goal?"*

### 2.2 Measurable layer: **Success criteria** (not KPI)

| Option evaluated | Verdict |
|------------------|---------|
| **Success criteria** | **Adopt** — checklist-friendly, auditable, works in YAML and markdown tables. |
| KPI | Avoid as schema key — implies dashboard culture; use in human prose if needed. |
| Metric | Sub-field inside a criterion (`metric`, `target`, `current`). |
| Checkpoint | Alias in iteration ledger entries (`checkpoint_passed: true`); synonym for one criterion at one point in time. |

Example (job-search): criterion `applications_per_week` with `target: 5`, `current: 1`, `period: 2026-06-08..2026-06-12`; plus pipeline criteria (e.g. `interviews_scheduled`, `process_advances`) sourced from `applications.md` / agent-repo KPIs — the loop tracks the full search funnel, not only postulaciones.

### 2.3 Signal vs Goal (extractor vs loop)

| Concept | Extractor | Loop |
|---------|-----------|------|
| Purpose | None (by contract) | `goal` required |
| Unit of capture | **Signal** → `memory/`, summaries | **Candidate** → `inbox.md` |
| Human decision | Promote to wiki (Bibliotecario) | **Commit** → `applications.md` / closed state |
| Routine question | "Did we ingest since last SLA?" | "Did we advance criteria since last run?" |

---

## 3. Minimum contract tables

### 3.1 Extractor module

**Registry:** `.secretary.yml` → `paths.extractors.<module>.*` (existing).  
**Phase 0 add-on:** `extractors/<module>/contract.yaml` (stub, validated loosely).

| Artifact | Required | Schema / notes |
|----------|----------|----------------|
| `contract.yaml` | Phase 0: stub · Phase 1: required | See §3.1.1 |
| `state.md` | Yes (mail, whatsapp, drive, meetings) | Operational snapshot: last run, inbox stats, alerts — **no** goal or objective |
| `memory/` | Yes | `entidades.md`, `acciones.md` per ETL; module may add files |
| `policy.md` | Recommended (mail, whatsapp) | Capture rules, accounts, gates |
| `summaries/` | meetings, whatsapp | Structured evidence per event |
| `logs/` | mail | Run logs |
| Routine branch | `extractors/<module>/auto-*` | PR delivery |

#### 3.1.1 `contract.yaml` — extractor (minimum)

```yaml
kind: extractor
id: mail                    # matches folder name
version: 1
routine: revision-correo    # scheduled task id

source:
  type: gmail               # gmail | tactiq | drive | whatsapp | …
  accounts: [personal, work]   # keys from .secretary.yml accounts

coverage:
  description: "Inbox threads ≤30 per account; triage labels"
  # optional: explicit scope lists

freshness:
  sla: "18:00 America/Lima daily"   # cron-ish or ISO duration
  last_success_at: null             # routine fills; CI warns if stale

sink:
  memory: extractors/mail/memory
  state: extractors/mail/state.md
  # other paths = keys under paths.extractors.mail in YAML

# extractors MUST NOT define goal, objective, or success_criteria
```

| Field | Required | Validator |
|-------|----------|-----------|
| `kind` | yes | must be `extractor` |
| `id` | yes | must match parent folder |
| `routine` | yes | must exist in manifest |
| `source.type` | yes | enum |
| `freshness.sla` | yes | non-empty string |
| `sink.memory` | yes | resolves via `secretary config path` |
| `goal` | **forbidden** | CI error if present |
| `objective` | **forbidden** | CI error if present (reserved for knowledge plane) |

**Reference implementations:** `extractors/mail/` (richest `state.md`), `extractors/meetings/` (thin `state.md` + `summaries/` + `freshness.last_success_at` in contract).

### 3.2 Loop module

**Registry:** `.secretary.yml` → `paths.loops.<workflow>.*`.  
**Phase 0 add-on:** `loops/<workflow>/contract.yaml`.

| Artifact | Required | Schema / notes |
|----------|----------|----------------|
| `contract.yaml` | Phase 0: stub · Phase 1: required | §3.2.1 |
| `state.md` | Recommended at workflow root | Goal progress, blockers, human-readable; may duplicate contract `state` |
| `inbox.md` | Pattern: intake queue | Candidates **not yet committed**; routines may append |
| `applications.md` | Pattern: committed tracking | Human/session-owned conversions; **meta** encodes success criterion |
| `sources-web/` or sub-workflows | Optional | Nested loop; own `state.md` as iteration ledger |
| `iteration.md` | Optional (Phase 1) | Normalized ledger if `state.md` grows too large |
| Routine branch | `loops/<workflow>/auto-*` | PR delivery |

#### 3.2.1 `contract.yaml` — loop (minimum)

```yaml
kind: loop
id: job-search
version: 1
routine: job-search-crawler

goal:
  title: "Búsqueda laboral sostenible: detección → postulación → avance de proceso"

# Enlace obligatorio al objetivo estratégico (knowledge plane, obj-*.md):
objective_ref: knowledge/objectives/strategy/obj-20260702-002.md

success_criteria:
  - id: applications_per_week
    description: "Postulaciones enviadas (no solo detectadas)"
    metric: count
    target: 5
    period: weekly
    window: Mon-Fri America/Lima
    source: loops/job-search/applications.md
  - id: process_advances
    description: "Avances de proceso (entrevistas agendadas, rondas, cierres) — todo artefacto en el repo agente actualiza su KPI"
    metric: count
    target: 1
    period: weekly
    source: loops/job-search/applications.md

state:
  last_run_at: null
  summary: ""   # one line for pulse

submodules:
  - id: sources-web
    path: loops/job-search/sources-web
    iteration_ledger: loops/job-search/sources-web/state.md
    freshness:
      sla: "Mon/Wed/Fri 07:00 America/Lima"
```

| Field | Required | Validator |
|-------|----------|-----------|
| `kind` | yes | must be `loop` |
| `goal.title` | yes | non-empty |
| `objective_ref` | yes | must resolve to `knowledge/objectives/**/obj-*.md`; if no matching objective exists, secretary (session or brief) prompts el operador to review/create objectives — no loop proceeds with only a local title |
| `success_criteria` | yes | ≥1 entry with `id`, `target`, `source`; may span full funnel (applications + interviews + process) |
| `state` | yes | object (may be empty values in stub) |
| `source` / `freshness` only | N/A | loops use criteria + optional submodule freshness |

**Inbox vs applications pattern (job-search reference):**

| File | Writer | Semantics |
|------|--------|-----------|
| `inbox.md` | Routines (mail crawler, web feeds) | Detected opportunities; triage queue |
| `applications.md` | el operador (interactive sessions); rutinas **leen** criterios y ayudan follow-through (nudges en PR, drafts, sync KPI) | Committed actions + pipeline (postulaciones, entrevistas, avance); hosts **success criteria** progress |
| `sources-web/state.md` | `job-search-crawler` | **Iteration ledger** — run #, stats, dedup ledger, dry-run streaks; may **rewrite** `goal` / `success_criteria` in `contract.yaml` when aligned to `objective_ref` |

### 3.3 Side-by-side summary

| Dimension | Extractor | Loop |
|-----------|-----------|------|
| Purpose field | — | `goal` + `objective_ref` (required) |
| Health | `freshness.sla` + `last_success_at` | `success_criteria` + `state` |
| Evidence | `memory/`, summaries | `inbox.md` + ledgers |
| Goal mutation | N/A | **Routine or session** — update `goal` / criteria between iterations (Ralph); routine proposes pivot when current goal is exhausted |
| Wiki promotion | Via Bibliotecario only | `objective_ref` → `knowledge/objectives/` (canonical strategic store) |

---

## 4. Operational translation

### 4.1 Where definitions live

| Layer | Location | Role |
|-------|----------|------|
| **Instance registry** | `.secretary.yml` `paths.extractors.*`, `paths.loops.*` | Canonical paths; routines resolve via `secretary config path` |
| **Module contract** | `extractors/<m>/contract.yaml`, `loops/<w>/contract.yaml` | Machine-readable minimum; module-local |
| **Durable strategic objectives** | `knowledge/objectives/{strategy,relations}/` | L0/L1 entities; **required** link from loop `objective_ref` |
| **Operational prose** | `state.md`, `applications.md`, playbooks | Human audit trail; may exceed contract |
| **Scheduled binding** | `.cursor/routines/manifest.yaml` | `routine` id in contract must match |

**Rule:** `contract.yaml` is the **audit source of truth** for module kind, loop **goal**, and criteria; `knowledge/objectives/` is the **durable strategic store** — every loop must link one via `objective_ref`. Local `goal.title` operationalizes the linked objective; if no suitable `obj-*` exists, secretary surfaces a review prompt (session or brief) before treating the loop as healthy.

### 4.2 Routine validation (CI)

New script (phase 1): `scripts/ci/validate_module_contract.py`

| Check | Severity |
|-------|----------|
| Every `extractors/*` and `loops/*` has `contract.yaml` | warn (phase 0) → error (phase 1) |
| `kind` matches parent plane | error |
| Extractor with `goal` or `objective` key | error |
| Loop without `goal.title` | error |
| Loop without `objective_ref` resolving to `obj-*.md` | error |
| Loop without `success_criteria` | error |
| `routine` listed in manifest | warn |
| `sink` / `source` paths exist in `.secretary.yml` | error |
| `freshness.last_success_at` older than 2× SLA | warn in CI; alert in pulse |

Integrate in `.github/workflows/ci.yml` alongside `validate_ordenamiento.py` (allowlist unchanged; contract is additive).

### 4.3 pulse / sec-refresh audit

**Readiness checklist** (new section in pulse / sec-refresh skills, phase 1):

1. `secretary validate` (existing) + `validate_module_contract` (new).
2. For each extractor: compare `contract.freshness` vs `state.md` / heartbeat mentions.
3. For each loop: read `success_criteria[].source` file; compute `current` vs `target` where parseable; rutinas may surface gaps in PR body (not reserved for pulse/brief only).
4. Flag loops with stale `iteration_ledger` or dry-run streak beyond threshold (job-search pattern); routine may propose `goal` / criteria rewrite aligned to `objective_ref`.
5. Surface in brief **Resumen de la corrida** or pulse table: `module | kind | health | gap`.

sec-refresh phase 3 (`pre-brief-pipeline`) should call contract health after path validation.

### 4.4 Future UI — secd admin surface

Target API shape (engine follow-up, not this PR):

| Method | Route | Body / response |
|--------|-------|-------------------|
| GET | `/modules` | List extractors + loops from registry + merged `contract.yaml` |
| GET | `/modules/:id` | Full contract + computed health |
| GET | `/modules/:id/health` | `{ freshness_ok, criteria: [{id, target, current, ok}] }` |
| PUT | `/modules/:id/contract` | Admin update goal / criteria (human gate) |
| POST | `/modules/:id/run` | Trigger routine (dispatch integration, future) |

Implementation notes:

- Reuse `objectives.mjs` patterns for parsing frontmatter; contracts are YAML not MD.
- `storeDir` for contracts = module folder (not `knowledge/objectives/`).
- `GET /context` may later include active loop criteria for Axon relay.

---

## 5. Migration path

### Phase 0 — additive stubs (this spec / PR)

- Add `_diseño/specs/L0-fundacion/015-module-contract/spec.md` (this file).
- Add stub `contract.yaml` to `extractors/mail/`, `extractors/meetings/`, `loops/job-search/`.
- Extend `canon/rules/glossary.md` § Loops (Ralph + link).
- CI: optional warn-only if stub missing (defer strict validator).

### Phase 1 — reference implementations

| Module | Actions |
|--------|---------|
| **job-search** | Full `contract.yaml` with `objective_ref`; criteria span funnel (applications + process); postulación casi automática (el operador valida/ejecuta); routine reads criteria + may rewrite goal |
| **mail** | Full extractor contract; `last_success_at` from `state.md` "Última corrida" |
| **meetings** | `contract.yaml` + thin `state.md` (última transcripción) + `freshness.last_success_at` ✅ |

### Phase 2 — validator + pulse integration ✅

- `validate_module_contract.py` enforced in CI. ✅ merged #415
- `contract_health.py` — freshness SLA + loop criteria parse; warn-only CI job `contract-health`.
- pulse/sec-refresh skills read contracts and surface `module | kind | health | gap` table.
- **secd stub:** `GET /modules` deferred; prototype via `secretary modules health` (secretary-core) calling `contract_health.py`.

### Phase 2 deliverables ([#441](https://github.com/<instance-repo>/pull/441))

| Item | Status |
|------|--------|
| `scripts/ci/contract_health.py` | ✅ |
| CI job `contract-health` (warn) | ✅ |
| `pulse` §3.6 + report table | ✅ (harness skill) |
| `sec-refresh` phase 2 checklist | ✅ (harness skill) |
| `secretary modules health` CLI | ✅ secretary-core |
| `success_criteria[].current` sync | `--sync-contract` flag (job-search) |

### Phase 3 — secd admin ✅ (2026-07-02, secretary-core)

| Item | Status |
|------|--------|
| `secretary modules list\|health\|contract get\|put` | ✅ `secretary/modules.py` |
| `GET /modules`, `GET /modules/:id`, `GET /modules/:id/health` | ✅ `secd/lib/modules.mjs` |
| `GET/PUT /modules/:id/contract` | ✅ delegates to CLI |
| Merge `secd/` tree to `main` (daemon MVP) | ✅ mergeado a `main` (verificado 2026-07-27: `git show main:secd/lib/modules.mjs` en `secretary-core` resuelve) |

**Nota (actualizada 2026-07-27):** `secd/` ya vive en `main` de `secretary-core`; la nota
anterior sobre `secd/daemon-mvp` como rama pendiente de merge quedó obsoleta.

### Non-goals (phase 0–2)

- No move of `job-search` files.
- No change to extractor PR branch naming or ETL cut.

---

## 6. Decisiones (el operador)

1. **Loop `state` path** — **[DECISIÓN] (2026-06-29, Phase 1):** `loops/job-search/state.md` en la raíz del workflow es el `state` canónico (snapshot humano + progreso hacia criterios). `sources-web/state.md` queda como **iteration ledger** del submódulo `sources-web` (referenciado en `contract.yaml` → `submodules[].iteration_ledger`). `.secretary.yml` → `paths.loops.job_search.state` apunta a la raíz.

2. **Goal ↔ objective linking** — **[DECISIÓN] (2026-07-02):** Sí — todo loop debe enlazar un objetivo estratégico (`obj-*` en `knowledge/objectives/`) vía `objective_ref`. El `goal.title` local operacionaliza ese objetivo; no basta un título aislado en `contract.yaml`. Si no existe un `obj-*` adecuado, secretary (sesión o brief) debe pedir a el operador revisar/crear objetivos antes de dar el loop por sano.

3. **Success criteria ownership / alcance del loop (job-search)** — **[DECISIÓN] (2026-07-02):** El loop va **más allá de postulaciones** — seguir entrevistas y avance de proceso. Todo artefacto en el repo agente actualiza su KPI. Postular debe ser **casi automático**: el operador valida/ejecuta o pide ejecución cuando hay automatización. Las rutinas **pueden leer** criterios y ayudar con follow-through (nudges en PR, borradores, sync) — no reservado solo a pulse/brief.

4. **Meetings sin `state.md`** — **[DECISIÓN] (2026-07-02):** *Qué se decidía:* si el extractor de reuniones podía omitir `state.md` e inferir frescura solo del mtime del último archivo en `summaries/`, o si debía tener `state.md` explícito como mail/whatsapp. *Resolución:* **exigir `state.md` delgado** (última transcripción procesada, legible por humanos) **y** `freshness.last_success_at` en `contract.yaml` (auditoría mecánica vía `contract_health.py`). El mtime de `summaries/` no es fuente de verdad de salud. Ya implementado: `extractors/meetings/state.md`, `sink.state` en contract, allowlist en `validate_ordenamiento.py`.

5. **Ralph goal mutation** — **[DECISIÓN] (2026-07-02):** La **rutina** del loop puede reescribir `goal` y `success_criteria`, siempre alineados al `objective_ref` estratégico. Si bajo el goal actual no queda nada que lograr, debe **proponer** cómo actualizar meta/goal (no estancarse en silencio). Sesiones interactivas también pueden mutar con OK del operador.

---

## References

- ``_diseño/.specify/memory/constitucion-operativa.md`` (instance path) §2.1–2.2
- [`012-instance-layout-extractors-knowledge/spec.md`](../012-instance-layout-extractors-knowledge/spec.md)
- ``knowledge/objectives/_schema.md`` (instance path)
- ``loops/job-search/applications.md`` (instance path) — success criterion example
- ``loops/job-search/sources-web/state.md`` (instance path) — iteration ledger
- ``extractors/mail/state.md`` (instance path) — extractor operational state
- Reunión ``2026-06-29-session-notes-loops-speckit`` (instance path)
