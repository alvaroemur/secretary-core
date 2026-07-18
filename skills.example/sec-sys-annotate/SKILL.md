---
name: sec-sys-annotate
description: Internal primitive. Adds a sec:pending annotation block inline in a wiki article, immediately below the target section heading. Does NOT touch the article's prose. Called by sec-write when the destination is the wiki; the annotation is later integrated by sec-sys-integrate inside wiki-update.
---

# sec-sys-annotate

**Mission:** write a `sec:pending` annotation block inline in a wiki article — fast, non-destructive. The block marks where new information should be integrated, without touching the existing prose.

## Guardrails
- **Never touch prose** — only insert the annotation block; leave all existing content intact.
- **Preserve existing `sec:pending` blocks** — if one already exists in the same section, append a new one below it (don't merge, don't overwrite).
- **Resolve paths via `.secretary.yml`** — never hardcode `WIKI_ROOT`.
- **Synthesize the signal before writing** — no raw source dumps in the block.

## Loop

1. **Resolve the article path** from the slug using the same derivation rules as `wiki-write` (type → subcarpeta; minúsculas, sin tildes, spaces → `-`). Check if the file exists.

2. **Locate the target section:**
   - If the article exists and the section heading is found → insert the block immediately after the heading line (before the next `##` or EOF).
   - If the article exists but the section is NOT found → append the section heading + block at the end of the article (before `## Véase también` if present).
   - If the article does NOT exist → create it with minimal frontmatter + the section heading + block only. Use this frontmatter skeleton:
     ```yaml
     ---
     titulo: {titulo}
     tipo: {tipo}
     ultima_actualizacion: {hoy}
     fuentes: []
     ---
     ```

3. **Write the block** immediately below the section heading (one blank line before the block):

   ```
   <!-- sec:pending source="<fuente_id>" date="<AAAA-MM-DD>"
   <synthesized signal — plain text or short markdown>
   -->
   ```

4. **Log** to `WIKI_ROOT/memory/indice.md`:
   ```
   YYYY-MM-DD | sec-sys-annotate | <slug> | anotación pendiente en §<sección> desde <fuente_id>
   ```

5. **Commit** (`~/.secretary` auto-commit policy — main directo):
   ```bash
   git -C ~/.secretary add wiki/articulos/<slug>.md wiki/memory/indice.md
   git -C ~/.secretary commit -m "docs(wiki): anotar <slug> §<sección> — pendiente de integrar"
   ```
   Only commit if the file actually changed.

## Report
`<ruta absoluta del artículo>` · `annotated` / `created+annotated` · sección afectada · sha del commit (o `sin commit`).

---
Paths come from `.secretary.yml`. Integration of the block into prose is not your job — that's `sec-sys-integrate`. If the slug or section heading were not given, ask before writing.
