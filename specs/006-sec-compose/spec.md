<!-- claude-generated:dispatch -->
---
id: "006"
slug: sec-compose
layer: L2
status: implementado
last_reviewed: 2026-07-02
implemented:
  - ~/.claude/skills/sec-compose/SKILL.md
---

# Feature 006 — `sec-compose`: destilar fragmento + destinatario → mensaje contextualizado

**Estado:** `implementado v1` — SKILL.md en runtime (el operador aprobó el draft 2026-06-08)
**Origen:** dispatch desde sesión de diseño de la capa de enriquecimiento de la wiki (2026-06-08).
**Decisión de naming relacionada:** `../../decisiones/2026-06-07-naming-skills.md` (instance design log)

## Problema

La familia `sec-*` tiene capa de lectura (`sec-recall`), de escritura (`sec-write`) y de
mantenimiento (`sec-consolidate`). No tiene capa de **salida**.

Cuando el operador quiere compartir un material con alguien, el flujo manual es: recordar de qué
han hablado, releer la última conversación, decidir si arrancar tema nuevo o retomar el hilo,
y redactar en su registro. Hoy `sec-recall` ayuda con el primer paso (qué sé de la persona)
pero deja el resto al humano. El material y el destinatario nunca se combinan en un producto.

Falta el primitivo que haga la **composición**: `(material, destinatario) → mensaje anclado
en el historial de relación`.

## Solución: primitivo `sec-compose`

### Insumos

| Insumo | Obligatorio | Descripción |
|---|---|---|
| `material` | sí | El fragmento/idea/link a compartir. Texto libre o referencia. |
| `destinatario` | sí | Persona de la wiki (`knowledge/wiki/articulos/personas/<slug>.md`). |
| `canal` | no | `whatsapp` \| `correo` \| `generico` (default: `generico` — listo para pegar en cualquier conversación). |
| `tono` | no | Override del registro (default: el natural del operador con esa persona, inferido del historial). |
| `tema` | no | Override explícito del tema a buscar como ancla. Si se omite, el subagente infiere conceptos clave del `material`. |

### Salida

1-2 **borradores en markdown**, listos para copiar. Nunca un envío. Por defecto ofrece dos
variantes:

