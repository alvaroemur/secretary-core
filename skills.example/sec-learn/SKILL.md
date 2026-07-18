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

**Mission:** turn a concrete harness/system friction or improvement into an actionable backlog
signal by invoking the **dispatch** playbook (usually `ISSUE`, optionally `ISSUE+WIKI`). Never a
second write path.

Doctrine: `rules/skills-contract.md` · GitHub signatures: `rules/github-signatures.md` ·
Issues relacionados: `rules/issues-relacionados.md` · Playbook: skill `dispatch`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
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
3. **Build the learning payload** with this issue body shape (keep owner language in the body;
   skill prose stays English):

   ```markdown
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

4. **Invoke dispatch playbook** (capability-gated, same as `dispatch`):
   - If `spawn_task` exists → chip with-context; `prompt` includes the payload labeled
     `learning` and triage hint **ISSUE** (optionally ISSUE+WIKI). Chip `cwd` = dest root.
   - Else (Cursor / core) → create the GitHub issue now with signatures; optional
     `.cursor/tasks/` brief only if follow-up execute is requested.

   Signature block before `gh issue create`:

   ```bash
   export SECRETARY_SKILL=sec-learn
   export SECRETARY_BRANCH=$(git -C <dest> branch --show-current 2>/dev/null || true)
   SIG_MARK=$(~/.claude/scripts/sec-signature.sh sec-learn --mark)
   SIG_FOOT=$(~/.claude/scripts/sec-signature.sh sec-learn --footer)
   # Body: "${SIG_MARK}\n\n<learning sections>\n\n---\n${SIG_FOOT}"
   ```

5. If the new issue lists related issues under `## Relacionado`, add reciprocal links per
   `rules/issues-relacionados.md`.
6. **Report** the issue URL and stop — do not implement the improvement in this call unless the
   owner asked for EXECUTE.

## Report

One **inline** line. Header: `📎 **Learn** · `` `<repo>` `` · issue `<url>` `` · triage ISSUE|ISSUE+WIKI`.
Add a second line only for warnings (out-of-allowlist repo, redirected to sec-write/lessons).

Use judgment on the detail; don't enumerate every case. Owner language, git conventions, and
workspace maps live in runtime `CLAUDE.md`.
