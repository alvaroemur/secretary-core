# Wiki Sync Routine

**What this routine does:** Merges auto-generated PRs from extractor routines (mail, meetings, WhatsApp, Drive), reads consolidated memory files from all sources, integrates new information into wiki articles, runs consistency checks, rebuilds the HTML site, deploys it, and opens a PR with the change report.

This is the "transformation and loading" layer of the system. Extractor routines (mail-review, meetings-processor, whatsapp-monitor, drive-crawler) produce raw memory files. This routine reads those files and integrates them into the structured wiki.

> Designed for Claude Code scheduled tasks, but the pattern works with any AI coding agent that can read files, run shell commands, and call APIs.

## Prerequisites

- **Git** with push access to the instance repository
- **GitHub CLI** (`gh`) for PR management (list, merge, create)
- **Static site generator** for the wiki (the secretary-core wiki module, or Hugo, Eleventy, etc.)
- **Deploy mechanism** for the built HTML (git push to a deploy branch, rsync, Netlify CLI, etc.)
- Environment variables: `$INSTANCE`, `$CORE` (pointing to engine repo)

## Schedule

Daily, after all extractor routines have run (e.g., `0 12 * * *` — noon, assuming extractors run in the morning).

---

## Step 0 — Worktree setup

```bash
BRANCH="wiki/sync-$(date +%Y-%m-%d)"
WORKTREE="$INSTANCE/.claude/worktrees/wiki-sync-$$"

cd "$INSTANCE"
git fetch origin main
git worktree add "$WORKTREE" -b "$BRANCH" origin/main
cd "$WORKTREE"
```

## Step 1 — Merge extractor PRs

Before integrating new data, merge any pending PRs from extractor routines into main. This ensures the memory files in the worktree are up to date.

### 1a. List candidate PRs

```bash
gh pr list --base main --state open --json number,title,headRefName,labels
```

Filter for PRs matching extractor branch patterns:
- `mail/review-*`
- `meetings/process-*`
- `whatsapp/monitor-*`
- `drive/crawl-*`

### 1b. Pre-merge checks

For each candidate PR:

1. **Check for unresolved comments**: `gh pr view <number> --comments`. If there are unresolved review comments from the user, SKIP this PR and note it in the report. The user needs to resolve their feedback before the data gets integrated.
2. **Check CI status**: If the repo has CI checks, ensure they pass.
3. **Check for merge conflicts**: `gh pr view <number> --json mergeable`. Skip conflicted PRs.

### 1c. Merge

```bash
gh pr merge <number> --squash --delete-branch
```

After merging all eligible PRs, update the worktree:

```bash
cd "$WORKTREE"
git pull origin main
```

### 1d. Track provenance

Maintain a record of which items came from which PR vs. pre-existing data. This is important for debugging and for the user to understand where information came from.

```
merged_prs=("PR #42 mail/review-2026-05-22" "PR #43 meetings/process-2026-05-22")
```

Log these in the final report.

## Step 2 — Read consolidated memory files

Scan memory directories from all sources:

| Source | Memory path | Key files |
|---|---|---|
| Mail | `$INSTANCE/mail/memory/` | `personas.md`, `organizaciones.md`, `entidades.md`, `suscripciones.md` |
| Meetings | `$INSTANCE/meetings/memory/` | `personas.md`, `organizaciones.md`, `entidades.md`, `acciones.md`, `reuniones.md` |
| WhatsApp | `$INSTANCE/whatsapp/memory/` | `personas.md`, `organizaciones.md`, `entidades.md`, `acciones.md`, `chats.md` |
| Drive | `$INSTANCE/drive/memory/` | `personas.md`, `organizaciones.md`, `proyectos.md`, `documentos-clave.md` |
| Wiki own | `$INSTANCE/wiki/memory/` | `dudas-pendientes.md`, `indice.md`, `fuentes-drive.md`, `dictados.md` |

For each file, extract items with `pendiente_wiki: true`. These are the items that need to be integrated.

## Step 3 — Integrate into wiki articles

For each pending item:

### 3a. Find or create the target article

- **Personas** go to `$INSTANCE/wiki/articulos/personas/<slug>.md`
- **Organizations** go to `$INSTANCE/wiki/articulos/organizaciones/<slug>.md`
- **Topics/Projects** go to `$INSTANCE/wiki/articulos/temas/<slug>.md`
- **Actions** get appended to the relevant person's or topic's article under an "Actions" section
- **Meetings** get summarized in the main user profile article under "Recent Activity"

If the article already exists, MERGE the new information — do not overwrite. Read the existing article first and only add genuinely new facts.

If the article does not exist, create it using the standard frontmatter template:

```markdown
---
title: "<Entity Name>"
slug: "<slug>"
tipo: persona | organizacion | tema
created: YYYY-MM-DD
updated: YYYY-MM-DD
fuentes:
  - "<source reference>"
---

# <Entity Name>

<Integrated content here>
```

### 3b. Source attribution

Every fact added to the wiki should be traceable. Use inline source references:

```markdown
Works at Acme Corp as VP of Engineering (source: mail 2026-05-22, meeting 2026-05-15).
```

### 3c. Conflict resolution

When two sources provide contradictory information:
- Use the most recent source as primary
- Note the discrepancy in the article: `<!-- conflict: mail says X, meeting says Y — using mail (more recent) -->`
- Add to `wiki/memory/dudas-pendientes.md` for the user to resolve

### 3d. Mark as integrated

After successfully integrating an item, flip its flag:

```markdown
- pendiente_wiki: false  # integrated YYYY-MM-DD by wiki-sync
```

Or remove the item from the memory file entirely if the memory file convention is "delete after integration."

