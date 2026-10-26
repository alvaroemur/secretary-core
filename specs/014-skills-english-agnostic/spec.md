---
id: "014"
slug: skills-english-agnostic
layer: L0
status: fase 3
last_reviewed: 2026-07-03
implemented:
  - $SECRETARY_INSTANCE/canon/rules/skills/skills-contract.md
  - $SECRETARY_INSTANCE/canon/operational/briefing.md
  - $SECRETARY_INSTANCE/scripts/ci/validate_paths.py
  - $SECRETARY_INSTANCE/scripts/ci/validate_ordenamiento.py
  - $SECRETARY_INSTANCE/scripts/ci/validate_harness_paths.py
gaps:
  - playbooks grandes sin traducir (housekeeping, wiki-update, drive-crawler, job-search-crawler, whatsapp-monitor)
  - canon/rules/skills/skills.md export EN
---

# Spec — Feature 014: skills English + instance-agnostic

**Estado:** `fase 3` — inventario + CI harness grep; `revision-correo` y `reuniones-update` traducidos (harness); playbooks grandes restantes pendientes  
**Branch:** `diseño/014-skills-phase2`  
**Worktree:** `~/.wt/secretary-014-p2`

---

## Problem

Secretary skills and scheduled playbooks mix **Spanish prose**, **hardcoded instance paths**
(`$SECRETARY_INSTANCE`, `<owner>@…`, `<github-user>/…`, `America/Lima`), and **personal layout** (`<cowork-root>/…`).
That blocks exporting the harness layer to other instances and duplicates config that already
belongs in `.secretary.yml` / `operational/`.

## Architecture decision

| Concern | Owner | Resolution |
|---------|-------|------------|
| Skill mission, guardrails, loop, report shape | Harness `SKILL.md` (English) | `canon/rules/skills/skills.md`, `canon/rules/skills/skills-contract.md` |
| Paths (extractors, wiki, subsystem) | `.secretary.yml` → `paths.*` | `secretary config path <key>` |
| Instance root / engine root | Env vars | `SECRETARY_INSTANCE`, `SECRETARY_CORE` |
| Google accounts | `.secretary.yml` → `accounts` | `secretary config show` → `.accounts` |
| Calendar day boundary | `.secretary.yml` → `timezone` | `secretary config show` → `.timezone` |
| Daily brief GitHub target | `.secretary.yml` → `brief` | `secretary config show` → `.brief` |
| Brief accounts, calendar, labels | `canon/operational/briefing.md` | Instance appendix (phase 2) |
| Dispatch allowlist | `.secretary.yml` → `dispatch.executor.repos` | `secretary config show` |
| User language, clients, Cowork map | Instance `CLAUDE.md` | Not in skills |
| Wiki/memory prose language | Instance data | Spanish OK |

**CLI exposure:** `secretary config show` includes `timezone` and `brief` (engine change in `secretary-core/secretary/config.py`).

---

## Audit table (2026-07-01, post phase 2)

Legend: **ES** = Spanish body · **PATH** = hardcoded instance path · **ID** = personal identifiers · **OK** = mostly compliant

### Harness skills (`~/.claude/skills/`)

