---
name: desk-design
description: >-
  Check whether a proposed new module, skill, catalog, or abstraction is genuinely new or
  actually the same underlying data/transformation as something that already exists — before
  building it. Applies a DDD/DOD design heuristic (find the real data and transformation, not
  the vocabulary) instead of a scheduled audit. Invoke at the decision point, right before
  creating structure — not on a cadence. Triggers: "/desk-design", "¿esto ya existe parecido?",
  "¿fusiono X con Y?", "se siente redundante", "premature abstraction", a feeling of skill or
  catalog sprawl, "should this be its own skill/catalog/module".
---

# desk-design

**Mission:** decide whether a proposed new module/skill/catalog/abstraction should be built as
new, merged into something existing with a discriminator, or kept separate under a shared
contract — before it's built, grounded in the actual repo and its own design-doc trail, not in
how similar the names sound or in a fixed set of examples memorized once.

## Guardrails

- **Read-only judgment call.** Never merges, renames, or refactors files itself — reports a
  recommendation for the owner or session to act on.
- **Don't force a finding to justify being invoked.** "Build it separately, they're genuinely
  different" is a common, valid outcome.
- **Ground every claim in the repo, never in memory.** Read the candidate files, grep for the
  actual write/read pattern, check a real commit if one exists — don't assert "these are the
  same" or "these are different" without evidence.
- **Don't hardcode precedents.** Rely on whatever the instance's own design-doc hierarchy
  currently holds (see step 0) — an instance without that hierarchy still gets the heuristic in
  step 2 onward; the pointer is an enrichment, not a dependency.

## Loop

0. **Consult the instance's design-doc hierarchy, if one exists** — resolve via
   `secretary config path rules` (rule surface) and the instance's design index (e.g. a
   `specs/README.md`-style index, a decisions log, a research/investigation log). Read whatever
   is actually live there for prior precedent on this domain; don't assume a specific filename.
   Absent any of this, proceed from step 1 with generic reasoning.
1. Identify the things in tension: the proposed new thing, and the existing thing(s) it might
   overlap with (a skill, a catalog file, a routine, a module).
2. For each, find the real data and the real transformation — who writes it, who reads it, what
   triggers it — not what it's named or how its description reads. Read the actual files.
3. Compare triggers and mechanics, not vocabulary. Two things that sound similar ("both are
   opt-in", "both are a catalog", "both read fresh state") only merge if the trigger and the
   write/read authority are actually the same.
4. If they're the same transformation with only a few varying fields → recommend one shape with
   a discriminator column/field, not two separate files or skills.
5. If they share a control-loop shape but the domain-specific payload differs meaningfully →
   recommend a shared contract/doctrine reference instead of a full merge.
6. If they're genuinely different transformations that merely sound alike → recommend building
   separately, and state the concrete difference in trigger or write authority as the reason.
7. If a real but small duplication turns up (repeated boilerplate, not a repeated shape) →
   recommend a follow-up task via `spawn_task` rather than a redesign of either thing.
8. If a durable, reusable outcome emerges (a new discriminator pattern, a new shared contract) —
   note in the report that it belongs in the instance's own rule surface, not only in this
   session's transcript; don't write it there yourself unless asked.

## Report

Render inline. Header: `🧩 **Design check** · <thing A> vs <thing B>`. One paragraph verdict —
merge-with-discriminator / shared-contract / keep-separate / follow-up-task — followed by the
concrete evidence checked (files, commits, grep results). Close with the one-line reason a future
reader would need, not a recap of the theory behind it.

Use judgment on the detail; don't enumerate every case. Anything invariant about
the user (language, git conventions, what's private, folder layout) lives in the
runtime's AGENTS.md, not here. Current-moment data comes from the runtime (the
engine's lookup sources), not this file.
