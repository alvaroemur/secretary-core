---
name: sec-recall
description: Answer "what do I know about X?" by searching secretary's memory — wiki articles, module memory files, and live state. Use when a session needs to retrieve context about a person, org, project, or topic before acting.
---

# sec-recall

**Mission:** find and synthesize what secretary knows about a given subject so the session can act on informed context rather than assumptions.

## Guardrails
- **Read only** — never write or modify memory during a recall pass.
- Distinguish what's recorded (cite source and date) from what's inferred (flag it).
- If sources conflict, surface the conflict; don't silently pick one.

## Fresh-first (extractors)

When the question touches a **live external medium** — mail, a meeting that just ended, Drive files,
WhatsApp — **do not start here**. Run the medium skill's **step 0** first, then return to this
skill for consolidated memory.

| Medium | Delegate to | Typical trigger |
|--------|-------------|-----------------|
| Gmail / drafts | `sec-mail` | "my email", "reply to thread", unread inbox |
| Meetings / Tactiq | `sec-meeting` | "did we process the call?", transcript, "an hour ago" |
| Drive index / sync | `sec-drive` / `drive-sync` for mirrored Docs | "what's in Drive", edit Doc |
| WhatsApp | `sec-whatsapp` | chat with X |
| Cowork layout | `sec-cowork-audit` (alias `sec-workspace`); fit → `sec-cowork-fit` | portfolio drift vs one-folder skeleton |

Quick freshness without opening the full skill:

```bash
secretary fresh mail          # or meeting | drive | whatsapp | all
secretary fresh all --format json
```

Doctrine: `rules/extractor-ops.md` (resolve via `secretary config path rules`).

## Loop
1. Identify the subject: person, org, project, topic, or an open-ended question about current state.
2. **If the medium is an extractor** (table above) → invoke the matching `sec-<medium>` step 0, then continue.
3. Resolve lookup sources via `.secretary.yml` (wiki articles, module `memory/` dirs, wip store).
4. Search in order of likely precision: wiki article → module memory → wip state → raw captures.
5. **Scan unmerged captures (anti-amnesia).** Evidence captured by a routine but not yet merged lives on an open `auto-*` PR branch, invisible to the checkout. Always check it — a meeting summarized this morning by `reuniones-update` won't be on `main` until it merges. See *Unmerged scan* below.
6. Synthesize a coherent answer, citing the source file and date for each material fact. Evidence from an unmerged PR is **tentative** — mark it (see Report).
7. Flag gaps: what's missing, what's stale (no update in a long time), what might need a `sec-write` pass.

### Unmerged scan

```bash
CFG=$(secretary config show)
INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
PAT='^(mail|correo|meetings|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$'
git -C "$INSTANCE" fetch origin --quiet

gh pr list --repo "$BRIEF_REPO" --state open \
  --json number,headRefName,title \
  --jq ".[] | select(.headRefName | test(\"$PAT\"))"

# Read a file from a PR branch without checkout:
git -C "$INSTANCE" show "origin/<branch>:<path>"
gh pr diff <N> --repo "$BRIEF_REPO" | grep -i "<subject>"
```

Only surface unmerged evidence that actually matches the subject. Don't dump whole PRs.

## Report
Render **inline** (never spawn a new surface unless interactivity is the architectural point, e.g. diagram viewers). Header: `🧠 **Recall — <subject>** · <type>`. Use the densest fitting form — a table when there are ≥3 comparable fields (with field markers like 👤 relation, 💼 work, 📅 last contact), a labeled list otherwise. Cite recorded facts as `` `source:date` `` and flag inferences. Close with a `🔎 Gap:` line when something material is missing. Synthesize — don't paste raw file contents.

**Tentative (unmerged) evidence** is marked `⏳ tentative (unmerged, PR #N)`. If a tentative fact contradicts what's on `main`, surface both and note that merging the PR would make the tentative version win. Offering to merge is `sec-merge` / `babysit` — this skill stays read-only.

Use judgment on the detail; don't enumerate every case. Anything invariant about
the user (language, git conventions, what's private, folder layout) lives in the
runtime's CLAUDE.md, not here. Current-moment data comes from the runtime (the
engine's lookup sources), not this file.

## Atomic ops

Deterministic pre-pass (no LLM):

```bash
secretary recall "<subject>" --format json
secretary fresh <module> --format json   # step 0 when medium is an extractor
secretary config path wiki.articles
```

Use hits as a file index; synthesis and unmerged scan remain the skill's job.