## Step 4 — Modules panel

If the wiki has a "modules panel" (dashboard showing the user's active projects, roles, and key relationships), update it:

- Add new organizations where the user has an active role
- Update project statuses based on recent meeting/email data
- Remove or archive projects that have gone silent for 60+ days (move to "Inactive" section, don't delete)

## Step 5 — Tidy-up pass

Run consistency checks across all wiki articles:

### 5a. Broken links
Scan for `[[wikilinks]]` that point to non-existent articles. For each:
- If the target is close to an existing slug (typo), fix the link
- If the target is genuinely missing, create a stub article or add to `dudas-pendientes.md`

### 5b. Category mismatches
Check that articles are in the right directory:
- A persona article should be in `personas/`, not `organizaciones/`
- If an entity was miscategorized by an extractor, move it

### 5c. Stale fields
Check for articles with `updated:` dates older than 90 days that have active memory file entries. Update the `updated:` field.

### 5d. Duplicate detection
Look for articles that refer to the same entity under different names (common with phonetic transcription errors). Flag potential duplicates in the report.

### 5e. Index regeneration
Regenerate index files:
- `articulos/personas/_index.md` — alphabetical list of all persona articles
- `articulos/organizaciones/_index.md` — alphabetical list of all org articles
- `articulos/temas/_index.md` — alphabetical list of all topic articles

## Step 6 — Doubts backlog

Maintain `$INSTANCE/wiki/memory/dudas-pendientes.md` as an append-only file of things the routine could not resolve:

- Entities with ambiguous identity (same name, different people?)
- Facts that contradict existing wiki content
- Items marked `# duda:` by extractor routines
- Broken wikilinks with no obvious fix

Format:

```markdown
## YYYY-MM-DD — <brief description>
- source: <which memory file / PR>
- question: <what needs resolving>
- suggested_action: <what the routine would do if it could>
```

## Step 7 — Build and deploy

```bash
# Build the static HTML site
cd "$CORE/wiki"
node build.js --instance "$WORKTREE"

# Commit the built output
cd "$WORKTREE/wiki/output"
git add -A
git commit -m "build(wiki): rebuild $(date +%Y-%m-%d)"

# Deploy (adapt to your hosting setup)
# Option A: push to deploy branch
git subtree push --prefix wiki/output origin gh-pages

# Option B: rsync to server
# rsync -avz wiki/output/ user@server:/var/www/wiki/

# Option C: Netlify/Vercel CLI
# netlify deploy --prod --dir wiki/output
```

**Always commit and push the built output automatically after rebuild.** Do not ask for confirmation — the wiki deploy is a routine operation.

## Step 8 — Self-maintenance

This routine can edit its own file. If during the run the agent discovers a pattern that should be codified (e.g., "articles from source X always need field Y normalized"), it can:

1. Append a note to the "Learnings" section at the bottom of this file
2. Include the edit in the same PR for user review

This is how the routine improves over time. The user reviews and approves via PR merge.

## Step 9 — Commit and open PR

```bash
cd "$WORKTREE"
git add wiki/ mail/memory/ meetings/memory/ whatsapp/memory/ drive/memory/
git commit -m "docs(wiki): sync $(date +%Y-%m-%d)"
git push origin "$BRANCH"

gh pr create \
  --title "docs(wiki): sync $(date +%Y-%m-%d)" \
  --body "$(cat <<'REPORT'
## Wiki Sync Report — YYYY-MM-DD

### PRs merged before sync
- PR #NN — title (source)

### Articles created
- personas/new-person.md — from: mail memory
- organizaciones/new-org.md — from: meetings memory

### Articles updated
- personas/existing-person.md — added: new role at Company (from: mail)
- temas/project-x.md — updated: status to "in progress" (from: whatsapp)

### Actions integrated
- acc-YYYYMMDD-NNN — assigned to Person — deadline: YYYY-MM-DD

### Tidy-up fixes
- Fixed N broken wikilinks
- Moved N articles to correct category
- Regenerated N index files

### Doubts added
- [description of unresolved questions]

### Skipped PRs (unresolved comments)
- PR #NN — reason

### Learnings (self-edits to this routine)
- [any routine improvements made this run]
REPORT
)" \
  --base main \
  --label "routine:wiki"
```

## Step 10 — Cleanup

```bash
cd "$INSTANCE"
git worktree remove "$WORKTREE" --force
```

---

## Customization

1. **Extractor PR patterns**: Update the branch name patterns in Step 1 to match your actual routine branch naming convention.
2. **Memory file paths**: Adjust the table in Step 2 if your extractors use different directory names (e.g., `correo/` instead of `mail/`).
3. **Wiki article format**: The frontmatter template in Step 3 is a suggestion. Adapt to your static site generator's requirements.
4. **Build command**: Replace `node build.js` with your actual wiki build tool.
5. **Deploy method**: Choose one of the deploy options in Step 7 or add your own.
6. **Wikilink syntax**: This template assumes `[[slug]]` wikilinks. Adjust the tidy-up pass if you use a different linking convention.
7. **Doubts backlog**: If you prefer to track doubts as GitHub issues instead of a markdown file, modify Step 6 to use `gh issue create`.
8. **Self-maintenance**: If you don't want the routine to edit itself, remove Step 8. But this is one of the most powerful features — the routine gets better with each run.
9. **PR labels**: Create `routine:wiki` label (`gh label create routine:wiki --color 1D76DB`).
10. **Merge strategy**: The template uses `--squash` for extractor PRs. If you prefer merge commits for traceability, change to `--merge`.

---

## Learnings

_This section is appended to by the routine itself during runs. Review and curate periodically._
