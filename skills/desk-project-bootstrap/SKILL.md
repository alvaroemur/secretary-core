---
name: desk-project-bootstrap
description: >-
  Intake questionnaire plus step-by-step bootstrap for a new client/engagement
  project, always crossing people and orgs through desk-recall (wiki, meetings,
  mail, unmerged captures) before creating folders. Triggers: "/desk-project-bootstrap",
  "bootstrap this project", "new engagement", "project intake questionnaire",
  starting a project from a brief/deck/PDF.
---

# desk-project-bootstrap

**What this does:** turn a brief, deck, or “new project” intent into a filled
intake + project home — but only after `desk-recall` (and extractor freshness when
needed) has crossed leads, client, and related signals so the folder is not built
from the attachment alone.

Doctrine: `rules/skills-contract.md` · Cowork skeleton: `desk-cowork-fit` · memory: `desk-recall` · entity contract: spec 025

## Guardrails

- **Recall before mkdir.** Never create a project home from a deck/PDF alone when
  named people or orgs are present.
- **Read vs infer.** Cite recall sources; mark inferences; surface conflicts
  (e.g. deck branded Org A, owner says client is Org B).
- **No inventing phases** under execution. Empty execution dir until the owner names phases.
- **Ask before mkdir** if target path or client slug is ambiguous.
- No commit / push / PR / third-party send unless the owner asks.
- Do not embed instance paths, account emails, or owner proper names in this skill
  (resolve via `secretary config` / runtime AGENTS.md).

## Skill chain

| Need | Delegate |
|------|----------|
| Person / org / topic memory (+ unmerged scan) | **`desk-recall` (required)** |
| Live mail / invites touching the engagement | `desk-mail` step 0, then recall |
| Meeting just ended / facilitation kickoff call | `desk-meeting` step 0, then recall |
| Drive folder for the client/event | `desk-drive` step 0, then recall |
| WhatsApp with lead/team | `desk-whatsapp` step 0, then recall |
| Cowork folder skeleton (perfil + dirs + README seed) | `desk-cowork-fit` (`bootstrap` / `apply`) |
| Persist a confirmed fact to wiki/memory | `desk-write` (only if owner asks) |
| Entity contract (`contract.yaml`) | This skill — emit from intake (spec 025). Fit does not overwrite. |

---

## Loop

### 0 — Subjects from the seed

From the user message + attachments, extract a **recall subject set** (min 1):

- Delivery lead (person)
- Client / contracting org
- Event or program name (if distinct)
- Each named co-facilitator / core teammate
- Working title / project phrase

If the seed mentions calendar invites, mail threads, or a call that just happened →
run the matching extractor skill’s **step 0** (or `secretary fresh <module> --format json`)
**before** recall.

### 1 — `desk-recall` (required)

For each subject in the set (batch when practical):

```bash
secretary recall "<subject>" --format json
```

Then follow **`desk-recall` fully**: wiki → module memory → wip → **unmerged `auto-*` PR scan**.
Synthesize; do not dump raw hits.

Fold recall into intake fields. Especially:

| Intake field | Typical recall source |
|--------------|----------------------|
| Delivery lead / relation | wiki person article, meetings |
| Team identities (email → full name) | mail/calendar memory, unmerged wiki PRs |
| Prior work with same lead/org | meetings, Drive proyectos |
| “What this is NOT” | owner statement + conflicting brand on deck |
| Next meeting / dates | calendar + mail (fresh-first) |

Mark every filled field as `recorded` (`source:date`) or `(inferred)`.

### 2 — Questionnaire (fill gaps with owner)

Copy and complete. Skip rows already solid from recall. Use `TBD` when unknown.

```markdown
# Project bootstrap — intake

## Identity
- Working title:
- Project slug (lowercase-hyphen):
- Client / contracting org:
- Client slug:
- End beneficiary / event / program (if different):
- What this is NOT:

## Ownership
- Delivery lead:
- Owner role / accountabilities:
- Core team (name → role):
- Sponsor / client contact:
- Billing vehicle:

## Scope
- Engagement type: facilitation | consulting | product | research | other:
- One-sentence outcome:
- In scope:
- Out of scope:
- Key artifacts expected:
- Source materials on hand:

## Timing
- Status: prospect | proposed | awarded | in delivery:
- Key dates:
- Next meeting / checkpoint:

## Homes
- Management workspace root:
- Proposed project folder path:
- Durable file store (Drive / other):
- Code repo (or none):
- Scratch (or none):

## Folder profile
- Profile: client-engagement | product-jv | custom:
- Include admin folder? yes | no | later:
- Include living log? yes | no | later:
- Skeleton: default | match workspace convention | custom list:

## Recall cross-check
- Subjects recalled:
- Conflicts (deck vs memory vs owner):
- Tentative unmerged evidence (PR #):

## Risks / notes
- Open questions:
- Constraints (NDA, brand, languages, travel):
```

**Minimum to unblock mkdir:** client (or TBD slug), project slug, target parent path, owner role.

### 3 — Present intake (🚧)

Header: `Bootstrap intake — <working title>`

Dense table or labeled list. Include a short **Recall cross-check** (lead, client, team, conflicts).
Ask confirmation of path + profile before creating dirs (unless the owner already ordered
bootstrap with an unambiguous path).

### 4 — Create project home

**If the target is under the owner’s Cowork proyectos tree** → hand the folder to
`desk-cowork-fit` (`bootstrap` or `apply` after 🚧 OK). Do not fork a second skeleton policy.

**Otherwise** (non-Cowork / custom root), use a minimal default:

```text
README.md
01-admin/          # optional
02-inputs/
03-execution/
04-comms/
05-deliverables/
06-log/            # optional
```

Match local naming if a workspace convention exists (e.g. numbered Spanish dirs).

### 5 — Seed files

- Write `README.md` from intake (identity, team, scope, timeline, homes, gaps).
- Write `01-admin/BOOTSTRAP.md` (or local admin equivalent) with the filled questionnaire
  **including the Recall cross-check section**.
- Write root `contract.yaml` from `$SECRETARY_INSTANCE/templates/contract.example.yaml`
  (spec 025). Map intake → identity, status.phase, mirrors (homes). `type`: `proposal` if
  status is prospect/proposed **and** the owner said this is a bid; else `project`.
  `edt.activities`: only phases the owner named; `validated_at` / `validated_by` stay
  null until the owner confirms the tree (🚧). Do **not** invent phases. Do **not**
  overwrite an existing `contract.yaml` unless the owner OK'd replace.
- Copy source briefs/decks into inputs with `YYYYMMDD-` prefixes.
- Leave execution empty unless the owner named phases.

### 6 — Close-out report

```
## desk-project-bootstrap — <slug>
- path: …
- recall subjects: …
- conflicts / tentative: …
- dirs created | skipped:
- files seeded:
- contract.yaml: created | skipped (exists) | TBD
- TBD / risks:
→ next: …
```

Suggested next often: kickoff agenda, contract under admin, or `desk-write` for a new
person/org fact confirmed in session.

---

## Out of scope

- Portfolio-wide Cowork audit → `desk-cowork-audit`
- Persisting wiki articles without owner OK → offer `desk-write`, do not auto-write
- Running the engagement work itself (facilitation design, code, proposals beyond intake)
