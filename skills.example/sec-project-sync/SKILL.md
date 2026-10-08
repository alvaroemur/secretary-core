---
name: sec-project-sync
description: >-
  Synchronize stable project instructions, source references and repository hygiene
  after session changes. Check entity-contract and layout drift without mutating
  the contract. Reuse close_context during wind-down.
user-invocable: true
---

# sec-project-sync — project instructions and hygiene

Keep project instructions accurate and session scratch out of canonical deliverables. Use this during project checkpoints or as part of wind-down.

## Context and scope

When given `close_context`, reuse its files, decisions, actual checkout and brief. Do not scan git, conversation history or unrelated worktrees again.

When invoked independently, collect only the active project's relevant state once. Identify its project AGENTS.md, workspace AGENTS.md, canonical sources and applicable layout policy.

## Stable project instructions

Update the nearest project AGENTS.md only for stable decisions from this session. Check:

- Stakeholders and roles that govern the engagement.
- Canonical source IDs and URLs, spreadsheet tab names and GIDs where relevant.
- Deliverable taxonomy, definitions and model conventions.
- Operating rules such as authorized accounts, dynamic formulas and batching parameters.
- Commands, folder conventions and references needed to resume accurately.

The workspace root keeps an index of project instructions; do not duplicate their content. If a needed project AGENTS.md is missing, propose its content from verified facts.

Do not add a session diary, PR status or next steps to AGENTS.md. Durable knowledge belongs in the configured memory/wiki flow; transient continuity belongs in the brief.

Use AGENTS.md for project instructions. Do not create harness-specific instruction alternatives. Before removing a legacy instruction file, verify that exclusive content has been migrated and the active harness reads AGENTS.md.

## Scratch hygiene

Review only files created or touched by this session. Remove only scratch positively identified as disposable and authorized by the session or repo policy.

Never delete by broad patterns such as `test_*.py`, `payload_*.json` or `values_*.json`: these may be real source files or datasets. Preserve canonical deliverables, curated datasets, scripts and tests. Put new scratch in the repo's configured temporary area.

## Layout and entity contract

Check affected folders against the applicable project profile. Typical engagement folders include admin, inputs, execution, communications, deliverables and logs; use the actual layout policy rather than inventing a skeleton.

If `contract.yaml` has `kind: entity`:

1. Read activity IDs, including children, and compare them with affected execution folders.
2. Report extra disk folders as drift; never copy folder names into the EDT.
3. Report missing folders separately; a pending activity may legitimately lack a folder.
4. If `edt.validated_at` is null, state that the EDT is not audited.
5. The contract wins when AGENTS.md contradicts status, mirrors or EDT IDs. Report the conflict.

Do not mutate contract.yaml. If a necessary contract is absent, propose the available template and intake flow; never invent an EDT.

## Continuity and delivery

During wind-down, add the review result to `close_context`. Handover is the sole brief writer. Do not create another continuity document or repeat its questions.

Independently, update an existing brief only when continuation was requested. Keep work-repo briefs in their checkout's `.briefs/`, never in the instance brief tree.

Report changed instructions, corrected source references, hygiene applied, layout/contract drift and remaining blockers. If no stable rule changed, report "no instruction changes". Do not claim an untouched repo is clean or ready to commit.
