---
name: desk-workspace
description: >-
  Alias for desk-cowork-audit. Audit ~/Cowork/ project folders against canonical
  layout (sistemas-ordenamiento §3 profiles + skeleton). Proposes relocations —
  never moves without OK. Triggers: "/desk-workspace", "ordena Cowork",
  "drift estructural", "dónde va este proyecto". Prefer "/desk-cowork-audit";
  single-folder skeleton → desk-cowork-fit.
---

# desk-workspace → desk-cowork-audit (compat alias)

**This skill is a stub.** Canonical name: **`desk-cowork-audit`**.

When invoked as `/desk-workspace` or `desk-workspace`, **read and follow**
[`../desk-cowork-audit/SKILL.md`](../desk-cowork-audit/SKILL.md) in full — same
mission, inputs, loop, and guardrails.

| Intent | Skill |
|--------|-------|
| Portfolio / drift audit ("ordena Cowork") | `desk-cowork-audit` (this alias) |
| One folder skeleton (bootstrap / diagnose / apply) | `desk-cowork-fit` |

Do not implement audit logic here; do not silently switch to `desk-cowork-fit`
unless the owner named a single project path and asked to fit/bootstrap it.
