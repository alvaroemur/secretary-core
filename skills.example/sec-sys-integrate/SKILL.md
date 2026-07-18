---
name: sec-sys-integrate
description: Internal primitive. Scans wiki articles for sec:pending annotation blocks and integrates each signal into the article's prose. Called by wiki-update as a pre-step before the HTML build. Marks conflicts with sec:conflict when two blocks in the same section contradict each other.
---

# sec-sys-integrate

**Mission:** consume `sec:pending` annotation blocks in wiki articles — integrate each signal into the surrounding prose, then remove the block. Leave the article in a clean, merged state ready for the HTML build.

## Guardrails
- **Integrate, then delete the block** — never leave a processed block in the file.
- **On conflict, flag — don't guess** — two blocks in the same section that contradict each other become `<!-- sec:conflict -->` entries for manual review.
- **Preserve all content outside the blocks** — manual prose and `<!-- auto:... -->` blocks are untouchable.
- **Idempotent** — running twice on an already-integrated article produces no change.
- **Resolve paths via `.secretary.yml`** — never hardcode `WIKI_ROOT`.

## Loop

1. **Discover articles with pending blocks:**
   ```bash
   grep -rl 'sec:pending' WIKI_ROOT/articulos/
   ```
   If no results, report `0 artículos con bloques pendientes` and exit cleanly.

2. **For each article**, process its pending blocks in order:

   a. Parse each `<!-- sec:pending source="..." date="..."` block: extract source, date, and signal content.

   b. Read the surrounding section (content between this block's `##` heading and the next `##` or EOF).

   c. **Check for conflict:** if two or more blocks in the same section contain information that directly contradicts each other (same fact, different values), replace both with:
      ```
      <!-- sec:conflict
      [block 1 content — source="..." date="..."]
      [block 2 content — source="..." date="..."]
      Resolución requerida manualmente.
      -->
      ```
      Do not integrate conflicting blocks; leave them for User.

   d. **Integrate:** rewrite the section prose to naturally incorporate the signal. Rules:
      - Don't duplicate: if the signal is already expressed in the prose, discard the block silently.
      - Don't invent: only add what the block explicitly states.
      - Preserve the existing prose's voice and structure; add the new information where it fits logically.
      - Remove the `sec:pending` block after integration.

3. **Write** the updated article.

4. **Log** to `WIKI_ROOT/memory/indice.md` — one line per article touched:
   ```
   YYYY-MM-DD | sec-sys-integrate | <slug> | integrados <N> bloques, <M> conflictos
   ```
   If an article had no changes (all signals already present), do not log.

5. **Commit** (`~/.secretary` auto-commit policy — main directo):
   ```bash
   git -C ~/.secretary add wiki/articulos/ wiki/memory/indice.md
   git -C ~/.secretary commit -m "docs(wiki): integrar anotaciones pendientes — <N> artículos"
   ```
   Only commit if at least one article changed.

## Report
One summary line per article: `<slug>` · `<N> integrados` · `<M> conflictos` · `sin cambios`.
Then total: `<X> artículos procesados, <Y> bloques integrados, <Z> conflictos`.

---
Paths come from `.secretary.yml`. Called by `wiki-update` as a pre-step before the HTML build; can also be invoked standalone for a one-off integration pass. Conflict resolution is always manual — never guess when signals disagree.
