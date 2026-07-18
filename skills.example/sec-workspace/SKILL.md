---
name: sec-workspace
description: >-
  Alias for sec-cowork-audit. Audit ~/Cowork/ project folders against canonical
  layout (sistemas-ordenamiento §3 profiles + skeleton). Proposes relocations —
  never moves without OK. Triggers: "/sec-workspace", "ordena Cowork",
  "drift estructural", "dónde va este proyecto". Prefer "/sec-cowork-audit";
  single-folder skeleton → sec-cowork-fit.
---

# sec-workspace → sec-cowork-audit (compat alias)

**This skill is a stub.** Canonical name: **`sec-cowork-audit`**.

When invoked as `/sec-workspace` or `sec-workspace`, **read and follow**
[`../sec-cowork-audit/SKILL.md`](../sec-cowork-audit/SKILL.md) in full — same
mission, inputs, loop, and guardrails.

| Intent | Skill |
|--------|-------|
| Portfolio / drift audit ("ordena Cowork") | `sec-cowork-audit` (this alias) |
| One folder skeleton (bootstrap / diagnose / apply) | `sec-cowork-fit` |

Do not implement audit logic here; do not silently switch to `sec-cowork-fit`
unless the owner named a single project path and asked to fit/bootstrap it.
