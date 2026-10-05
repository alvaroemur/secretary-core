---
name: handover
description: >-
  Write a self-contained handover with work state, decisions, blockers and how to
  resume. Reuse the single brief and close_context when called during wind-down.
  Use for explicit handovers, not durable memory or AGENTS.md updates.
---

# handover — session, repo or person handoff

Produce a Markdown brief that another session or person can resume from without chat history. Do not run tests, builds or linters to write it.

## Shared context

When given `close_context`, use its checkout, branch, commit, files, decisions, result, blockers, next action, references and chosen brief path. Do not collect git or conversation state again. Update that same brief if called again during the close.

For a standalone invocation, collect current checkout status, branch, commit, relevant session changes and decisions once. Do not use recent commits as proof that this session touched a file. Without git, state that fact and continue.

## Destination and identity

Infer a short title and destination from the request. Ask once if a material choice cannot be inferred. Do not ask again for inputs or permission already provided.

- During wind-down: use its chosen `<actual-checkout>/.briefs/YYYY-MM-DD-HHMM-<slug>.md`.
- Standalone: respect an explicit destination; otherwise use the active repo's `.briefs/`. A person-facing handover may use `docs/handovers/` when requested.
- Keep briefs for work repos in those repos. Never place them in the instance brief tree.
- Use a lowercase slug, strip diacritics, collapse punctuation to hyphens and limit it to 60 characters.
- Update the known brief for this session. For an unrelated name collision, use a numeric suffix; do not overwrite or delete another handover.

## Required content

Keep sections that carry information. Explain missing material facts instead of inventing them.

1. **Identity:** session, repo, branch, commit and timestamp with timezone.
2. **Context and result:** objective, why the handover is needed, work completed and partial work.
3. **Current state:** affected files or components, what works, what is broken or missing.
4. **Prioritized next steps:** action, inputs and observable completion criterion; include active todos.
5. **Decisions:** choice, reason and rejected paths that matter for continuation.
6. **Risks and blockers:** pending questions and mitigation.
7. **References:** actual file paths, source links, PRs/issues and checks completed or pending.
8. **How to resume:** first file to read, first action or command and next open question.

Write the handover in the user's configured language. Do not copy global instructions or a transcript. A chat link is supplemental, never the only context. Redact secrets.

## Preview and write

For a standalone handover, show the proposed Markdown and destination before writing when not already approved. Write only after approval. During wind-down, include the destination and summary in its single proposal; do not introduce another confirmation after the owner approved that proposal.

Write to the actual checkout or explicit absolute destination. Return its path and a short summary. Follow the configured signature policy.

## Git and boundaries

Do not change AGENTS.md or harness memory. Do not push. During wind-down, leave git add/commit/push to its orchestrator. A standalone commit is optional and requires authorization; follow the repo's commit conventions.

Jump consumes this brief and does not create a second one.
