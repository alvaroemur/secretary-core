---
name: revision-correo
description: >-
---

Read instance `AGENTS.md` at `SECRETARY_INSTANCE` before starting. Instance appendix:
`operational/briefing.md` (Google accounts, calendar). Doctrine: `rules/skills-contract.md`.

# revision-correo — evening mail batch

Review mail from the last 24 hours and complete the tasks below. Run output is delivered as a
**Pull Request** that acts as the report: the owner reads it on GitHub and merges.

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
DOW=$(TZ="$TIMEZONE" date '+%A')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
BRIEF_LABEL=$(echo "$CFG" | jq -r '.brief.label // "tipo:informe-diario"')
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
WORK_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.inspiro // .accounts.work // empty')
ENNUI_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.ennui // empty')

if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$SECRETARY_INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
```

## W. Isolated worktree (do this first)

This run does **not** write to the main working copy. Create an ephemeral worktree from
`origin/main`, work there, then open a PR at the end.

```bash
set -euo pipefail
REPO="$SECRETARY_INSTANCE"
cd "$REPO"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=correo
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
git worktree add -b "$BRANCH" "$WT" origin/main
echo "WT=$WT  BRANCH=$BRANCH"
```

From here on, **all WRITE paths hang off `$WT/`** (`$WT/extractors/mail/state.md`,
`$WT/extractors/mail/memory/...`, `$WT/extractors/mail/policy.md`,
`$WT/loops/job-search/inbox.md`), never from `$SECRETARY_INSTANCE/` directly. Context reads
(policy, settings, wiki) also come from `$WT/` (fresh `main` checkout = last merged state).
Gmail is external: labeling/archiving via `gog` operates on the account and does not depend on the
worktree.

> Operations: this routine's bookkeeping lives in the PR, not on `main`. Merge auto PRs daily; if
> they pile up unmerged, the next run starts from `main` and may repeat work.

## 0. Preparation

### 0.1 — sec-status from open brief

Before drafting replies or follow-ups, read `sec-status` comments on today's open briefing issue
(`BRIEF_LABEL`, state `open`):

```bash
BRIEF=$(gh issue list --repo "$BRIEF_REPO" --label "$BRIEF_LABEL" --state open \
  --json number --jq 'sort_by(.createdAt) | last | .number')
gh issue view "$BRIEF" --repo "$BRIEF_REPO" --json comments \
  --jq '.comments[] | select(.body | contains("sec-status")) | .body' | grep "sec-status ·"
```

- Items with `🚫` → **cancelled**. Do not create follow-up drafts or carry them as pending.
- Items with `✅` → already done. Do not duplicate work.

### 0.2 — Relational anchor (wiki contacts)

For senders that exist in `$WT/knowledge/wiki/articulos/personas/`, before drafting:

1. `grep -r "<name|email>" "$WT/extractors/meetings/summaries/" -l --include '*.md'` — meetings in
   the last 14 days.
2. If there was a meeting **<48h** with that person → **continuation** tone, not a new-meeting pitch.
   Delegate the draft to `sec-compose` (channel: email) anchored on recent conversation.
3. Active collaborators (ongoing project, recent meeting) → always route through `sec-compose`
   instead of cold drafting.
4. Project with structured state available — before defaulting to a cold draft, check whether the
   sender/thread maps to a `proyecto` (same normalization `reuniones-update` uses on `contexto`)
   that has either: (a) an active entry in `$WT/subsystem/wip/<repo>.md`, or (b) frontmatter on
   `~/Cowork/<workspace>/proyectos/<slug>/README.md`. If either exists → route through `sec-compose`
   too, even if it doesn't meet triggers 2/3 above. No match → no change, fall through to normal
   cold-draft or trigger 3.

### 0.3 — Persist draft copy (Gmail thread replies only)

**Inbox thread replies only** — not project deliverables. Proposals/decks/commercial docs belong
in the target org's Cowork project folder per instance `AGENTS.md` § domain dispatch and
`operational/sistemas-ordenamiento.md` §6.1 (`<cowork>/<org>/proyectos/<slug>/borradores/`).

Besides the Gmail draft, save text to `$WT/extractors/mail/drafts/YYYY-MM-DD-<slug>.md` **only for
thread replies** (slug = recipient or short subject). Format: recipient, subject, thread-id, draft
body, status (`listo-revisar` / `pendiente-rewrite`).

If content is a project deliverable (proposal, deck, working document), do not persist it under the
secretary instance: save in the Cowork project `borradores/` path and reference that path in the
report.

### Tools

Use `gog` (Google Workspace CLI) for Gmail read/write.

`GOG_KEYRING_BACKEND`, `GOG_KEYRING_PASSWORD`, and `GOG_ACCOUNT` are already in harness
`settings.json` under `env`.

**Multi-account.** This routine covers up to three accounts: `PERSONAL_ACCOUNT` (always active),
`WORK_ACCOUNT` (Inspiro, corporate), and `ENNUI_ACCOUNT` (ennui.solutions, hub de desarrollo).
Check each additional account before using it:

```bash
WORK_ACTIVE=false
if [ -n "$WORK_ACCOUNT" ] && \
   gog gmail search 'newer_than:1d' --account="$WORK_ACCOUNT" --max 1 --plain --no-input 2>/dev/null; then
  WORK_ACTIVE=true
