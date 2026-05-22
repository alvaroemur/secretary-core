# WhatsApp Monitor Routine

**What this routine does:** Fetches new WhatsApp messages, processes whitelisted chats through specialized sub-agents (project, radar, and persona), triages non-whitelisted chats for signal detection, produces structured summaries and entity extraction, surfaces whitelist candidates, and opens a PR with the monitoring report.

This routine operates on a core/instance split: the chat capture scripts live in the engine repo (`$CORE/whatsapp/src/`), while data, policy, and memory live in the instance repo (`$INSTANCE/whatsapp/`).

> Designed for Claude Code scheduled tasks, but the pattern works with any AI coding agent that can read files, run shell commands, and call APIs.

## Prerequisites

- **Git** with push access to the instance repository
- **WhatsApp Web bridge** — a tool that can:
  - Fetch new messages since a timestamp (e.g., Baileys-based scripts, whatsapp-web.js, or a custom bridge)
  - Dump chat messages as structured text (sender, timestamp, content type, text)
  - Identify group vs. 1-on-1 chats
  - Map JIDs (WhatsApp internal IDs) to display names
- **Sub-agent capability** for parallel processing
- **Glossary** (`$INSTANCE/whatsapp/memory/_glossary.md`) — maps JIDs, pushNames, and aliases to canonical names
- Environment variables: `$INSTANCE`, `$CORE`

## Schedule

Daily (e.g., `0 9 * * *`), or more frequently if real-time monitoring is desired (every 6h).

---

## Step 0 — Worktree setup

```bash
BRANCH="whatsapp/monitor-$(date +%Y-%m-%d)"
WORKTREE="$INSTANCE/.claude/worktrees/whatsapp-monitor-$$"

cd "$INSTANCE"
git fetch origin main
git worktree add "$WORKTREE" -b "$BRANCH" origin/main
cd "$WORKTREE"
```

## Step 1 — Fetch new messages

Run the capture script to dump new messages since the last run:

```bash
cd "$CORE/whatsapp/src"
npx tsx fetch.ts --since "$(cat $WORKTREE/whatsapp/estado.md | grep 'last_fetch' | cut -d' ' -f2)" \
  --output "$WORKTREE/whatsapp/inbox/"
```

This produces one file per chat in `inbox/chats/<jid-or-slug>.md`, each containing the new messages in chronological order.

## Step 2 — Load context

1. **Policy** (`$INSTANCE/whatsapp/policy.md`) — The whitelist. Three tiers:
   - **Project chats** — group chats tied to active projects; extract actions, deadlines, decisions
   - **Radar chats** — group chats to monitor for opportunities and news; no forced actions
   - **Persona chats** — 1-on-1 conversations with key contacts; extract commitments and personal/professional info
   Plus: blocked list, triage rules for non-whitelisted chats.

2. **State** (`$INSTANCE/whatsapp/estado.md`) — Last run metadata, processing stats, pending whitelist candidates, active issues. This file doubles as the PR body.

3. **Glossary** (`$INSTANCE/whatsapp/memory/_glossary.md`) — Maps JIDs and aliases to canonical names. Handles the common problem of WhatsApp contacts having different display names across devices.

4. **Memory files** — `personas.md`, `organizaciones.md`, `entidades.md`, `acciones.md`, `chats.md`.

5. **Wiki context** — Known personas and organizations for enriching entity extraction.

## Step 3 — Classify chats

For each chat with new messages:

```
IF chat JID or slug is in policy.md "Approved" list:
  → route to appropriate sub-agent (Step 4)
  
ELIF chat JID is in "Blocked" list:
  → skip entirely, do not report

ELSE:
  → route to triage sub-agent (Step 5)
```

## Step 4 — Process whitelisted chats (sub-agents)

Dispatch sub-agents based on chat tier:

### 4a. Project chat sub-agent

**Input:** Chat messages, glossary, wiki context for project participants.

