# Meetings Processor Routine

**What this routine does:** Reads meeting transcriptions from a cloud folder (e.g., Google Drive via a transcription tool like Tactiq, Otter, or Fireflies), groups related fragments, dispatches parallel sub-agents to produce structured summaries, extracts entities (people, organizations, actions, topics), applies phonetic corrections, consolidates into memory files, and archives processed files. Output is a PR with the processing report.

> Designed for Claude Code scheduled tasks, but the pattern works with any AI coding agent that can read files, run shell commands, and call APIs.

## Prerequisites

- **Git** with push access to the instance repository
- **Google Drive access** — either:
  - Filesystem mount (e.g., Google Drive for Desktop) for zero-token reads, OR
  - Drive API / MCP tool for listing and reading files
- **Sub-agent capability** — the agent must be able to spawn parallel workers (Claude Code `Task` tool, or sequential processing as fallback)
- **Glossary** maintained by the user (`$INSTANCE/meetings/memory/_glossary.md`) — ground truth for name corrections
- Environment variables: `$INSTANCE`, `$CORE`
- **Bookkeeping file**: `$INSTANCE/meetings/memory/_processed.jsonl` — tracks which Drive files have been processed

## Schedule

Daily, after transcription files are expected to land (e.g., `0 8 * * *`).

---

## Step 0 — Worktree setup

```bash
BRANCH="meetings/process-$(date +%Y-%m-%d)"
WORKTREE="$INSTANCE/.claude/worktrees/meetings-process-$$"

cd "$INSTANCE"
git fetch origin main
git worktree add "$WORKTREE" -b "$BRANCH" origin/main
cd "$WORKTREE"
```

## Step 1 — Load context

1. **Glossary** (`$INSTANCE/meetings/memory/_glossary.md`) — Ground truth for phonetic corrections. Maps common transcription errors to correct names. The sub-agent MUST respect this as authoritative; if the glossary contradicts the transcript, the glossary wins (the transcript was mis-transcribed).
2. **Processed log** (`$INSTANCE/meetings/memory/_processed.jsonl`) — One JSON line per previously processed file: `{"drive_id": "...", "title": "...", "date": "...", "group_id": "...", "processed_at": "..."}`.
3. **Wiki articles** — Scan `$INSTANCE/wiki/articulos/` for known personas, orgs, and topics to enrich entity extraction.
4. **Memory files** — Read existing `$INSTANCE/meetings/memory/personas.md`, `organizaciones.md`, `acciones.md`, `reuniones.md` to avoid duplicates.

## Step 2 — Discover new transcriptions

List files in the transcription folder:

```
Drive folder: <TRANSCRIPTION_FOLDER_ID>
Filter: files modified since last run OR files not in _processed.jsonl
Sort: by creation time ascending
```

For each file, extract:
- `drive_id` — unique file identifier
- `title` — usually contains meeting name + date
- `created_at` — when the transcription was created
- `modified_at` — when it was last modified

Skip any file whose `drive_id` already appears in `_processed.jsonl`.

## Step 3 — Group fragments

Transcription tools often split a single meeting into multiple files (fragments). Group them intelligently:

### 3a. Primary grouping: date + title similarity

Files from the same date with similar titles (edit distance < 30% of title length, or same title with different suffixes like "Part 1", "Part 2", "(2)") belong to the same meeting.

### 3b. Extended groups: late fragments

Sometimes a fragment arrives late (e.g., the transcription tool retries). If a new file has the same title as a previously processed group AND was created within 2 hours of the group's latest fragment, add it to the group as a "late fragment." Re-process the entire group.

### 3c. Same-day siblings: different meetings

Two files from the same day with clearly different titles are DIFFERENT meetings. Do not group them. Example: "Team Standup 2026-05-22" and "Client Call — Acme 2026-05-22" are siblings, not fragments.

### 3d. Group metadata

For each group, compute:
- `group_id` — deterministic hash of normalized title + date
- `fragments` — ordered list of drive_ids
- `total_duration_estimate` — sum of fragment durations (if available from metadata)
- `participants_hint` — any participant names visible in file metadata

## Step 4 — Dispatch sub-agents (per meeting)

For each meeting group, spawn a sub-agent with the following instructions:

