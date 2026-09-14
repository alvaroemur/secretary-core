---
name: sec-learn
description: >-
  Capture a system/harness learning or improvement as a durable backlog item via dispatch
  (default triage: ISSUE). Thin wrapper — does not invent a write pipeline. Intent is skills,
  tooling (gog, CI, mail HTML limits), and harness friction — NOT business facts (sec-write/wiki)
  and NOT dream hygiene (subsystem/dream/lessons.md). Triggers: "/sec-learn", "captura este
  aprendizaje", "lesson for the system", "harness friction", "aprendizaje del sistema".
user-invocable: true
---

# sec-learn — harness learning → dispatch

**What this does:** turn a concrete harness/system friction or improvement into an actionable backlog
signal by invoking the **dispatch** playbook (usually `ISSUE`, optionally `ISSUE+WIKI`). Never a
second write path.

Doctrine: `rules/skills-contract.md` · GitHub signatures: `rules/github-signatures.md` ·
Issues relacionados: `rules/issues-relacionados.md` · Playbook: skill `dispatch` · Recurrence
(spec 024 SC-4): fingerprint = issue marker `<!-- fingerprint: <slug> -->` — dedupe before create.

## Instance setup

```bash
eval "$(secretary env)"
CFG=$(secretary config show)
# Destination allowlist (slug + local path)
echo "$CFG" | jq -r '.dispatch.executor.repos[] | "\(.repo)\t\(.path)"'
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
```

## NOT for

| Intent | Use instead |
|--------|-------------|
| Business / entity facts (person, client, project) | `sec-write` → wiki / module memory |
| Dream/drone correction hygiene ("don't repeat this job mistake") | `subsystem/dream/lessons.md` (or the agent's lessons store) |
| Mid-thread "remember this later" with no harness angle | `dispatch` directly (blob / with-context) |
| End-of-session sweep that only *detects* candidates | `wind-down` Stage 1–2 → call this skill on **Y** |

## Guardrails

- **Wrapper only.** Classify → choose dest repo → invoke **dispatch** issue-create (or chip
  playbook if `spawn_task` exists). Do not invent a parallel store under `subsystem/` or wiki.
- **Default triage: ISSUE.** Optionally `ISSUE+WIKI` when the learning is also durable doctrine.
  Rarely `EXECUTE` — only if the fix is ~15 min and the owner asked to ship now.
- **Signature mandatory** on every `gh issue create` / comment — same as `dispatch`.
- **Do not send mail, merge PRs, or rewrite skills** unless Stage/owner explicitly asks for that
  separate work.
- Resolve repos via `dispatch.executor.repos` / instance `CLAUDE.md` — never hardcode slugs.

## Inputs

Either:

1. **Free text** — discovery narrative from the session (“gog --attach has no CID…”), or
2. **Structured fields** (preferred when wind-down pre-fills):
   - `discovery` — what was observed
   - `friction` — what slowed or broke work
   - `proposed_improvement` — concrete next change
   - `destination_repo` — allowlist slug or logical name (optional; skill routes if omitted)
   - `session_evidence` — links, paths, versions, dates

## Loop

1. **Classify.** Is this really harness/system learning?
   - Yes → continue.
   - Business fact → stop and point to `sec-write`.
   - Dream hygiene only → stop and point to the lessons store.
2. **Choose destination repo** from `dispatch.executor.repos` (+ instance Cowork/Dev map):
   - Skills, gog, sec-mail, signatures, secretary CI → instance / `brief.repo`
   - Client product / Dev repo infra → that allowlisted repo (or report out-of-allowlist and ask)
3. **Fingerprint (spec 024, SC-4) — before opening anything.**
   The ad-hoc registro de recurrencia **is the issue itself**. Compute a stable kebab-case slug
   from the *finding* (object/path/symptom), not from free prose. Examples:
   `main-checkout-guard-missing`, `gog-attach-no-cid`, `validate-wikilinks-scans-worktrees`.

   ```bash
   FP="<slug>"   # kebab-case, stable across sessions
   DEST_REPO="<chosen allowlist slug>"   # from step 2; usually $BRIEF_REPO for harness
   # Search open + recently closed issues for the HTML marker (not title fuzzy match):
   MATCH=$(gh issue list --repo "$DEST_REPO" --state all --limit 50 \
     --json number,title,state,body,labels,url \
     --jq --arg fp "$FP" \
     '.[] | select(.body | contains("<!-- fingerprint: " + $fp + " -->"))')
   ```

   - **If match:** do **not** create a duplicate. Comment the new evidence on the existing issue.
     Count prior `sec-learn` / fingerprint evidence comments (+ original body = 1). At **N=3**
     consecutive reports of the same finding while still open: add label `para-alvaro` (if missing)
     and say so in the comment. Report the existing URL and stop.
   - **If no match:** continue to step 4 and **embed** the marker in the new issue body.

4. **Build the learning payload** (owner language in the body; skill prose stays English).
   Put the fingerprint marker on its own line near the top (after the signature mark):

   ```markdown
   <!-- fingerprint: <slug> -->

   ## Discovery
   <what was observed>

   ## Friction
   <what broke or slowed the session>

   ## Proposed improvement
   <concrete change — skill, docs, tooling, CI>

   ## Destination
   <repo slug · optional local path key>

   ## Session evidence
   - <paths, versions, dates, related PRs/issues>
   ```

5. **Invoke dispatch playbook** (capability-gated, same as `dispatch`):
   - If `spawn_task` exists → chip with-context; `prompt` includes the payload labeled
     `learning`, the fingerprint slug, and triage hint **ISSUE** (optionally ISSUE+WIKI).
     Chip `cwd` = dest root. Instruct the chip to run the fingerprint search (step 3) before
     `gh issue create`.
   - Else (Cursor / core) → after step 3 found no match, create the GitHub issue now with
     signatures + fingerprint marker; optional `.briefs/` brief only if follow-up execute is
     requested.

   Signature block before `gh issue create`:

   ```bash
   export SECRETARY_SKILL=sec-learn
   export SECRETARY_BRANCH=$(git -C <dest> branch --show-current 2>/dev/null || true)
   SIG_MARK=$(~/.claude/scripts/sec-signature.sh sec-learn --mark)
   SIG_FOOT=$(~/.claude/scripts/sec-signature.sh sec-learn --footer)
   # Body: "${SIG_MARK}\n\n<!-- fingerprint: ${FP} -->\n\n<learning sections>\n\n---\n${SIG_FOOT}"
   ```

6. If the new issue lists related issues under `## Relacionado`, add reciprocal links per
   `rules/issues-relacionados.md`.
7. **Report** the issue URL (or "evidence added to #N") and stop — do not implement the
   improvement in this call unless the owner asked for EXECUTE.

## Report

One **inline** line. Header: `📎 **Learn** · `` `<repo>` `` · issue `<url>` `` · triage ISSUE|ISSUE+WIKI`
· `fp:<slug>` (add `· evidence-on-existing` when step 3 commented instead of creating).
Add a second line only for warnings (out-of-allowlist repo, redirected to sec-write/lessons,
escalated to `para-alvaro` at N=3).

Use judgment on the detail; don't enumerate every case. Owner language, git conventions, and
workspace maps live in runtime `CLAUDE.md`.