**Task:**
- Extract action items with owners and deadlines
- Identify decisions made
- Note status changes on tracked deliverables
- Flag scheduling discussions (meetings proposed/canceled/moved)
- Produce structured summary

**Output:** `summaries/YYYY-MM-DD-<chat-slug>.md` with:
```markdown
---
chat: "<chat-slug>"
date: YYYY-MM-DD
messages_processed: N
participants_active: [list]
---

# <Chat Name> — YYYY-MM-DD

## Summary
<2-5 sentences on what happened>

## Actions
| ID | Owner | Action | Deadline | Status |
|---|---|---|---|---|

## Decisions
- <decision 1>

## Entities
<JSON block per meetings-processor format>
```

### 4b. Radar chat sub-agent

**Input:** Chat messages, glossary.

**Task:**
- Extract interesting news, opportunities, links, events
- Do NOT force action items — radar chats are monitoring, not task-tracking
- Note any mentions of the user or user's projects/organizations
- Summarize the general vibe and topics

**Output:** `summaries/YYYY-MM-DD-radar-digest.md` (one consolidated file for all radar chats, or per-chat if volume warrants it).

### 4c. Persona chat sub-agent

**Input:** Chat messages, glossary, wiki article for the person (if exists).

**Task:**
- Extract commitments made by either party
- Note personal/professional information shared (new job, travel, life events)
- Identify follow-up needs (questions asked but not answered, promises made)
- Respect privacy: personal venting or emotional content in trusted 1-on-1 chats is contextual signal, NOT action items. Record as mood/context note only.

**Output:** `summaries/YYYY-MM-DD-<person-slug>.md`.

### 4d. Anti-hallucination gates (same as meetings)

- `pendiente_wiki: false` by default for new entities
- Never guess surnames from context
- Glossary overrides message text for entity identification
- Unknown senders in groups (`?` or missing participant) — include in topic analysis, exclude from person-attribution

### 4e. Multiple runs per day

If the routine runs more than once daily, append a suffix to the summary filename:
- First run: `2026-05-22-chat-slug.md`
- Second run: `2026-05-22-chat-slug-pm.md`
- Third run: `2026-05-22-chat-slug-evening.md`

## Step 5 — Triage non-whitelisted chats

For chats NOT in the whitelist, run a lightweight triage sub-agent:

### Signal classification

| Signal Level | Criteria | Report Action |
|---|---|---|
| **High** | >5 real-text messages, OR mentions known wiki entity, OR new 1-on-1 contact, OR contains keywords (deadline, proposal, meeting, invoice, payment, convocatoria) | Add to "Whitelist Candidates" in estado.md |
| **Medium** | 1-3 messages with minimal content (scheduling, "ok", "thanks") | Add to "Minor Activity" (1-line) in estado.md |
| **Low** | Media-only, emoji-only, reactions-only | Stats only in estado.md |

### New contact detection

If a previously unseen JID sends a 1-on-1 message, flag as "New contact detected" in estado.md. Include pushName and any available info.

### Candidates output

```markdown
## Whitelist Candidates (review and decide)

- **<pushName>** (<jid>) — <why this looks relevant>
  - Suggested action: add as `persona` / add as `radar` / ignore
```

The user decides by editing policy.md and merging the PR.

## Step 6 — Radar consolidation

If multiple radar chats had activity, produce a consolidated radar digest:

```markdown
# Radar Digest — YYYY-MM-DD

## Opportunities spotted
- [link/event/call-for-proposals from radar chat X]

## Ecosystem news
- [notable developments mentioned across radar chats]

## Mentions of user's projects/orgs
- [any references to known wiki entities]
```

This gives the user a single place to scan for radar intelligence.

## Step 7 — Update estado.md

`estado.md` serves dual purpose: state file for the routine AND PR body for the user.

Update all sections:
- **Last run** metadata (timestamp, message count, chat count)
- **Processed chats** — per-tier summaries with links to memo files
- **Whitelist candidates** — new + carried-over from previous runs
- **Minor activity** — low-signal chats
- **New contacts detected**
- **Reactivated chats** — whitelisted chats that were dormant and came back
- **Global statistics**
- **Next run** — when the routine will run again