### Sub-agent input
```
- Fragments: [list of transcript texts, ordered by creation time]
- Glossary: [full glossary content]
- Wiki context: [relevant persona/org articles based on participants_hint]
- Output path: $INSTANCE/meetings/summaries/YYYY-MM-DD-<slug>.md
```

### Sub-agent task

#### 4a. Merge fragments
Concatenate transcripts in chronological order. If fragments overlap (same dialogue appears in two fragments), deduplicate.

#### 4b. Produce structured summary

```markdown
---
title: "<Meeting title>"
date: YYYY-MM-DD
duration_min: <estimated minutes>
participants:
  - "[[personas/<slug>|Display Name]]"
  - "Unknown Participant (description if available)"
type: "<1:1 | team | external | workshop | ...>"
source_drive_ids:
  - "<drive_id_1>"
  - "<drive_id_2>"
processed_at: "YYYY-MM-DDTHH:MM:SSZ"
---

# <Meeting title> — YYYY-MM-DD

## Context
<1-2 sentences on why this meeting happened, who called it, what the agenda was>

## Key Discussion Points
<Bulleted summary of main topics, organized thematically>

## Decisions Made
<Numbered list of explicit decisions>

## Action Items
| ID | Owner | Action | Deadline | Status |
|---|---|---|---|---|
| acc-YYYYMMDD-001 | Person | Description | YYYY-MM-DD | pending |

## Entities Extracted
<JSON block — see 4c below>

## Notable Quotes
<2-3 significant quotes, attributed, max 15 words each>
```

#### 4c. Entity extraction (JSON)

Produce a structured JSON block for downstream consumption:

```json
{
  "personas": [
    {
      "name": "Full Name",
      "slug": "full-name",
      "role_context": "VP at Acme Corp",
      "source": "meetings/summaries/YYYY-MM-DD-slug.md",
      "pendiente_wiki": false,
      "notes": "First mention — needs user confirmation"
    }
  ],
  "organizaciones": [
    {
      "name": "Acme Corp",
      "slug": "acme-corp",
      "context": "Client, discussed contract renewal",
      "source": "meetings/summaries/YYYY-MM-DD-slug.md",
      "pendiente_wiki": false
    }
  ],
  "acciones": [
    {
      "id": "acc-YYYYMMDD-001",
      "responsable": "Full Name",
      "accion": "Send revised proposal",
      "deadline": "2026-05-30",
      "estado": "pending",
      "contexto": "[[temas/acme-project]]",
      "source": "meetings/summaries/YYYY-MM-DD-slug.md",
      "pendiente_wiki": true
    }
  ]
}
```

#### 4d. Anti-hallucination gates

The sub-agent MUST follow these rules to prevent hallucinated data:

1. **`pendiente_wiki: false` by default for NEW entities.** Only set to `true` for entities that are unambiguously identified (full name, clear role, appears multiple times in the transcript). The user promotes items to `true` during PR review.

2. **Never guess surnames.** If the transcript says only "Maria" and the glossary doesn't map it, register as `"Maria (surname pending)"`. Do NOT infer a surname from context, org affiliation, or email domains.

3. **Glossary overrides transcript.** If the glossary says `"Penut" -> "UNDP"`, apply the correction even if the transcript clearly says "Penut" fifty times. The transcription tool made the error, not the glossary.

4. **Do not create organizations from fragments.** If the transcript mentions "ex-Price" or "post-Alpha", these are descriptors, not org names. Only create orgs that are clearly named as such ("we met with representatives from Acme Corp").

5. **Unknown speakers.** When a transcript has messages from unidentified speakers, include those messages in the topic analysis but exclude them from person-attribution. Mark as `"speaker: unidentified"`.

6. **Phonetic correction.** Before finalizing any entity name, run it through the glossary's correction list. Common patterns:
   - Brand names transcribed as common words
   - Foreign names phonetically adapted to the transcript tool's language model
   - Acronyms expanded incorrectly

## Step 5 — Consolidation

After all sub-agents complete:

### 5a. Stable action IDs

Action IDs follow the pattern `acc-YYYYMMDD-NNN` where NNN is sequential within a day. Check existing IDs in `acciones.md` to avoid collisions. If the meeting date already has IDs 001-005, start the new batch at 006.

### 5b. Append to memory files

For each entity type, read the corresponding memory file, check for duplicates, and append new items:

