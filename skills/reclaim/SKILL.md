---
name: reclaim
description: >-
  On-demand disk reclamation — inventory the disk, clear regenerable caches, triage transit
  folders, migrate to Drive what belongs there, and recommend a restart. Interactive and
  thorough, unlike the weekly tidy-up routine (transit folders only). Use when the user asks to
  free space, the disk is below ~15% free, or a previous run needs repeating. Triggers:
  "/reclaim", "free up space", "disk is full", "how much does my disk weigh", "repeat last
  month's cleanup". NOT for the light weekly triage of Desktop/Downloads/Documents.
user-invocable: true
---

# reclaim — disk reclamation

**Mission:** free disk space safely: delete what is regenerable, ask about everything else, and
leave the playbook better than you found it.

The detailed playbook (phases, paths, per-app procedures, decisions already taken) lives in the
**instance**, not here: `secretary config path operational.reclaim` → `README.md`. Read it first
and follow its phases in order. Do not embed paths or decisions in this skill.

## Guardrails

- **Delete the regenerable, ask for the rest.** Caches and verified duplicates go without asking.
  Photos, media, books, business data and anything with no verified copy need an explicit yes.
- **Verify before deleting; never assume.** "It should already be in Drive" is a hypothesis: check
  it (exact size or checksum) before removing the local file.
- **Never restart the machine, quit the user's apps or delete app data you cannot rebuild
  without an explicit yes.** Work that kills this session (closing the host app) is delegated to
  another harness with a self-contained prompt.
- **Loose credentials are deleted on sight** and reported with 🚨. Do not copy their values
  anywhere, including the playbook.
- **Do not assert a cause you did not verify**, and measure before promising savings.
- The playbook may only become **more cautious or more informed on its own**, never more
  permissive. Policy changes go through the user.

## Loop

1. Read the instance playbook (`secretary config path operational.reclaim`).
2. Run its phases in order (inventory → caches → transit folders → Drive → pipelines → close).
   Group questions to the user at the end of each phase, not per file.
3. While working, keep a list of findings in the session scratchpad: new paths, commands that
   failed, assumptions that turned out false, the free-space baseline.
4. At close, run the playbook's last phase: turn the findings into a **pull request** against the
   instance (worktree from `origin/main`, never an edit on the main checkout, never self-merged).

## Report

Compact, `sec-output` style: free space before → after, what was done vs proposed, 🚨 alerts, and
the link to the learnings PR. No long `du`/`find` listings in chat.

## Trust your judgment

The playbook records cases, not every branch. When a path or app is new, classify it
(regenerable / transit / real data), ask once, and capture the answer as a finding.
