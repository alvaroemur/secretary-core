# Política de procesamiento — WhatsApp

## Regla general (whitelist estricta)

**Sólo se procesan los chats explícitamente listados en la whitelist (Aprobados).**
El resto de WhatsApp (~430 chats) se captura en `inbox/chats/` pero NO se generan memos automáticos.

Esto es porque WhatsApp contiene una mezcla de conversaciones personales, profesionales y casuales. Una vez identifiquemos qué vale la pena procesar, se agrega a la whitelist.

## Excepciones

### Contactos nuevos
Si aparece un contacto nuevo (primera vez que escribe) y NO está en la whitelist, se anota en `estado.md` como "Contacto nuevo detectado" para que Álvaro decida si agregarlo o no.

### Pendientes de aprobación
Si un chat de la whitelist estuvo inactivo >30 días y se reactiva, se sigue procesando (ya está aprobado).

## Whitelist — Aprobados

### Grupos de proyectos (procesar siempre — info accionable)
- Norte Compartido (`norte-compartido.md`)
- Mentoría Fundraising (`mentoria-fundraising.md`)
- Proyecto Trazabilidad Loreto 🍃 (`proyecto-trazabilidad-loreto.md`)
- CLab - C&B Contadores (`clab-c-b-contadores.md`)
- Aliantza AI 🤖 (`aliantza-ai.md`) — canal operativo de Aliantza (Grace, Rosarella, Henry); entregas con deadlines reales

### Grupos de radar (monitorear por novedades)
- El Club de la IA (`el-club-de-la-ia.md`)
- Emprendedores Sostenibles (`emprendedores-sostenibles.md`)
- Red de Impacto LATAM (`red-de-impacto-latam.md`)
- Big 4 Alumni - Comunicaciones (`big-4-alumni-comunicaciones.md`)
- SM - LX3 (`sm-lx3.md`)
- Big 4 Alumni (`big-4-alumni.md`) — grupo madre; Ruedas de Negocios y oportunidades comerciales
- Comunidad Fundraising (APF) (`comunidad-fundraising-apf.md`) — convocatorias Kunan, búsquedas de orgs, ecosistema fundraising PE
- Networking Miembros - Red de Impacto LATAM (`networking-miembros-red-de-impacto-latam.md`) — Demo Days, eventos del ecosistema
- Red de Impacto Perú 🇵🇪 (`red-de-impacto-peru.md`) — capítulo Perú, mismo ecosistema

### Personas (1-on-1)
- Arturo Gonzales del Valle (`arturo-gonzales-del-valle.md`)
- Milagros (Aliantza Contadora) — `51935230775` — sin chat aún
- Henry Delgado — `51903540599` — sin chat aún
- Karen Maldonado (`karen-maldonado.md`)
- Rosarella Bendezú (`rosarella-bendezu.md`)
- Rodrigo Salazar (Perú) (`rodrigo-salazar-peru.md`)
- Rodrigo Salazar (Brasil) (`rodrigo-salazar-brasil.md`)
- Rodrigo Pavez — `56982890504` — sin chat aún
- Ernesto Ríos (`ernesto-rios.md`)
- Grace Spray — `51937218921` — sin chat aún
- Fernando Blandón Ramírez (`fernando-blandon-ramirez.md`)
- Julián Tamayo (`julian-tamayo.md`)
- Angélica Vásquez (`angelica-vasquez.md`)
- Boris Gamarra (`boris-gamarra.md`)
- Ross Martínez (`ross-martinez.md`)
- Anggela Peña — `51979838542` — sin chat aún
- Marco Martínez (`marco-martinez.md`)
- Yeraldine Balarezo — `51958879660` — sin chat aún
- Milagros Pérez (Aliantza Contadora) (`milagros-perez.md`) — JID `191775255830718@lid` (variante privacy del `51935230775` ya en glosario; confirmar identidad)
- Jimmy (`jimmy.md`) — lead Inspiro vía Arturo (`80230005866508@lid`)
- Consuempresa / Lester (`consuempresa.md`) — lead Inspiro vía Arturo (`201090771456198@lid`)
- Roger Hidalgo (`roger-hidalgo.md`) — amigo cercano (ChangeLab/Ágora); contexto importante sobre dinámica del comité

## Bloqueados explícitos
<!-- JIDs/nombres que nunca deben procesarse ni aparecer en el reporte de triage -->
(ninguno por ahora)

## Triage de chats fuera del whitelist

La rutina NO genera memos para chats fuera de la whitelist, pero SÍ hace **triage** de su actividad y lista candidatos en `estado.md` para que Álvaro decida.

### Reglas de clasificación del triage (subagente "triage")

- **señal_alta** → aparece en `estado.md` como "candidato para whitelist". Cumple ≥1 de:
  - >5 mensajes nuevos con texto real
  - Menciona ≥1 entidad existente en wiki (persona, org, tema)
  - Contacto nuevo (primera vez que escribe en chat 1-on-1)
  - Mensaje con palabra clave: "deadline", "convocatoria", "fondo", "propuesta", "reunión", "factura", "pago", URLs a docs/forms

- **señal_media** → aparece en `estado.md` como "actividad menor" (1-línea). 1-3 mensajes con contenido textual mínimo (scheduling, "ok", "gracias")

- **señal_baja** → aparece sólo en stats de `estado.md`. Solo media sin caption, solo emojis/reacciones

### Cómo ajustar la rutina

- **Para sumar un chat al procesamiento profundo**: agregar slug/JID a la sección Aprobados (en la categoría que corresponda)
- **Para silenciar un chat permanentemente**: agregar a Bloqueados
- **Para que un contacto nuevo no se reporte como nuevo otra vez**: agregar a `memory/_glosario.md` con sus alias

## Notas operativas

- **Tipo de procesamiento por categoría**:
  - *Proyectos*: extraer acciones, deadlines, decisiones, evidencias para wiki
  - *Radar*: extraer novedades, oportunidades, links interesantes; sin acciones forzadas
  - *Personas*: extraer compromisos, info personal/profesional relevante para sus perfiles en wiki
- **Mensajes con sender desconocido (`?`)**: en el dump histórico, algunos mensajes de grupo no tienen participant. Estos mensajes se incluyen en el análisis de **temas** (de qué se habló) pero se **omiten del análisis de personas** (no se atribuyen a nadie). En los memos aparecen sin autor o como "remitente no identificado"
- **Mensajes en vivo (post-2026-05-08)**: capturados por `fetch.ts` cada 6h, traen `participant` correcto, atribución 100% confiable