fi

ENNUI_ACTIVE=false
if [ -n "$ENNUI_ACCOUNT" ] && \
   gog gmail search 'newer_than:1d' --account="$ENNUI_ACCOUNT" --max 1 --plain --no-input 2>/dev/null; then
  ENNUI_ACTIVE=true
fi
```

For each active account: run the full mail sweep (search, triage, archive, drafts, follow-up) adding
`--account="$ACCOUNT"` on every `gog` call. Consolidate all accounts into one PR with **separate
sections per account** in the report. For inactive accounts, add one line:
`⚠️ $ACCOUNT not registered in gog — see instance AGENTS.md § Google accounts`.

The `policy.md` inbox/archive/delete rules apply to **all accounts** unless a rule explicitly names
one. Account-specific rules (e.g. a capture-only account) are noted in `policy.md`.

**Compact output — use `--plain`, not `--json`, for reading.** `gog ... --json` returns huge payloads
(a `thread get --json` ~49 KB) that the harness truncates into `tool-results/<id>`, which you then
read with `cat` — wasted round-trips and tokens. `--plain` gives stable compact TSV/text (same thread
~870 B, ~57× smaller) with everything needed to triage (ID, date, from, subject, labels) **and
includes each message id**. Reserve `--json`/`--full` for the single thread you will **reply to**
(when you need the full body), never for the sweep.

Useful commands:
- Search **all** mail from the last 24h (any folder, not just Inbox):
  `gog gmail search 'newer_than:1d -in:chats' --max 100 --plain --no-input`
- Recent sent (for follow-up): `gog gmail search 'in:sent newer_than:7d' --max 50 --plain --no-input`
- Label: `gog gmail labels modify <threadId> --add "Etiqueta" --no-input`
- Archive (= Queue/Delete): `gog gmail labels modify <threadId> --remove INBOX --no-input`
- View thread (triage): `gog gmail thread get <threadId> --plain --no-input` — add `--full` only if
  you need the body to draft a reply.
- Create draft (thread reply):
  `gog gmail drafts create --to "email" --subject "Re: subject" --body "text" --reply-to-message-id <messageId> --json --no-input`

**NEVER move to Trash.** This routine never deletes mail. "Queue/Delete" means **archive**
(`--remove INBOX`), never `--add TRASH`.

If `gog` is unavailable, use Gmail MCP tools as fallback (read + drafts only — note: MCP does not
support reply-to; drafts may be orphaned from the thread).

### Context — read before acting

Read these files at the start of each run:

1. **Classification policy**: `$WT/extractors/mail/policy.md`
   Rules for Queue/Delete labels, archive, inbox retention, and priority senders.

2. **Current state**: `$WT/extractors/mail/state.md`
   Active projects, recurring billing issues, upcoming events, and prior inbox state.

3. **User adjustments**: `$WT/extractors/mail/settings.md`
   Corrections the owner made to prior decisions. Apply as rules.

4. **Personal wiki**: `$WT/knowledge/wiki/articulos/`
   Person (`personas/`), organization (`organizaciones/`), and topic (`temas/`) articles. Consult
   when a sender or actor appears in mail.

5. **Routine memory**: the 2–3 most recent files in `$WT/extractors/mail/memory/`
   Daily memos from prior runs. Do not duplicate what is already in `state.md`.

## 1. Summary by category

Cover **all mail from the last 24h**, not only what remained in Inbox. Explicitly include messages
auto-archived or auto-labeled by Gmail filters (`gog gmail search 'newer_than:1d -in:chats'`, do not
restrict to `in:inbox`). Important items may have been auto-archived by a rule; surface them anyway.

- **Important / personal**: direct messages or CC on active topics. Include sender, subject, brief
  summary.
- **Action required**: mail needing a reply or action (direct questions, requests, confirmations,
  payments).
- **Events and invitations**: meetings, webinars, or events invited to.
- **Newsletters and subscriptions**: brief summaries.
- **Job alerts**: one grouped line with the most relevant roles.
- **Promotions / spam**: mention briefly if any, no detail.

**Ticket candidate (issue cowork-secretary#512):** if an "action required" mail is a client
requesting new work (not a routine follow-up), flag it in the report as a ticket candidate — e.g.
"📎 posible ticket: <client> pide <thing> — ver `subsystem/contratos/tickets.md`". Never write the
ticket file yourself; the owner decides what counts as billable/trackable work and registers it
manually.

## 2. Reply drafts

For "important" and "action required" mail, create drafts with a professional but warm tone
consistent with the owner's style (see `settings.md`). Do not reply to bulk mail where an individual
response is not expected.

**IMPORTANT**: Always use `gog gmail drafts create --reply-to-message-id <messageId>` so the draft
stays in the original thread. The messageId appears in `--plain` thread output (line
`Message N/N: <id>`); if you need the body to draft, use
`gog gmail thread get <threadId> --plain --full`.

## 2.5 Sent-mail follow-up (no reply yet)

Review mail **sent in the last 7 days** and detect threads still awaiting a reply, to decide whether
follow-up is warranted.

1. List recent sent: `gog gmail search 'in:sent newer_than:7d' --max 50 --plain --no-input`.
2. For each thread, open it (`gog gmail thread get <threadId> --plain`) and check whether the
   **last message in the thread is mine** (no recipient reply after). If the last message is theirs,
   the thread already got a reply → skip.
3. Of those still unanswered, **evaluate follow-up merit**:
   - **Warrants follow-up** (create draft): I asked for something concrete (answer, decision,
     payment, document, scheduling), or it is a priority contact/project (see `policy.md` and wiki),
     and a reasonable margin has passed (≥3 business days without reply; use judgment on urgency).
   - **Does not warrant** (create nothing): informational / no reply expected, bulk send, very
     recent prior follow-up, recipient usually replies slowly and it is still early, or process is
     **cancelled** per sec-status / `state.md`.
4. For those that warrant it, **create a follow-up draft** in the same thread
   (`--reply-to-message-id` on my last message), warm and brief, reminding the pending point without
   sounding pushy. Match owner style (`settings.md`).
5. **Never send** — leave drafts for owner review. List each suggested follow-up in the report
   (recipient, subject, why) and each evaluated-and-skipped thread in one line.

## 2.6 Drafts acumulados en un mismo hilo (consolidación)

Gmail permite múltiples drafts por hilo vía API, pero su UI solo muestra el último — un draft
sustancial puede quedar invisible mientras se crea uno nuevo más corto sobre el mismo hilo,
perdiendo contenido. Caso real que motivó esto: hilo con Juliana Villalba (ERP CLab) con un draft
del 3-jul (sílabo completo de 10h) y otro del 8-jul mucho más corto que no lo reaprovechaba —
ambos seguían sin resolver un mes después.

1. Listar drafts de la cuenta: `gog gmail drafts list --account="$ACC" --json`.
2. Agrupar por `threadId`. Grupos con **2 o más drafts** son candidatos.
3. Filtrar por umbral de días desde el draft **más antiguo** del grupo:
   `mail.settings.consolidacion_drafts_umbral_dias` (default 6 si `settings.md` no define el campo).
4. Antes de sintetizar, chequear si hubo respuesta real del destinatario en el hilo desde el draft
   más viejo: `gog gmail thread get <threadId> --plain --no-input --account="$ACC"`. Si respondió
   después de esa fecha → **no consolidar**, el contexto cambió más que solo el tiempo transcurrido;
   marcar el hilo para revisión manual en el reporte y seguir con el siguiente candidato.
5. Sin respuesta intermedia → traer el detalle de cada draft del grupo:
   `gog gmail drafts get <draftId> --json` (headers, body, `internalDate`).
6. Sintetizar un draft consolidado: preservar la sustancia del draft **más completo** (no
   necesariamente el más reciente), con el tono/urgencia ajustado a que pasó tiempo, sin sonar como
   excusa ("retomo esto que quedó pendiente..." en vez de ignorar o negar la demora). Tono de
   `settings.md` (Abrazo, tuteo, conciso). Si hay más de 3 grupos candidatos en la corrida, delegar
   la síntesis de cada uno a un subagente aislado — no bloquear el resto de la corrida.
7. Actualizar el draft en Gmail vía `sec-mail` con `intent=update-draft`: `draft_id` = el que se
   mantiene vivo, `body` = el consolidado, `superseded_draft_ids` = el resto del grupo.
8. **Nunca borrar los drafts superseded automáticamente** — `gog gmail drafts delete` es
   irreversible y no pasa por Trash. Listarlos en el reporte para confirmación explícita del owner.
9. Reportar cada grupo procesado: hilo/destinatario, cuántos drafts tenía, fecha del más viejo,
   acción tomada (consolidado / revisión manual por respuesta intermedia / bajo el umbral, sin
   acción).

## 3. Inbox cleanup

Apply `policy.md` rules with `gog gmail labels modify`. When in doubt, **prefer leaving in inbox**.

Pending detection (CRITICAL) — before archiving or labeling any message:
- Direct unanswered question? → do NOT archive; add to "Action required"
- Pending payment or billing? → do NOT archive; mark action required
- Future event invitation? → do NOT archive; include in "Events"
- Pending procedure? → do NOT archive; mark action required
- Priority sender? → do NOT archive; include in "Important"

## 4. Inbox Zero

After processing last-24h mail, check total inbox count. If more than 30 remain, sweep in batches
of 50 starting with oldest, applying the same rules.

Continue until inbox ≤30 or all processed. Priority: >30 days, then >7 days, then the rest.

## 5. Final report (daily)

This report is **not printed standalone**: write it to a temporary Markdown file and use it as the
**Pull Request body** (see "## W2. Close"). Include:

### Mail from the last 24h
- Summary by category (Section 1)
- Drafts created (Section 2)

### Sent follow-up (Section 2.5)
- Follow-up drafts created (recipient, subject, reason)
- Sent threads evaluated and skipped (one line each)

### Drafts consolidados (Section 2.6)
- Hilos consolidados (destinatario, cuántos drafts tenía, draft vivo actualizado)
- Superseded pendientes de confirmación para borrar (draft-id uno por uno)
- Hilos marcados para revisión manual (respuesta intermedia detectada)

### Inbox cleanup
- How many labeled Queue/Delete (with examples)
- How many archived (with examples)
- How many remain and why
- Recurring billing issues

### Inbox state
- Total remaining messages
- Breakdown: action pending vs. reference
- Whether Inbox Zero was reached or how many remain

## 6. Weekly report (Fridays only)

If `DOW` is `Friday`, besides the daily report, generate an extended report covering the full week
(since prior Friday):

1. **Archived summary**: search archived and Queue/Delete-labeled mail from the last 7 days. Group
   by type and summarize what arrived.
2. **Relevance review**: check whether anything archived/deleted might have been relevant. Flag
   items worth a second look.
3. **Unsubscribe suggestions**: for recurring senders never relevant, check for unsubscribe links and
   list with instructions.
4. **Inbox evolution**: compare inbox state vs. prior Friday (if a memo exists).

## 7. State update

At the end of each run, update:

### `state.md`
Rewrite with current state: active projects, billing issues, upcoming events, inbox state. Rolling
file, not cumulative.

### `extractors/mail/memory/YYYY-MM-DD.md` (daily memo)
Write to `$WT/extractors/mail/memory/YYYY-MM-DD.md`.

Only **durable, non-derivable** information:
- New or updated projects/commitments (with contacts and dates)
- New data on people or organizations (roles, relationships, emails) → feeds wiki
- New suggested priority senders (to add to `policy.md`)
- Patterns or anomalies
- Owner corrections

Do NOT store: mail summary, re-readable mail content, inbox state, info already in `state.md` or
`policy.md`.

Read the 2–3 most recent memos before writing to avoid duplication.

### `policy.md`
If new senders should be added to archive or delete lists during the run, add them directly to
`policy.md` in the right section with a dated note in "Notas de evolución".

### `loops/job-search/inbox.md` (job opportunities)
When relevant job opportunities appear in LinkedIn alerts or other sources, add each to
`$WT/loops/job-search/inbox.md` under "Pendientes de revisión" with: role, org, city, direct job
posting link, source mail reference, and a brief note. Evaluate fit vs. owner profile (social
impact, sustainability, AI, project management, Latam, leadership). Only record good fits.
Discarded ones go under "Descartadas" with one line.

### Wiki (indirect update via consolidados)

Do NOT write directly to wiki during the run. Flow:

1. **Daily memo** (`memory/YYYY-MM-DD.md`) — historical run log (described above).
2. **Consolidados** (`memory/personas.md`, `memory/organizaciones.md`, `memory/entidades.md`,
   `memory/suscripciones.md`) — persistent files accumulating items pending wiki integration.
   **This is what `wiki-update` consumes.**

When you discover a new person / organization / entity / subscription or new data on an existing one:

a. **Before adding**, read `$WT/knowledge/wiki/articulos/` to verify whether an article already
   exists. If it exists, record only **new data** the wiki does not yet have.

b. Add an item to the matching consolidado with this format:

```markdown
## <Full name>
- email: <email if applicable>
- contexto: <brief description of discovery>
- fuentes: gmail:<message-id>, ...
- detectado: YYYY-MM-DD
- pendiente_wiki: true
```

c. If uncertain (incomplete surname, ambiguous org), add a `# duda: ...` line. `wiki-update` will
   see it and decide.

