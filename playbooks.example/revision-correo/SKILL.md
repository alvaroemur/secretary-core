---
name: revision-correo
description: >-
  Daily mail summary, reply drafts, inbox cleanup, and Inbox Zero goal.
  Delivers run output as a Pull Request report.
---

Read instance `CLAUDE.md` at `SECRETARY_INSTANCE` before starting. Instance appendix:
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

### 0.3 — Persist draft copy (Gmail thread replies only)

**Inbox thread replies only** — not project deliverables. Proposals/decks/commercial docs belong
in the target org's Cowork project folder per instance `CLAUDE.md` § domain dispatch and
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

**Multi-account.** This routine covers two accounts when configured: `PERSONAL_ACCOUNT` (always
active) and `WORK_ACCOUNT` (corporate, when registered in gog). Check whether the work account is
registered before using it:

```bash
WORK_ACTIVE=false
if [ -n "$WORK_ACCOUNT" ] && \
   gog gmail search 'newer_than:1d' --account="$WORK_ACCOUNT" --max 1 --plain --no-input 2>/dev/null; then
  WORK_ACTIVE=true
fi
```

If `WORK_ACTIVE=true`: run the mail sweep for both accounts (add `--account="$WORK_ACCOUNT"` on
work-account calls) and consolidate into one PR with separate sections per account. If
`WORK_ACTIVE=false`: operate on the personal account only and add one line to the report:
`⚠️ $WORK_ACCOUNT not registered in gog — see instance CLAUDE.md § Google accounts`.

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
