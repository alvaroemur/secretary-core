---
name: sec-consolidate
description: Distill and deduplicate long-term memory — merge scattered evidence from module memory files into wiki articles, prune stale or redundant entries. Use at end-of-session or as a scheduled pass when memory has accumulated and needs compaction.
---

# sec-consolidate

**Mission:** reduce memory debt by merging dispersed module evidence into canonical wiki articles and pruning what's no longer useful.

## Guardrails
- **Never delete without a replacement** — if removing a raw evidence file, confirm the fact already lives in the wiki or module state.
- **Don't touch generated output** (`wiki/output/`) — only source articles and memory files.
- **One source of truth per fact** — if a fact appears in both a module memory file and a wiki article, the wiki article wins; the raw entry can be removed after confirming.
- Stop and report if a merge decision is ambiguous (conflicting dates, contradictory facts) — don't silently pick one.

## Loop
1. Identify scope: full pass or a specific module/entity (from the invocation context).
2. Resolve lookup sources via `.secretary.yml`; list what has accumulated since the last consolidation (check dates in module `memory/` files vs. wiki `ultima_actualizacion`).
3. For each module's new evidence: classify — does it update an existing wiki article, create a new one, or belong only in module state?
4. Merge into wiki via `sec-write` (delegates to `wiki-write` for the actual write). Don't duplicate what's already there.
5. After a successful merge, remove or truncate the raw evidence that's now captured in the wiki. Log what was pruned.
6. Check for duplicate wiki articles on the same entity (different slugs, same subject) — flag them; don't auto-merge without review.

## Report
Render **inline**. Header: `🧹 **Consolidate** · <scope>`. A compact tally line (✅ N articles updated/created · N raw entries pruned) and, if any, a `⚠️` list of flagged conflicts or ambiguous merges needing review. Close with `→` next-pass suggestion if memory debt remains.

Use judgment on the detail; don't enumerate every case. Anything invariant about
the user (language, git conventions, what's private, folder layout) lives in the
runtime's CLAUDE.md, not here. Current-moment data comes from the runtime (the
engine's lookup sources), not this file.