- `memory/personas.md` — new people
- `memory/organizaciones.md` — new organizations
- `memory/entidades.md` — other entities
- `memory/acciones.md` — action items (with stable IDs)
- `memory/reuniones.md` — one entry per meeting processed (metadata + link to summary)

### 5c. Update action states

If a meeting references a previously known action (someone says "we finished the proposal"), look for the matching `acc-YYYYMMDD-NNN` and add an `[update]` entry:

```markdown
## acc-YYYYMMDD-NNN [update]
- estado_nuevo: completed
- evidencia: "mentioned as done during 2026-05-22 team call"
- origen: meetings/summaries/YYYY-MM-DD-slug.md
- detectado: YYYY-MM-DD
- pendiente_wiki: true
```

## Step 6 — Archive processed files in Drive

Move (or copy) processed transcription files to an archive folder in Drive:

```
Source: <TRANSCRIPTION_FOLDER_ID>/<filename>
Destination: <ARCHIVE_FOLDER_ID>/YYYY-MM/<filename>
```

If the Drive tool supports moving, move. If not, note in the report that files should be manually archived.

## Step 7 — Update bookkeeping

Append one line per processed file to `_processed.jsonl`:

```json
{"drive_id": "abc123", "title": "Team Standup", "date": "2026-05-22", "group_id": "hash456", "fragments": 2, "summary_path": "meetings/summaries/2026-05-22-team-standup.md", "processed_at": "2026-05-22T08:30:00Z"}
```

## Step 8 — Commit and open PR

```bash
cd "$WORKTREE"
git add meetings/summaries/ meetings/memory/
git commit -m "docs(meetings): process $(date +%Y-%m-%d)"
git push origin "$BRANCH"

gh pr create \
  --title "docs(meetings): process $(date +%Y-%m-%d)" \
  --body "$(generate_report)" \
  --base main \
  --label "routine:meetings"
```

### Report structure

```markdown
# Meetings Processed — YYYY-MM-DD

## Meetings
| Meeting | Date | Duration | Participants | Fragments |
|---|---|---|---|---|
| Title | YYYY-MM-DD | ~Nmin | N people | N files |

## Entities Extracted
- Personas: N new (M promoted to wiki, K pending user review)
- Organizations: N new
- Actions: N new, M updates to existing

## Late fragments detected
- [any fragments that extended a previous group]

## Glossary corrections applied
- "Transcript Error" -> "Correct Name" (N occurrences)

## Files archived in Drive
- N files moved to YYYY-MM/ archive

## Issues / Doubts
- [any unresolved questions for the user]
```

## Step 9 — Cleanup

```bash
cd "$INSTANCE"
git worktree remove "$WORKTREE" --force
```

---

## Customization

1. **Transcription source**: Replace `<TRANSCRIPTION_FOLDER_ID>` with your actual Drive folder. If you use Otter.ai, Fireflies, or another tool, adapt the file discovery logic (Step 2) for their output format.
2. **Glossary**: Start with an empty `_glossary.md` and populate it as you review PRs. Every time the transcription tool gets a name wrong, add the correction. This compounds — after a few weeks, most common errors are auto-corrected.
3. **Fragment grouping**: The thresholds (edit distance, 2-hour window) are tuned for Tactiq. Adjust if your tool behaves differently.
4. **Anti-hallucination strictness**: The default is conservative (`pendiente_wiki: false` for new entities). If you trust the agent more, you can relax this — but start strict and loosen over time.
5. **Sub-agent parallelism**: If your agent platform doesn't support parallel sub-agents, process meetings sequentially. The output is the same; it just takes longer.
6. **Archive folder**: Set `<ARCHIVE_FOLDER_ID>` to a Drive folder where processed transcripts go. Create a `YYYY-MM/` subfolder structure for organization.
7. **Action ID format**: `acc-YYYYMMDD-NNN` is a convention. Change if you prefer a different scheme, but keep IDs stable and collision-free.
8. **Summary language**: Summaries default to the language of the transcript. If your meetings are multilingual, add a language detection step and standardize output language.
9. **PR labels**: Create `routine:meetings` label (`gh label create routine:meetings --color D93F0B`).
10. **Meeting types**: The `type` field in summaries (1:1, team, external, workshop) is a suggestion. Define your own taxonomy based on your meeting patterns.