| Skill | ES | PATH | ID | Notes |
|-------|:--:|:----:|:--:|-------|
| `sec-refresh` | **OK** | **OK** | **OK** | Phase 1 |
| `pulse` | **OK** | **OK** | **OK** | Phase 1 |
| `sec-recall` | **OK** | **OK** | **OK** | Phase 1 |
| `sec-heartbeat` | **OK** | **OK** | **OK** | Phase 1 |
| `sec-mail` | **OK** | **OK** | **OK** | Phase 2 |
| `sec-meeting` | **OK** | **OK** | **OK** | Phase 2 |
| `sec-compose` | **OK** | **OK** | **OK** | Phase 2 |
| `sec-write` | **OK** | **OK** | **OK** | Phase 2 |
| `sec-merge` | **OK** | **OK** | **OK** | Phase 2 |
| `wiki-write` | **OK** | **OK** | **OK** | Phase 2 — prose language deferred to instance |
| `wind-down` | **OK** | **OK** | **OK** | Phase 2 |
| `dispatch` | **OK** | **OK** | **OK** | Phase 2 |
| `handover` | **OK** | — | **OK** | Phase 2 — report prose per instance CLAUDE.md |
| `sec-state` | partial | — | — | English mission; Spanish report header — phase 3 |
| `drive-sync` | ✓ | ✓ | ✓ | Phase 3 |
| `sec-consolidate` | ? | ? | ? | Not audited line-by-line |
| `sec-sys-annotate` | partial | ? | — | Internal primitive |
| `sec-sys-integrate` | partial | ? | — | Internal primitive |
| `visual-thinking` | ✓ | ✓ | ✓ | Domain skill — phase 3 boundary |
| `jarvis` | ✓ | — | ✓ | Persona — low priority |
| `babysit`, `pr-sync`, `split-to-prs` | EN | low | — | Generic Cursor skills |
| `speckit-*`, `to-cursor`, `setup-ci` | EN | low | — | Out of secretary scope |

### Scheduled playbooks (`~/.claude/scheduled-tasks/*/SKILL.md`)

| Playbook | ES | PATH | ID | Notes |
|----------|:--:|:----:|:--:|-------|
| `secretary-briefing` | **OK** | **OK** | partial | Phase 2 — English; IDs in `canon/operational/briefing.md` |
| `revision-correo` | **OK** | **OK** | **OK** | **translated 2026-07-03** (harness) |
| `reuniones-update` | **OK** | **OK** | **OK** | **translated 2026-07-03** (harness) |
| `housekeeping` | ✓ | ✓ | ✓ | Phase 3 |
| `wiki-update` | ? | ? | ? | Phase 3 |
| `drive-crawler` | ? | ? | ? | Phase 3 |
| `dispatch-executor` | ? | ? | ? | Phase 3 |
| `job-search-crawler` | ? | ? | ? | Phase 3 |
| `whatsapp-monitor` | partial | ✓ | — | Phase 3 |
| `sec-heartbeat` (scheduled) | ✓ | ✓ | — | Mirror harness skill |
| `tidy-up` | ? | ? | ? | Phase 3 |

### Instance canon (`.secretary/`)

| File | ES | PATH | Notes |
|------|:--:|:----:|-------|
| `canon/rules/skills/skills-contract.md` | — | — | Phase 1; cross-link `canon/operational/briefing.md` phase 2 |
| `canon/operational/briefing.md` | — | ID | **Created phase 2** — instance brief appendix |
| `canon/rules/glossary.md` | partial | — | Updated phase 1 |
| `canon/rules/skills/skills.md` | ✓ | — | Phase 3 export candidate |
| `canon/operational/skills-vs-operational.md` | ✓ | partial | Phase 1 cross-refs |
| `.secretary.yml` | ✓ | — | `timezone`, `brief` keys |
| `CLAUDE.md`, `AGENTS.md` | ✓ | ✓ | Instance runtime — Spanish OK |

### Engine (`secretary-core`)

| File | Notes |
|------|-------|
| `cli/README.md` | Phase 3 |
| `secretary/config.py` | PR #9 — `timezone`, `brief` in `config show` |
| `secretary/status.py` | PR #9 — reads `brief.repo`/`label` from config |

---

## Phase 1 delivered

- `canon/rules/skills/skills-contract.md`, glossary cross-link, `.secretary.yml` `timezone`/`brief`
- Harness: `sec-refresh`, `pulse`, `sec-recall`, `sec-heartbeat`
- Engine: `config show` extensions

## Phase 2 delivered (2026-07-01)

### Instance repo (git)

- `canon/operational/briefing.md` — accounts, calendar appendix, brief labels, timezone, assignee
- `canon/rules/skills/skills-contract.md` — pointer to `canon/operational/briefing.md`

