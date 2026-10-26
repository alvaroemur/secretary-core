---
name: handover
metadata:
  close-contract: "3"
description: >-
  Write a self-contained handover with work state, decisions, blockers and how to
  resume. Reuse the single brief and close_context when called during wind-down.
  Keeps the brief lifecycle (pending, done, superseded). Use for explicit
  handovers, not durable memory or AGENTS.md updates.
---

# handover — session, repo or person handoff

Produce a Markdown brief that another session or person can resume from without chat history. Do not run tests, builds or linters to write it.

## Shared context

When given `close_context`, use its checkout, branch, commit, files, decisions, result, blockers, next action, references and chosen brief path. Do not collect git or conversation state again. Update that same brief if called again during the close.

For a standalone invocation, collect current checkout status, branch, commit, relevant session changes and decisions once. Do not use recent commits as proof that this session touched a file. Without git, state that fact and continue.

## Destination and identity

Infer a short title and destination from the request. Ask once if a material choice cannot be inferred. Do not ask again for inputs or permission already provided.

- Briefs are versioned: `.briefs/YYYY-MM-DD-HHMM-<slug>.md` in the repo, committed like any other file. Never scratchpad or `/tmp`.
- **With a topic branch** (the session runs in a `.wt/` or harness worktree): write the brief in that checkout and commit it on the topic branch; it reaches `main` with the PR. Cite it as `<branch>:.briefs/<file>` plus its absolute path, so another session can read it with `git show origin/<branch>:.briefs/<file>` before the merge.
- **Without a topic branch** (the session runs in the main checkout): write it in `<main-checkout>/.briefs/`, where `<main-checkout>` is the parent of `git rev-parse --path-format=absolute --git-common-dir`. wind-down routes the commit (topic branch and PR; the instance repo commits to `main`).
- If the harness blocks writing outside its worktree, never work around it with the shell: write inside the worktree and commit there.
- Standalone: respect an explicit destination. A person-facing handover may use `docs/handovers/` when requested.
- Keep briefs for work repos in those repos. Never place them in the instance brief tree.
- Use a lowercase slug, strip diacritics, collapse punctuation to hyphens and limit it to 60 characters.
- Update the known brief for this session. For an unrelated name collision, use a numeric suffix; do not overwrite or delete another handover.

## Lifecycle (frontmatter)

Every brief starts with:

```yaml
---
status: pending
created: <YYYY-MM-DDTHH:MM±HH:MM>
repo: <absolute main-checkout path>
branch: <branch>
---
```

| status | When | Where |
|---|---|---|
| `pending` | New brief; its work is not finished | `.briefs/` |
| `done` | The work it hands over is finished; add `closed: <YYYY-MM-DD>` | `.briefs/_archivo/` |
| `superseded` | A newer brief replaces it (add `superseded_by: <path>`), or it stayed pending >30 days without use; add `closed:` | `.briefs/_archivo/` |

- When this handover continues a thread that already has a `pending` brief, mark the old one `superseded` with `superseded_by` and move it to `_archivo/`.
- A session that resumes from a brief and finishes its work marks it `done` and moves it (wind-down does this at close).
- Move, never delete: `git mv` when the brief is tracked, plain `mv` otherwise, and commit the move with the rest of the session's work.

## Required content

Keep sections that carry information. Explain missing material facts instead of inventing them.

1. **Identity:** session, repo, branch, commit and timestamp with timezone.
2. **Context and result:** objective, why the handover is needed, work completed and partial work.
3. **Current state:** affected files or components, what works, what is broken or missing.
4. **Prioritized next steps:** action, inputs and observable completion criterion; include active todos.
5. **Decisions:** choice, reason and rejected paths that matter for continuation.
6. **Risks and blockers:** pending questions and mitigation.
7. **References:** absolute file paths, source links, PRs/issues and checks completed or pending. Only paths another agent can read.
8. **How to resume:** first, check whether the work was already done elsewhere; then first file to read, first action or command and next open question.

Write the handover in the user's configured language. Do not copy global instructions or a transcript. A chat link is supplemental, never the only context. Redact secrets.

## Preview and write

For a standalone handover, show the proposed Markdown and destination before writing when not already approved. Write only after approval. During wind-down, include the destination and summary in its single proposal; do not introduce another confirmation after the owner approved that proposal.

Return the absolute path and a short summary. Follow the configured signature policy.

## Git and boundaries

Do not change AGENTS.md or harness memory. Do not push. During wind-down, leave git work (including the brief's commit) to its orchestrator.

Jump consumes this brief and does not create a second one.