## Step 8 — Consolidate memory files

Append new entities from all sub-agents to the shared memory files:

- `memory/personas.md` — new people with name, JID, context, source
- `memory/organizaciones.md` — new organizations mentioned
- `memory/entidades.md` — other entities
- `memory/acciones.md` — action items with stable IDs (check for collisions with meetings routine)
- `memory/chats.md` — metadata about processed chats (slug, JID, tier, last activity date)

## Step 9 — Commit and open PR

```bash
cd "$WORKTREE"
git add whatsapp/
git commit -m "docs(whatsapp): monitor $(date +%Y-%m-%d)"
git push origin "$BRANCH"

# Use estado.md as the PR body
gh pr create \
  --title "docs(whatsapp): monitor $(date +%Y-%m-%d)" \
  --body "$(cat whatsapp/estado.md)" \
  --base main \
  --label "routine:whatsapp"
```

## Step 10 — Cleanup

```bash
cd "$INSTANCE"
git worktree remove "$WORKTREE" --force
```

---

## Core/Instance split in detail

This routine relies on scripts and data living in separate repos:

| Component | Location | Purpose |
|---|---|---|
| `fetch.ts` | `$CORE/whatsapp/src/` | Captures new messages via WhatsApp Web bridge |
| `dump.ts` | `$CORE/whatsapp/src/` | Full history dump (one-time or reset) |
| `login.ts` | `$CORE/whatsapp/src/` | QR code authentication |
| `fix-group-senders.ts` | `$CORE/whatsapp/src/` | Repairs missing sender info in group messages |
| `download-media.ts` | `$CORE/whatsapp/src/` | Downloads media files referenced in messages |
| `policy.md` | `$INSTANCE/whatsapp/` | Whitelist, triage rules, blocked list |
| `estado.md` | `$INSTANCE/whatsapp/` | State file / PR body |
| `inbox/chats/` | `$INSTANCE/whatsapp/` | Raw message dumps per chat |
| `summaries/` | `$INSTANCE/whatsapp/` | Processed summaries |
| `memory/` | `$INSTANCE/whatsapp/` | Consolidated entity files |

Scripts resolve instance paths via `$SECRETARY_INSTANCE` environment variable, never hard-coded.

---

## Customization

1. **WhatsApp bridge**: The template assumes Baileys-based TypeScript scripts. Replace with your preferred WhatsApp Web library. The key requirement is: fetch messages since timestamp, output as structured text with sender, timestamp, and content.
2. **Whitelist tiers**: Three tiers (project, radar, persona) work well for most people. Add or remove tiers as needed. Some users add a "family" tier with different processing rules.
3. **Triage keywords**: The signal-high keywords (deadline, proposal, meeting, invoice) are a starting point. Add domain-specific keywords relevant to your work.
4. **Multiple phone numbers**: If a contact has multiple WhatsApp numbers (common with people who have personal and business phones), map both JIDs to the same canonical name in the glossary.
5. **Group name mapping**: WhatsApp groups have JIDs like `120363047983534809@g.us`. Map these to readable slugs in the glossary or in a separate mapping file.
6. **Privacy rules**: For 1-on-1 chats with close friends/family, you may want to process for context but suppress detailed summaries. Add a "confidential" tier that extracts only action items, no conversation summaries.
7. **Media handling**: This template focuses on text. If you want to process images (OCR), voice notes (transcription), or documents (extraction), add media processing steps after fetch.
8. **Run frequency**: Daily is a good default. For high-activity project chats, consider running every 6 hours with appropriate filename suffixes.
9. **PR labels**: Create `routine:whatsapp` label (`gh label create routine:whatsapp --color BFD4F2`).
10. **Glossary maintenance**: The user maintains the glossary manually. When the routine encounters a pushName it can't map confidently, it should note it in estado.md rather than guessing.
