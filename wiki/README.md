# Wiki personal

Wiki estilo Wikipedia sobre Álvaro Mur. Destino de agregación donde diversas apps y rutinas (procesamiento de correo, transcripciones de Meet, índices de Drive, calendario) consolidan el conocimiento que van recopilando.

## Estructura

- `articulos/` — fuentes en Markdown. Una subcarpeta por categoría.
  - `alvaro-mur.md` — perfil principal.
  - `personas/` — un `.md` por persona relevante.
  - `organizaciones/` — empresas, clientes, proyectos.
  - `temas/` — áreas, intereses, actividades recurrentes.
- `assets/` — CSS y JS para el visor.
- `build/build.py` — generador estático.
- `output/` — HTML generado. Abrir `output/index.html` en el navegador.
- `memory/indice.md` — log de cambios mantenido por agentes.

## Formato de un artículo

```markdown
---
titulo: Nombre del artículo
tipo: persona            # persona | organizacion | tema | perfil
infobox:
  Campo: Valor
  Otro campo: Valor
categorias: [personas]
ultima_actualizacion: 2026-04-22
fuentes:
  - tipo: correo
    ref: <gmail-message-id>
  - tipo: drive
    ref: https://drive.google.com/...
---

## Sección
Contenido Markdown.

Enlaces internos: [[personas/juan-perez]] o [[alvaro-mur]].
```

## Build

```
python3 secretary/wiki/build/build.py
```

Genera `output/` con un HTML por artículo más `index.html` (portada con búsqueda cliente, artículos recientes, categorías).

Sin dependencias externas: parseo de frontmatter y Markdown hecho a mano con la biblioteca estándar.

## Contrato para rutinas externas

Cualquier agente/rutina que quiera escribir en la wiki debe:

1. Crear o editar un `.md` en la subcarpeta correcta de `articulos/`.
2. Respetar el frontmatter. Actualizar `ultima_actualizacion` (YYYY-MM-DD) y añadir entradas a `fuentes`.
3. Usar `[[slug]]` o `[[categoria/slug]]` para enlaces internos; el builder los resuelve.
4. Añadir una línea a `memory/indice.md` con fecha + resumen del cambio.
5. Ejecutar `build.py` (o dejarlo a una tarea de rebuild).

No inventar datos: los campos desconocidos se dejan como `[por rellenar]`.
