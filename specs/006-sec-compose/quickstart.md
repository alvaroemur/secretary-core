# Quickstart: sec-compose

Valida el caso gatillo (US-1 en [spec.md](spec.md)) — el escenario que motivó todo el diseño.

## Prerrequisitos

- Un destinatario con artículo real en `knowledge/wiki/articulos/personas/<slug>.md`.
- Al menos una reunión o correo previo con ese destinatario indexado en
  `extractors/meetings/summaries/` o `extractors/meetings/memory/` (paths resueltos vía
  `.secretary.yml`), sobre un tema reconocible.

## Ejecutar

En una sesión de Claude Code, dentro de `$SECRETARY_INSTANCE`:

```
/sec-compose material="<párrafo o idea a compartir>" destinatario="<slug-persona>"
```

(o el equivalente invocando el skill directamente con esos insumos — `canal`, `tono`, `tema`
son opcionales).

## Resultado esperado

1. La sesión invocadora **no** se llena con el contenido de wiki/reuniones leído — solo recibe
   el resultado final del subagente.
2. Vuelven 1-2 borradores en markdown, en el registro del operador (tuteo peruano, nunca voseo).
3. El reporte nombra la "ancla usada" — fuente, fecha, por qué se eligió esa conversación y no
   otra — para poder corregirla si no es la mejor candidata.
4. Si no hay conversación previa relevante sobre el tema, vuelve solo la variante de arranque
   nuevo y lo dice explícitamente (no inventa una continuación falsa).
5. **Nada se escribe** en wiki ni en `*/memory/` — repetir la invocación no dejaría rastro salvo
   que el operador pida explícitamente `sec-write` después de confirmar que mandó el mensaje.

## Caso de prueba manual usado en el diseño original (2026-06-08)

Material: párrafo crítico sobre vector DBs/embeddings. Destinatario: Greg (`personas/greg-minaya`).
Resultado esperado: el subagente encuentra la reunión donde hablaron de RAG/agentes/su proyecto
de data analytics y ofrece arranque + continuación anclada en esa conversación.