### Harness skills (not in git)

- `sec-compose`, `sec-write`, `wiki-write`, `wind-down`, `dispatch`, `sec-merge`, `handover`
- `sec-mail`, `sec-meeting` (completed in #385 partial + this pass)

### Scheduled playbook (not in git)

- `secretary-briefing/SKILL.md` — English; defers instance IDs to `canon/operational/briefing.md` + config

---

## Backlog — phase 3 (GitHub #427)

### Parity criterion (ES/EN)

| Layer | Language | Paths / IDs |
|-------|----------|-------------|
| Mission, phases, guardrails, report shape | **English** | Harness `SKILL.md` body |
| Instance data (wiki, memory prose) | Spanish OK | `extractors/*/memory/`, wiki articles |
| Paths | **Config only** | `secretary config path <key>` — no `$SECRETARY_INSTANCE` literals |
| Accounts, brief repo, timezone | **Config** | `.secretary.yml` + `canon/operational/briefing.md` |
| User-facing deliverables in PRs | Spanish OK | Routine reports to owner |

**Done when:** playbook passes `validate_harness_paths.py` with `VALIDATE_HARNESS_STRICT=1`.

### Scheduled playbooks inventory (2026-07-03)

| Playbook | Lines | EN mission | Config paths | Status |
|----------|------:|:----------:|:------------:|--------|
| `secretary-briefing` | 239 | ✅ | ✅ | phase 2 |
| `sec-heartbeat` (scheduled) | 84 | ✅ | ✅ | phase 3 mirror |
| `dispatch-executor` | 57 | ✅ | ✅ | **translated 2026-07-03** |
| `tidy-up` | 150 | ✅ | ✅ | **translated 2026-07-03** |
| `revision-correo` | 374 | ✅ | ✅ | **translated 2026-07-03** (harness) |
| `reuniones-update` | 509 | ✅ | ✅ | **translated 2026-07-03** (harness) |
| `housekeeping` | 373 | ⏳ | partial | pending |
| `job-search-crawler` | 179 | ⏳ | partial | pending |
| `whatsapp-monitor` | 380 | ⏳ | partial | pending |
| `drive-crawler` | 515 | ⏳ | partial | pending |
| `wiki-update` | 650 | ⏳ | partial | pending |

### Delivered phase 3 (instance repo)

1. `scripts/ci/validate_harness_paths.py` — banned pattern grep (warn-only CI; strict via env).
2. Issue doc: `_diseño/issues/skills-playbooks-phase3.md`.
3. Harness translations: `dispatch-executor`, `tidy-up`, `revision-correo`, `reuniones-update`.

### Remaining

1. Translate large playbooks: `housekeeping`, `wiki-update`, `drive-crawler`, `job-search-crawler`, `whatsapp-monitor`.
2. `sec-state` report header; `canon/rules/skills/skills.md` English export.
3. `cli/README.md` English cleanup (engine).

## Backlog — phase 4

1. `SECRETARY_SCHEDULED_TASKS` env for harness path
2. Optional `secretary config path brief.repo` shorthand; `brief.assignee` in YAML
3. Promote `skills-contract.md` link in `AGENTS.md` and instance `CLAUDE.md` § skills

---

## Test plan (phase 2)

- [x] Phase 2 harness skills use `secretary config` / `SECRETARY_*` — no literal `$SECRETARY_INSTANCE` in skill bodies
- [x] `secretary-briefing` references `canon/operational/briefing.md` for accounts/calendar/labels
- [x] `validate_paths.py` and `validate_ordenamiento.py` pass on instance repo (2026-07-02 — removed legacy `correo/`)
- [x] Brief refresh still finds issue via `brief.repo` jq block (`secretary config show` → `<instance-repo>`, label `tipo:informe-diario`)

---

## Related

- Spec 011 (sistemas ordenamiento) — operational tables stay Spanish
- Spec 012 (instance layout) — canonical English folder names
- Spec 013 (sec-refresh) — skill behavior; body now English
