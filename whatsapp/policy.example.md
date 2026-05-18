# Política de procesamiento — WhatsApp

> Plantilla de ejemplo. Reemplaza placeholders `<...>` con los chats,
> grupos y contactos reales del usuario.

## Regla general (whitelist estricta)

**Sólo se procesan los chats explícitamente listados en la whitelist (Aprobados).**
El resto de WhatsApp (potencialmente cientos de chats) se captura en `inbox/chats/` pero NO se generan memos automáticos.

Esto es porque WhatsApp contiene una mezcla de conversaciones personales, profesionales y casuales. Una vez identificado qué vale la pena procesar, se agrega a la whitelist.

## Excepciones

### Contactos nuevos
Si aparece un contacto nuevo (primera vez que escribe) y NO está en la whitelist, se anota en `estado.md` como "Contacto nuevo detectado" para que el usuario decida si agregarlo o no.

### Pendientes de aprobación
Si un chat de la whitelist estuvo inactivo >30 días y se reactiva, se sigue procesando (ya está aprobado).

## Whitelist — Aprobados

> Reemplaza los siguientes ejemplos con los chats reales del usuario.
> Mantener un slug en `kebab-case` por chat para nombrar el archivo de
> memo asociado.

### Grupos de proyectos (procesar siempre — info accionable)
- `<PROJECT_GROUP_1>` (`<project-group-1>.md`)
- `<PROJECT_GROUP_2>` (`<project-group-2>.md`)
- `<PROJECT_GROUP_3>` (`<project-group-3>.md`) — canal operativo; entregas con deadlines reales

### Grupos de radar (monitorear por novedades)
- `<RADAR_GROUP_1>` (`<radar-group-1>.md`)
- `<RADAR_GROUP_2>` (`<radar-group-2>.md`)
- `<RADAR_GROUP_3>` (`<radar-group-3>.md`) — convocatorias, búsquedas de orgs, ecosistema relevante
- `<RADAR_GROUP_4>` (`<radar-group-4>.md`) — Demo Days, eventos del ecosistema

### Personas (1-on-1)
- `<CONTACT_NAME_1>` (`<contact-1>.md`)
- `<CONTACT_NAME_2>` — `<PHONE>` — sin chat aún
- `<CONTACT_NAME_3>` (`<contact-3>.md`)
- `<CONTACT_NAME_4>` (`<contact-4>.md`) — JID `<JID>@lid` (variante privacy del número ya en glosario; confirmar identidad)
- `<CONTACT_NAME_5>` (`<contact-5>.md`) — lead vía `<REFERRER_NAME>` (`<JID>@lid`)
- `<CONTACT_NAME_6>` (`<contact-6>.md`) — relación cercana; contexto importante sobre dinámica del grupo

<!-- TODO: confirm if generic — completar con los contactos reales del usuario -->

## Bloqueados explícitos
<!-- JIDs/nombres que nunca deben procesarse ni aparecer en el reporte de triage -->
(ninguno por ahora)

## Triage de chats fuera del whitelist

La rutina NO genera memos para chats fuera de la whitelist, pero SÍ hace **triage** de su actividad y lista candidatos en `estado.md` para que el usuario decida.

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
- **Mensajes con sender desconocido (`?`)**: en dumps históricos, algunos mensajes de grupo no traen `participant`. Estos mensajes se incluyen en el análisis de **temas** (de qué se habló) pero se **omiten del análisis de personas** (no se atribuyen a nadie). En los memos aparecen sin autor o como "remitente no identificado".
- **Mensajes en vivo (capturados por la rutina de fetch)**: traen `participant` correcto, atribución 100% confiable.
