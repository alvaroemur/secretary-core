---
name: sec-write
description: >-
  Write primitive for secretary's memory. Persists a signal or conclusion to the right place —
  the long-term wiki (via lazy annotation) or a module's memory/state. Use when an agent or
  routine needs to persist information into secretary. Generalizes and orchestrates wiki-write.
---

# sec-write — memory write primitive

**Mission:** persist a signal or conclusion in the right place of secretary's memory, without
duplicating or clobbering what is already there.

Doctrine: `rules/skills-contract.md`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
```

## Guardrails

- **Wiki path → annotate, never merge directly.** Write a `sec:pending` block inline in the article;
  `wiki-update` integrates it later. Do not rewrite article prose.
- **Non-wiki path → merge carefully.** Preserve existing content in module `memory/` files.
- **Resolve paths via CLI** — never hardcode instance roots.
- **Synthesize, never dump raw source content.**
- Do not run builds or touch generated output (`wiki/output`).

## Policies (Cowork artifacts — cross-ref)

This skill writes secretary memory only. For borradores/entregables in Cowork, other skills own
persistence — but if this session also persists an MD mirror, read
`operational.sistemas_ordenamiento` (§6–7) before writing.

```bash
secretary config path operational.sistemas_ordenamiento
```

## Loop

1. Understand input: content, source, subject.
2. Decide destination (if unclear, ask — do not invent):
   - Durable knowledge about an entity (person/org/topic) → **wiki path**: delegate to `sec-sys-annotate`.
   - Module state or processing memory → that module's `memory/` or `state` file, merged directly.
3. Execute:
   - **Wiki path:** call `sec-sys-annotate` with article slug, section heading, synthesized signal,
     source id, date. Done — do not touch prose.
   - **Non-wiki path:** `secretary config path <key>`, merge write, cite source, log change.

## Annotation format (wiki path)

`sec-sys-annotate` writes this block immediately below the target section heading:

```
<!-- sec:pending source="<source>" date="<YYYY-MM-DD>"
<synthesized signal text>
-->
```

Invisible in rendered output; visible when opening the markdown file directly.

## Report

One **inline** line. Header: `✍️ **Write** · `` `<path>` `` · <flag> <detail>`, where flag is
✅ annotated / ✅ updated / 🟡 unchanged. Note section or file touched and any ⚠️ warning. One line
unless there is a conflict to flag.

## Atomic ops

```bash
secretary config path <key>    # e.g. mail.memory, wiki.articles, meetings.memory
secretary paths                # all configured destinations
```

Use the printed path in the skill report; do not hardcode `extractors/...`.

User language, git conventions, and folder layout live in runtime `CLAUDE.md`. Wiki integration is
handled by `sec-sys-integrate` inside `wiki-update`.
