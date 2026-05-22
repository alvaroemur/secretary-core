# Mail Review Routine

**What this routine does:** Reviews all email from the last 24 hours, classifies each thread by importance, creates draft replies for actionable items, cleans the inbox according to policy rules, and opens a PR with the daily report. On Fridays, produces an extended weekly report covering everything archived/flagged since the previous Friday.

> Designed for Claude Code scheduled tasks, but the pattern works with any AI coding agent that can read files, run shell commands, and call APIs.

## Prerequisites

- **Git** with push access to the instance repository
- **Gmail CLI tool** with the following capabilities:
  - `search` — query threads by date, label, sender, category
  - `get` — read full thread content (headers + body)
  - `label` / `unlabel` — add/remove Gmail labels
  - `archive` — remove from INBOX (equivalent to `--remove INBOX`)
  - `drafts create --reply-to-message-id <id>` — create draft replies threaded correctly (never orphaned drafts)
  - `send` — send a composed email (used sparingly, only when policy allows)
- **Read access** to the wiki articles directory (for context about known people, organizations, topics)
- Environment variables: `$INSTANCE` pointing to the instance repo root

## Schedule

Daily, typically early morning (e.g., `0 7 * * *` in user's local timezone).

---

## Step 0 — Worktree setup

Every run operates in an isolated git worktree to avoid conflicts with the user's working tree or other routines.

```bash
BRANCH="mail/review-$(date +%Y-%m-%d)"
WORKTREE="$INSTANCE/.claude/worktrees/mail-review-$$"

cd "$INSTANCE"
git fetch origin main
git worktree add "$WORKTREE" -b "$BRANCH" origin/main
cd "$WORKTREE"
```

At the end of the run, clean up:

```bash
cd "$INSTANCE"
git worktree remove "$WORKTREE" --force
```

## Step 1 — Load context

Read all of these before processing any email:

1. **Policy** (`$INSTANCE/mail/policy.md`) — Classification rules: which senders to archive, which to flag for deletion, which to always keep in inbox, priority domains, payment alert senders.
2. **Settings** (`$INSTANCE/mail/settings.md`) — User corrections and behavioral preferences accumulated over time (draft tone, classification overrides, senders the user wants special handling for).
3. **State** (`$INSTANCE/mail/estado.md`) — Active projects/commitments, recurring payment issues, upcoming events, job search criteria, deadlines. This is the "working memory" of the routine.
4. **Pending config** (`$INSTANCE/mail/pending.md`) — Optional. Any configuration changes the user has queued (e.g., "start reading my work email too").
5. **Wiki context** — Scan `$INSTANCE/wiki/articulos/personas/`, `$INSTANCE/wiki/articulos/organizaciones/`, and `$INSTANCE/wiki/articulos/temas/` to understand who the user knows and what projects are active. This enriches classification: an email from a known wiki person is never spam.
6. **Memory files** — Check `$INSTANCE/mail/memory/personas.md`, `organizaciones.md`, `entidades.md`, `suscripciones.md` for recently detected entities not yet in the wiki.

## Step 2 — Fetch and classify emails

Query all threads from the last 24 hours (or since the last successful run timestamp from `estado.md`).

For each thread:

### 2a. Read the full thread
Retrieve headers (From, To, Cc, Subject, Date, Message-ID) and body text. For threads with multiple messages, read all messages to understand the conversation state.

### 2b. Classify into categories

| Category | Criteria | Action |
|---|---|---|
| **Important / Action Required** | User is in To/Cc on active project thread; contains deadline; requires a decision or response | Keep in inbox. Create draft reply if appropriate. |
| **Events with Deadlines** | Contains a future date + implicit action (RSVP, registration, attendance, form to fill) | Keep in inbox. Extract ALL implicit actions with explicit deadlines. Mark as "Action Required." If a response is warranted, create a draft (not just describe it). |
| **Payment / Billing Alerts** | Failed payment, suspension notice, overdue balance | Keep in inbox. Flag as "Action Required." If recurring, keep only the most recent, archive older ones. |
| **Security Alerts** | Unusual login, unrecognized transaction, account warnings | Keep in inbox. Flag prominently. |
| **Job Alerts / Opportunities** | Job postings, convocatorias, fellowship calls | Evaluate relevance against user's profile (from `estado.md`). Keep relevant ones in inbox; archive clearly irrelevant ones. Never auto-delete. |
| **Newsletters / Updates** | Tech newsletters, product updates, changelog emails | Archive. Include 1-line summary in report. |
| **Promotions / Marketing** | Commercial offers, discounts, re-engagement | Archive per policy. Verify nothing relevant is hidden (event, payment, opportunity) before archiving. |
| **Spam / Irrelevant** | Matches policy sender list with no exceptions triggered | Archive. Never delete — "delete" means archive (`--remove INBOX`), NEVER move to trash. |

### 2c. Safeguard check
Before archiving ANY thread, verify it does not contain:
- A relevant event or opportunity buried in promotional text
- A payment issue or account alert
- A personal message from a known contact

When in doubt, leave in inbox and mention in the report.

## Step 3 — Create draft replies

For threads classified as "Important / Action Required":

1. Check `settings.md` for tone preferences (sign-off style, formality level, language).
2. Draft a concise reply addressing the thread's needs.
3. Create the draft **inside the thread** using the reply-to-message-id of the latest message. Never create orphaned drafts.
4. Note in the report that a draft was created, with a 1-line summary of the proposed reply.

**Do NOT draft replies for:**
- Automated notifications (Drive shares, calendar updates) unless they contain a personal message
- Payment failure notices (user handles these manually)
- Calendar invitations (never accept/reject/respond to calendar events automatically — only report them)

## Step 4 — Track sent emails without replies

Query the user's sent mail from the last 7 days. For each sent message:
- Check if there has been a reply in the thread since the user sent their message.
- If no reply after 3+ days, add to the "Pending Follow-ups" section of the report.
- If no reply after 7+ days, flag as "Stale — consider nudge."

## Step 5 — Execute inbox actions

Apply classification decisions:

```
For each thread marked for archiving:
  → gmail archive <thread-id>  (removes INBOX label only)

For each thread that needs labeling:
  → gmail label <thread-id> --add <label>

For threads with drafts:
  → gmail drafts create --reply-to-message-id <message-id> --body <draft-text>
```

**CRITICAL SAFETY RULE:** Never move emails to TRASH. "Archive" means remove from INBOX. The routine has zero delete permissions.

## Step 6 — Friday extended report (weekly)

If today is Friday (or the configured weekly report day):

1. Query all threads archived/processed since the previous Friday.
2. Produce an extended section covering:
   - Summary of everything that arrived this week, grouped by category
   - Analysis of archived items that might have been relevant
   - Subscription audit: for newsletters/promos received 3+ times this week, research whether an unsubscribe link exists and include instructions
   - Inbox health metrics: threads in/out, response rate, oldest unresolved thread

## Step 7 — Update state and memory files

### 7a. Update `estado.md`
- Refresh "Active projects" with any new threads or status changes
- Update "Recurring payment issues" if new failures detected or old ones resolved
- Update "Upcoming events" with newly detected events
- Update "Inbox state" with current count and composition
- Set `last_run` timestamp

### 7b. Update memory files (append-only)
For each new entity discovered in email:

- **`memory/personas.md`** — New people with name, email, context, source message-id, `pendiente_wiki: true`
- **`memory/organizaciones.md`** — New organizations detected
- **`memory/entidades.md`** — Other entities (products, services, platforms)
- **`memory/suscripciones.md`** — New mailing lists/newsletters detected

Before appending, check if the entity already exists in the wiki or in the memory file. Only add genuinely new information.

### 7c. Update policy (if needed)
If a new sender was encountered that clearly fits an existing policy category (e.g., obvious promotional sender), propose adding it to `policy.md` in a clearly marked section. The user reviews and approves via PR.

### 7d. Write daily memo
Create `memory/YYYY-MM-DD.md` with the full daily report. This serves as the historical record for this run.

## Step 8 — Commit and open PR

```bash
cd "$WORKTREE"
git add mail/estado.md mail/memory/ mail/policy.md
git commit -m "docs(mail): daily review $(date +%Y-%m-%d)"
git push origin "$BRANCH"

# Open PR with the report as body
gh pr create \
  --title "docs(mail): daily review $(date +%Y-%m-%d)" \
  --body "$(cat mail/memory/$(date +%Y-%m-%d).md)" \
  --base main \
  --label "routine:mail"
```

The PR body IS the report. The user reads the PR to see what happened with their email today.

## Step 9 — Cleanup

```bash
cd "$INSTANCE"
git worktree remove "$WORKTREE" --force
```

---

## Report structure

The daily memo / PR body should follow this structure:

```markdown
# Mail Review — YYYY-MM-DD

## Important / Action Required
- [thread subject] — from: sender — summary of what needs attention
  - Draft created: [yes/no] — [1-line draft summary]

## Events with Deadlines
- [event name] — date: YYYY-MM-DD — actions: [register/RSVP/attend/share]

## Payment Alerts
- [service] — status: [failed/overdue/resolved] — amount — notes

## Job Opportunities
- [position @ company] — relevance: [high/medium/low] — [1-line why]

## Newsletters & Updates (archived)
- [newsletter name] — [1-line summary of interesting content]

## Promotions Archived
- [count] promotional emails archived from [list of senders]

## Follow-up Tracker
- [thread subject] — sent: YYYY-MM-DD — days waiting: N — status

## Inbox Status
- Threads in inbox: N (was M yesterday)
- Archived today: N
- Drafts created: N

## Policy Updates (if any)
- Added [sender] to [archive/delete] list — reason

## Weekly Report (Fridays only)
- [extended weekly sections as described above]
```

---

## Customization

To adapt this routine for your setup:

1. **Gmail CLI tool**: Replace the generic references with your actual tool. You need: search, read, label, archive, and draft-create-with-reply-to. Popular options include `gog` (Google CLI), custom MCP servers, or direct Gmail API scripts.
2. **`policy.md`**: Create your own classification rules. Start simple (5-10 senders to auto-archive) and let the routine propose additions over time.
3. **`settings.md`**: Start empty. Add corrections as you review PRs ("don't draft replies for X", "use informal tone with Y").
4. **`estado.md`**: Seed with your active projects, known payment issues, upcoming events.
5. **Job search criteria**: If you're not job-hunting, remove the job alerts category or simplify it.
6. **Weekly report day**: Change from Friday to whatever suits your workflow.
7. **Memory file format**: The `pendiente_wiki: true/false` flag assumes a wiki-sync routine will consume these. If you don't use that pattern, simplify to plain append-only notes.
8. **PR labels**: Create `routine:mail` label in your repo (`gh label create routine:mail --color 0E8A16`).
9. **Multiple email accounts**: To process additional accounts, add them to `pending.md` and extend Step 2 to query each account sequentially.
10. **Calendar events**: This routine REPORTS calendar-related emails but NEVER acts on them (no accepting/rejecting invitations). If you want calendar automation, build a separate routine.