- **Arranque nuevo** — para una conversación fría ("hey, ¿cómo estás? estaba pensando en…").
- **Continuación** — engancha con la conversación previa más relevante **por tema** ("como te
  decía la otra vez sobre…").

Si el historial no da para una continuación natural, devuelve solo el arranque y lo dice.

### Cómo trabaja (pipeline interno)

1. **Resolver destinatario** → localizar su artículo en la wiki (ruta vía `.secretary.yml`).
2. **Inferir tema** → si no hay `tema` explícito, el subagente extrae los conceptos clave del
   `material` (p. ej. "vector DBs", "embeddings", "RAG"). Si el operador pasó `tema`, usarlo como
   query de búsqueda sin re-inferir.
3. **Recall de relación** → invocar `sec-recall` sobre la persona + escanear
   `extractors/meetings/summaries/` y `extractors/meetings/memory/` (paths vía
   `.secretary.yml`) por conversaciones donde ese tema ya apareció. Incluir el **scan de
   capturas no mergeadas** (PRs `auto-*` abiertos de `reuniones-update`) — mismo patrón que
   `sec-recall` — para no perder reuniones del mismo día aún no en `main`. (Para Greg + vector
   DBs/embeddings: engancha con las sesiones donde hablaron de RAG/agentes.)
4. **Seleccionar ancla** → de las candidatas, elegir la **más temática** (no la más reciente
   por defecto). Nombrar la elegida en el reporte — fuente, fecha y por qué encaja — para que
   el operador la corrija si prefiere otra.
5. **Componer** → redactar las variantes en el registro del operador (tuteo peruano, nunca
   voseo; ver `feedback_tuteo_peruano`), adaptadas al `canal`.
6. **Reportar** → devolver los borradores + la línea de ancla usada. **No escribir memoria**
   (ver DD-5).

### Aislamiento (requisito explícito)

`sec-compose` debe correr **sin ensuciar el contexto de la sesión que lo invoca**. La lectura
de wiki + reuniones es voluminosa y no debe quedar en el hilo principal. Opciones (DD-1):

- **(a) Subagente** vía el Tool `Agent`: la sesión lanza un subagente que hace todo el
  pipeline y devuelve solo los borradores. Simple, sin estado persistente, el contexto pesado
  muere con el subagente. **Recomendado.**
- **(b) Sesión hermana** vía `dispatch`/`send_message`: más pesado, pensado para trabajo
  continuable; aquí no hace falta continuidad.

El skill `sec-compose` (lean) describe la misión; el invocador (o el propio skill) dispara el
subagente. El subagente NO necesita los skills de escritura — es read-only + redacción.

### Persistencia de memoria (requisito explícito)

`sec-compose` es primitivo de **salida pura**: no escribe wiki, no deja `sec:pending`, no
actualiza `*/memory/`. Registrar "el operador le compartió X" sería un envío no confirmado
persistido como hecho. Solo si el operador confirma que mandó el mensaje puede una sesión aparte
invocar `sec-write` — fuera del pipeline de compose.

### Espejo MD (borrador en disco)

Cuando el entregable es un archivo (p. ej. `canal: correo` de proyecto), el skill persiste un
espejo markdown antes de devolver los borradores en chat — `borrador-correo-<slug>-YYYY-MM-DD.md`
según `canon/operational/sorting/sistemas-ordenamiento.md` §6.1, no en `extractors/mail/drafts/` para trabajo
de proyecto. Plantilla: `templates/borrador-correo-proyecto.md`.

### Handoff a Gmail

Para borrador en hilo de Gmail → `sec-mail` con `intent=draft`; aplica conversión MD→plain,
firma desde `mail.settings` y revisión de typos antes de `gog gmail drafts create`.

## User scenarios

**US-1 (el caso gatillo).** El operador, en una sesión de diseño, tiene un párrafo crítico sobre
vector DBs. Invoca `sec-compose` con el párrafo y destinatario = Greg. El subagente lee el
artículo de Greg, encuentra la reunión donde hablaron de RAG/agentes/su proyecto de data
analytics, y devuelve dos borradores (arranque + continuación). La sesión de diseño sigue
intacta; el operador copia el que prefiera a WhatsApp.

**US-2 (sin ancla).** El operador quiere compartir algo con un contacto con el que no hay
conversación previa sobre el tema. `sec-compose` devuelve solo la variante de arranque nuevo
y avisa: "no encontré conversación previa sobre esto; te dejo solo el arranque".

**US-3 (canal correo).** Mismo material, destinatario que el operador trata por correo. El borrador
sale con saludo/cierre de correo en vez de tono chat.

## Success criteria

- [x] `sec-compose` acepta `(material, destinatario)` y resuelve el artículo de la persona.
- [x] Infiere conceptos clave del `material` para buscar ancla (o usa `tema` explícito si
      el operador lo pasó).
- [x] Encuentra (si existe) la conversación previa relevante por **tema**, no solo por
      recencia; elige la más temática entre candidatas; incluye scan de PRs `auto-*` abiertos.
- [x] **No persiste memoria** por defecto — read-only sobre fuentes + redacción de borradores.
- [x] Devuelve 1-2 borradores en el registro del operador (tuteo peruano verificado).
- [x] **Nunca** envía: la salida es siempre texto para copiar (respeta `feedback_envios_explicitos`).
- [x] Corre aislado: el contexto de la sesión invocadora no se llena con la lectura de fuentes.
- [x] Reporta la "ancla usada" (fuente, fecha, razón) para que el operador la pueda corregir.

## Implementación — skills involucrados

| Skill | Rol | Estado |
|---|---|---|
| `sec-compose` | primitivo de salida: orquesta el subagente, define insumos/salida | ✅ SKILL.md en `~/.claude/skills/sec-compose/` (v1) |
| `sec-recall` | capa de lectura reusada por el subagente (qué sé del destinatario) | existe — sin cambios |
| `Agent` (tool) | mecanismo de aislamiento (subagente read-only) | nativo |

Split core/instance: la **lógica reusable** de `sec-compose` (cómo busca ancla, cómo compone)
es engine → `secretary-core`. El **contenido** (wiki, reuniones, registro del operador) es
instancia. El skill no hardcodea rutas ni nombra a el operador — resuelve fuentes lógicas vía
`.secretary.yml`, igual que el resto de la familia.

## Decisiones de diseño

Migradas a [`research.md`](research.md) (DD-1…DD-5: mecanismo de aislamiento, ubicación en la
familia `sec-*`, origen del tema, selección de ancla, persistencia) — formato Spec Kit
decisión/rationale/alternativa descartada. Ver también [`plan.md`](plan.md) para contexto
técnico y el gate de constitución.

## Relación con la capa de enriquecimiento

Este primitivo es independiente de la "capa de enriquecimiento" (tags dinámicos, grafo de
entidades, embeddings) que se discutía en la sesión origen, pero se beneficia de ella: un
grafo de wikilinks y embeddings haría la **búsqueda de ancla** (paso 2-3) mucho más precisa
que el grep temático. `sec-compose` se puede implementar hoy con grep/recall, y mejorar
cuando exista la capa.

---
🤖 _Generado por Claude Code — dispatch · 2026-06-08_
