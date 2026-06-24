# Personal Wiki

Wikipedia-style personal wiki. An aggregation destination where various apps and routines (mail processing, Meet transcriptions, Drive indexes, calendar) consolidate the knowledge they gather about the user.

## Structure

- `articulos/` — Markdown sources. One subfolder per category.
  - `user-profile.md` — main profile article.
  - `personas/` — one `.md` per relevant person.
  - `organizaciones/` — companies, clients, projects.
  - `temas/` — areas, interests, recurring activities.
- `assets/` — CSS and JS for the viewer.
- `build/build.py` — static site generator.
- `output/` — generated HTML. Open `output/index.html` in the browser.
- `memory/indice.md` — change log maintained by agents.

## Article format

```markdown
---
titulo: Article name
tipo: persona            # persona | organizacion | tema | perfil
infobox:
  Field: Value
  Other field: Value
categorias: [personas]
ultima_actualizacion: 2026-04-22
fuentes:
  - tipo: correo
    ref: <gmail-message-id>
  - tipo: drive
    ref: https://drive.google.com/...
---

## Section
Markdown content.

Internal links: [[personas/juan-perez]] or [[user-profile]].
```

## Build

```
python3 secretary/memoria/wiki/build/build.py
```

Generates `output/` with one HTML file per article plus `index.html` (landing page with client-side search, recent articles, categories).

No external dependencies: frontmatter and Markdown parsing done with the standard library.

## Contract for external routines

Any agent or routine that wants to write to the wiki must:

1. Create or edit a `.md` file in the correct subfolder of `articulos/`.
2. Respect the frontmatter. Update `ultima_actualizacion` (YYYY-MM-DD) and add entries to `fuentes`.
3. Use `[[slug]]` or `[[category/slug]]` for internal links; the builder resolves them.
4. Add a line to `memory/indice.md` with date + summary of the change.
5. Run `build.py` (or leave it to a rebuild task).

Do not invent data: unknown fields should be left as `[to be filled]`.
