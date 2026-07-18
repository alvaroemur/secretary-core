---
name: sec-meeting
description: >-
  Fresh check for recently ended meetings — probe Tactiq on Drive, read tentative
  summaries on unmerged reuniones/auto-* PRs, delegate recall to sec-recall, and
  point to reuniones-update for analysis. Triggers: "/sec-meeting", "¿ya procesó la reunión?",
  "transcripción de", "qué pasó en la reunión con", "reunión de hace".
---

# sec-meeting — meetings fresh-first

**Mission:** close the gap between "call ended" and "summary in main" — detect Tactiq
transcription, read tentative evidence on open PRs, integrate with `sec-recall`. **Does not write**
to `extractors/meetings/` (only the `reuniones-update` routine does).

Doctrine: `rules/skills-contract.md`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
WORK_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.Company // .accounts.work // empty')
if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$SECRETARY_INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
```

| Constant | Value | Notes |
|----------|-------|-------|
| `TACTIQ_ROOT` | `1TE6Z1uhZo7YrwOnWvp83se3CCXHiCKt9` | Tactiq Drive folder (instance-specific — move to `.secretary.yml` phase 3) |
| `ACC` | `$PERSONAL_ACCOUNT` | Tactiq uses personal Drive |
| `REPO` | `$SECRETARY_INSTANCE` | Local instance checkout |
| `ROUTINE_REPO` | `$BRIEF_REPO` | GitHub repo for reuniones PRs |

| Heuristic | Value |
|-----------|-------|
| Tactiq unstable | `modifiedTime` < 10 min → wait |
| Empty shell | `size` < 3000 B → not a meeting |
| Routine cadence | `reuniones-update` :00 (9–21) + 22:00 in `timezone` |

## Inputs

| Field | Values |
|-------|---------|
| `intent` | `fresh` (default) \| `probe` \| `recall` \| `trigger` |
| `meeting_ref` | Title, participant, or `last_2h` |
| `date` | `YYYY-MM-DD` (default: today in `timezone`) |

## Loop fresh-first

### Step 0 — Fresh (required)

```bash
secretary fresh meeting                   # table: main, auto-pr, Tactiq, last summary
secretary fresh meeting --format json
secretary fresh reuniones                 # alias of meeting

git -C "$SECRETARY_INSTANCE" show origin/main:extractors/meetings/memory/_procesados.jsonl 2>/dev/null | tail -8
```

Read tentative summary on open branch (no checkout):

```bash
BRANCH=reuniones/auto-YYYYMMDD-HHMM   # from gh pr list --repo "$ROUTINE_REPO"
git -C "$SECRETARY_INSTANCE" show "origin/${BRANCH}:extractors/meetings/summaries/YYYY-MM-DD-slug.md" | head -80
```

### Step 0b — Probe Tactiq (recent meeting)

```bash
# Docs at Tactiq root (exclude processed/discarded folders in jq)
gog drive ls --parent="$TACTIQ_ROOT" --json --account="$ACC" --no-input \
  | jq '[.files[]? | select(.mimeType=="application/vnd.google-apps.document") | {id,name,modifiedTime,size}]'

gog drive get <fileId> --json --account="$ACC" --no-input
```

Calendar — meeting that just ended:

```bash
gog calendar events primary --from today --to tomorrow --plain --account="$ACC"
# Work / shared calendars: list and repeat if needed
[ -n "$WORK_ACCOUNT" ] && gog calendar list --plain --account="$ACC"
```

### Step 1 — Recall

`sec-recall` on participants, topic, or `meeting_ref`. Mark PR facts as `⏳ tentative (PR #N)`.

### Step 2 — Action (`intent=trigger`)

Session **does not** merge or write summaries. Options:

1. Report status: "Tactiq stable, waiting `:00`" or "already in PR #N".
2. If owner asks to process now → invoke `reuniones-update` routine.
3. After run → PR URL; offer `babysit` / merge when ready.

## Decision tree (summary)

```
Calendar: event ended <2h?
  └─ no → standard sec-recall
  └─ yes → doc in TACTIQ_ROOT, >3KB, stable >10min?
        └─ no → "waiting for Tactiq"
        └─ yes → in _procesados.jsonl?
              └─ yes → recall + main summary
              └─ no → in reuniones/auto-* PR?
                    └─ yes → git show summary (tentative)
                    └─ no → offer trigger reuniones-update
```

## Post-merge commands

```bash
git -C "$SECRETARY_INSTANCE" show origin/main:extractors/meetings/memory/reuniones.md | tail -40
ls "$(secretary config path extractors.meetings.summaries 2>/dev/null || echo "$SECRETARY_INSTANCE/extractors/meetings/summaries")" | tail -5
```

## Report

Header: `🎙️ **Meeting — <meeting_ref|**fresh**>` · status `<waiting-tactiq|tentative-pr|in-main>`.

Include: calendar event (if any), Drive candidates (id, name, modifiedTime), PR # if applicable, next `:00` slot.

## Integration

| Skill / script | Role |
|----------------|------|
| `sec-recall` | Step 1; delegates here for meeting freshness questions |
| `reuniones-update` | Sole writer of `extractors/meetings/` |
| `secretary fresh meeting` | Atomic step 0 (main, auto-pr, Tactiq) |
| `pulse` | Flag `unprocessed meeting` if calendar >3h without PR |

Doctrine: `rules/extractor-ops.md` · Spec: `_diseño/specs/010-extractor-skills/spec.md` § sec-meeting