`wiki-update` on its next run:
- Reads items with `pendiente_wiki: true`.
- Integrates data into wiki (create or update article).
- **Removes the item from the consolidado** when integrated (cleanup).
- If consolidado data was wrong (typo, miscategorized), fix the consolidado before removing.

Daily memos (`memory/YYYY-MM-DD.md`) are context only when an item is ambiguous; not the primary
wiki source.

## W2. Close — Commit + Pull Request (this PR is the report)

**PR body signature:** `_firma.md` → `sec-signature.sh revision-correo`.

When all work in `$WT/` is done, write the FINAL REPORT (Section 5, and Section 6 on Fridays) to a
temporary file and open it as the PR body:

```bash
cd "$WT"
if [ -z "$(git status --porcelain)" ]; then
  echo "No versioned changes — no PR opened."
  cd "$REPO" && git worktree remove "$WT" --force && git branch -D "$BRANCH" 2>/dev/null || true
else
  # scripts/ci/update_contract_freshness.py no existe (verificado 2026-08-29, sec-dream) — el
  # único script vivo es scripts/ci/contract_health.py y su --sync-contract no toca
  # freshness.last_success_at de extractors. Patch manual, mismo patrón que drive-crawler:
  NOW=$(TZ=America/Lima date +"%Y-%m-%dT%H:%M:%S-05:00")
  python3 - "$NOW" <<'PYEOF'
import sys, re
p = "extractors/mail/contract.yaml"
s = open(p).read()
s = re.sub(r'last_success_at: ".*"', f'last_success_at: "{sys.argv[1]}"', s, count=1)
open(p, "w").write(s)
PYEOF
  git add -A
  git commit -m "chore(correo): corrida automática $(date +%Y-%m-%d)"
  git push -u origin "$BRANCH"
  gh label create "hilo:correo" --description "Hilo de trabajo: correo" --color BFD4F2 2>/dev/null || true
  # Write report (Markdown) with the Write tool to a temp file, e.g. /tmp/pr-correo.md
  gh pr create --title "chore(correo): corrida automática $(date +%Y-%m-%d)" \
    --label "hilo:correo" --body-file /tmp/pr-correo.md
  cd "$REPO" && git worktree remove "$WT" --force
fi
```

Notes:
- Create the report draft (`/tmp/pr-correo.md`) with the Write tool, not `echo`/heredoc.
- If `gh pr create` fails (network/auth), do not revert: the branch is already pushed; report the
  error and leave the worktree for manual inspection.
- Return the **PR URL** at the end.