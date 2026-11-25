---
name: componer
description: Compose branded figures, slides, and document assets as editable HTML, review individual elements in a live preview, and export a transparent PNG at 2×. Use for branded deliverables and /componer.
user-invocable: true
---

# Compose branded visuals

1. Find the project's design system and read its typography, color, and theme guidance. Load its CSS tokens and use the declared variables for the visual. Keep fonts and other dependencies available from both the preview and the renderer.
2. Keep the editable HTML in the project. Put the exported visual in a single `#capture` element. Keep the page background transparent and apply any intentional backgrounds to the elements that need them.
3. Open the HTML in the environment's live preview. Use its element picker when available. Otherwise, give elements stable, descriptive IDs and use those IDs to anchor feedback. Apply the edit to the HTML, refresh the same view, and verify the element with the reviewer.
4. Export the approved element using [render.py](scripts/render.py). Confirm that the PNG matches the preview and that any intended transparent areas preserve alpha.

```sh
python -m pip install playwright
python -m playwright install chromium
python /path/to/componer/scripts/render.py input.html output.png
```

For a static preview, the renderer accepts a local HTML path or a loopback HTTP URL. The optional third argument changes the capture selector. Serve only the project files needed for preview.
