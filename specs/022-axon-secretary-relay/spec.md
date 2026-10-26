---
id: "022"
slug: axon-secretary-relay
layer: L3
status: rfc-draft
last_reviewed: 2026-07-03
relocated_from: "007-axon-secretary-relay"
relocated_pr: 460
implemented:
  - P1 read bridge — secd GET /context, /objectives, /recall, /health (secretary-core secd/)
  - P1 relay stub — POST /relay con LLM (OpenAI probado; migración Claude pendiente)
  - knowledge/objectives/ seed store + perfil de voz en instancia
  - Axon secretary bridge (`axon` (sibling repo), PR #2 draft)
gaps:
  - POST /capture reescrito contra contrato 015 (P3; scaffold pre-migración en secd)
  - POST /signal → wiki lazy vía sec-write (P3)
  - Relay UI en sidebar Axon — respuestas sugeridas (P2)
  - Ciclo de vida secd — login item / runtime Secretary
  - Jubilación formal Baileys (contract.yaml retired, no pausado)
  - P4 modo escucha + playbooks + tier-notice
  - docs operativos en `axon` (sibling repo) (enlace al RFC, no copia del spec)
---

<!-- claude-generated:sesion -->
# Feature 022 — Axon × Secretary: puente de contexto y relay de objetivos

**Estado:** `RFC — draft` (sesión de diseño 2026-06-10 · pivote local-first 2026-07-02 · **reubicado L3 022** 2026-07-03 PR [#460](https://github.com/<instance-repo>/pull/460))
**Origen:** sesión interactiva. El operador quiere realinear Axon (su interfaz de lectura de
WhatsApp) a Secretary, para operar un chat con el contexto completo de su sistema y un agente
de relay que sugiera objetivos y respuestas.
**Actualización 2026-07-02:** el proyecto Supabase de Axon dejó de resolver (NXDOMAIN) y Baileys
lleva desvinculado desde 2026-05-20 (`extractors/whatsapp/auth/` ya no existe). Ambos hechos no
cambian las decisiones D1/D2 —ya apuntaban a `secd` local-first y a Axon como captura canónica—
pero las vuelven **forzosas, no preferidas**: hoy Axon no tiene ningún backend de persistencia.
Ver Problema y D1/D2 para el detalle; el resto del RFC (piezas, fases, riesgos) queda vigente,
con ajustes de prioridad y de formato de escritura marcados inline.
**Repos afectados:** `axon` (sibling repo) (extensión Chrome),
`secretary-core` (engine), `$SECRETARY_INSTANCE` (instancia/datos).

---

## Problema

Hoy existen **dos sistemas de WhatsApp paralelos que no se hablan**:

1. **Axon** — extensión de Chrome (MV3, JS puro) que lee WhatsApp Web / LinkedIn scrapeando
   el DOM. Usa OpenAI (GPT-4o-mini) para sugerir y refinar respuestas, transcribe audio
   (Whisper) y persiste en Supabase + `chrome.storage`. Tiene ya un mini-agente (sugerencias,
   refinamiento iterativo, resumen con preguntas). **Está totalmente aislado de Secretary**:
   cero referencias a `$SECRETARY_INSTANCE` o a secretary-core.
2. **secretary-core/whatsapp** — captura headless vía Baileys (dispositivo vinculado), corre
   en rutinas y consolida a la wiki. **Lleva 12 corridas con delta 0** (Baileys conecta pero el
   stream llega vacío): la captura programada está rota.

Consecuencias:

- Cuando el operador lee un chat en Axon, **no ve quién es la persona según Secretary** (su artículo
  de wiki, sus organizaciones), ni las **acciones abiertas** con ese contacto, ni el histórico
  consolidado. El agente sugiere respuestas a ciegas, con solo los últimos N mensajes del DOM.
- No hay forma de que una conversación **avance objetivos** más allá del chat mismo: Axon no
  sabe de estrategia, de relaciones de largo plazo, ni de tareas pendientes.
- La doble captura es redundante y, en la práctica, **ninguna alimenta bien a Secretary** (la
  buena —el scrape de Axon— no escribe a `$SECRETARY_INSTANCE`; la que escribe —Baileys— está rota).

Lo que falta es: (a) un **puente** que deje a Axon leer y escribir el contexto de Secretary en
vivo; (b) un **relay** que detecte intención y proponga objetivos jerárquicos que guíen las
respuestas; (c) **una sola captura** que funcione y alimente a Secretary.

**Actualización 2026-07-02 — el statu quo ya no existe.** Desde la sesión de diseño original,
los dos sistemas paralelos del punto (1)-(2) se degradaron más:

- El proyecto Supabase de Axon (`wqedbcxitjzfuidjswrb.supabase.co`) **no resuelve** (NXDOMAIN):
  login, historial de conversación para el mini-agente OpenAI, y el WIP de RAG (`schema/*.sql`,
  `services/ragClient.js`) quedaron sin backend. Axon hoy no persiste nada en ningún lado.
- Baileys pasó de "12 corridas secas" a **desvinculado**: `extractors/whatsapp/auth/` ya no
  existe en la instancia; la compuerta de re-vincular está abierta desde ~2026-06-08 sin
  respuesta (43 días sin captura real al momento de esta actualización).

Esto no introduce una decisión nueva —D1 y D2 abajo ya elegían `secd` local-first y Axon como
captura canónica— pero cambia el marco: ya no es "Axon versus Supabase, ¿cuál preferimos?", es
"Axon no tiene persistencia salvo la que construya `secd`". La Pieza 3 (captura, antes P3) pasa
de *cierra el lazo con la memoria de largo plazo* a *es la única memoria que Axon tendrá*.

---

## Decisiones de arquitectura (tomadas en la sesión)

| # | Decisión | Elegido | Descartado |
|---|----------|---------|------------|
| **D1** | Puente Axon ↔ contexto de Secretary | **Daemon local `secd`** (localhost) | Sync a Supabase · Servidor MCP |
| **D2** | Captura de WhatsApp | **Axon (scrape) se vuelve canónico y alimenta a Secretary; se jubila Baileys** | Mantener ambos · Diferir |
| **D3** | Objetivos multinivel | **Primitivo de primera clase en Secretary** (estrategia ↔ acciones) | Locales en Axon/Supabase |

**Por qué `secd` y no Supabase (D1):** Secretary es local-first y privado por doctrina (datos
reales en archivos + git, nunca público). Espejar wiki/memory en Supabase subiría contexto
privado a un tercero permanentemente. Un daemon en `localhost` mantiene `$SECRETARY_INSTANCE` como
fuente de verdad, da un API que **también sirven las rutinas**, y no expone nada a la nube.
*(Actualización 2026-07-02: el proyecto Supabase que hubiera sido la alternativa ya no existe
—NXDOMAIN—, así que esta decisión pasó de preferencia arquitectónica a única opción viable.)*

**Por qué jubilar Baileys (D2):** el scrape de Axon ya funciona; Baileys lleva 12 corridas
secas. Mantener dos capturas duplica esfuerzo y deja la mala como "fuente". Una sola captura
—la que anda— reduce superficie y arregla de paso la captura rota. *(Actualización 2026-07-02:
Baileys ya no está en estado degradado sino desvinculado —`auth/` ausente—; jubilarlo formalmente
cierra una compuerta abierta hace 43 días en vez de posponerla.)*

**Por qué objetivos en Secretary (D3):** los niveles altos que pidel operador se anclan a
"estrategia de empresa o personal" — eso es memoria de largo plazo, no estado de un chat. Si
viven en Axon se pierden entre conversaciones y no se alinean a la estrategia real.

---

## Arquitectura objetivo

```
┌─────────────────────────── Chrome ───────────────────────────┐
│  WhatsApp Web  ←scrape→  Axon (extensión MV3)                 │
│                            │  sidebar: contexto + relay        │
│                            │                                   │
└────────────────────────────┼──────────────────────────────────┘
                             │ HTTP/WS localhost (token)
                             ▼
              ┌──────────────────────────────┐
              │  secd  (daemon local)         │  ← vive en secretary-core
              │  - resolver entidad por chat  │
              │  - servir contexto (read)     │
              │  - aceptar señales (write)    │
              │  - store de objetivos         │
              │  - relay (razonamiento LLM)   │
              └──────────────┬───────────────┘
                             │ lee/escribe archivos
                             ▼
              ┌────────────────────────────────────────┐
              │  $SECRETARY_INSTANCE (instancia)             │
              │  knowledge/wiki/articulos/            │
              │  knowledge/objectives/ ★              │  ★ = nuevo
              │  extractors/whatsapp/memory/          │
              │    chats.md · acciones.md (captura) ● │  ● = escrito por secd/capture
              │  extractors/whatsapp/summaries/       │
              └────────────────────────────────────────┘
```

### Pieza 1 — `secd`, el daemon local de Secretary (secretary-core)

Servidor pequeño (Node/TS, junto al módulo whatsapp) que escucha **solo en `127.0.0.1`**,
autenticado por token (en `chrome.storage` de Axon). Resuelve rutas vía `SECRETARY_INSTANCE`
(misma convención que el engine; nunca `__dirname`). Endpoints:

**Lectura**
- `GET /context?chatId=…` → **tarjeta de contexto**: resuelve el chat (teléfono/alias) a la
  entidad de wiki (persona/organización), y devuelve: resumen del artículo, organizaciones
  ligadas, acciones abiertas con ese contacto (`acciones.md`), objetivos activos de la relación,
  y reglas de estilo/voz del operador (memorias de feedback: tuteo neutro, sin voseo, su prosa).
- `GET /objectives?scope=…` → objetivos por nivel/scope (ver Pieza 3).
- `GET /recall?q=…` → búsqueda libre sobre memoria (envuelve el primitivo `sec-recall`).

**Escritura**
- `POST /capture` → persiste la conversación scrapeada **en el formato del contrato de
  extractor** (`_diseño/specs/015-module-contract/`), no como volcado ad-hoc: agrega una sección
  a `extractors/whatsapp/memory/chats.md` (categoria/jid/periodo/mensajes_procesados/temas/
  resumen_path/detectado/`pendiente_wiki: true`), escribe el resumen en
  `extractors/whatsapp/summaries/`, y agrega a `acciones.md` cuando el chat trae una acción
  identificable. `wiki-update` ya sabe leer este formato — es el mismo que usaba
  `whatsapp-monitor` — así que no requiere código nuevo del lado de integración a wiki.
  Reemplaza a Baileys como fuente de este módulo.
- `POST /signal` → registra un hecho durable (→ anotación lazy en wiki vía `sec-write`).
- `POST /objectives` → crea/actualiza/cierra objetivos y tareas.

*(Nota de implementación 2026-07-02: el `secd` actual en `secd/daemon-mvp` ya tiene un scaffold
de `/capture` y `/signal`, pero escribe a rutas pre-migración (`whatsapp/inbox/`,
`whatsapp/memory/relay-signals.md`) en formato JSON/texto libre que `wiki-update` no consume, y
`/signal` deja `pendiente_wiki: false` hardcodeado —nunca se integraría—. Hay que reescribirlos
contra el contrato antes de P3; ver Fases.)*

**Resolución de entidad (clave):** índice `teléfono/alias → entidad de wiki`, construido desde
`correo/memory/personas.md`, `extractors/whatsapp/memory/` y los artículos de
`knowledge/wiki/articulos/personas`. Una referencia-hacia-adelante (contacto sin artículo) se
marca `pendiente_wiki: true`.

**Ciclo de vida:** MV3 tiene service worker efímero → Axon reconecta a `secd` por petición; el
daemon corre como proceso de login del usuario (o lo arranca el runtime de Secretary). *(Riesgo
abierto: cómo se lanza/mantiene `secd` — ver Riesgos.)*

### Pieza 2 — Axon realineado (extensión Chrome)

- **Al abrir un chat:** Axon llama `GET /context?chatId=…` y pinta la **tarjeta de contexto de
  Secretary** en el sidebar (quién es, organizaciones, acciones abiertas, objetivos activos).
  Punto de inyección: `background.js:822` (`buildConversationContext`) — el contexto de Secretary
  se concatena al de los últimos mensajes antes de cualquier llamada al LLM.
- **Captura → Secretary:** el scrape existente (`whatsappContent.js`) además hace `POST /capture`.
  Axon pasa a ser la captura canónica; se retira el extractor Baileys de secretary-core.
- **Relay en el sidebar:** nueva vista (junto a Chat/Resumen/Refine) que corre el ciclo de relay
  (Pieza 4) y muestra objetivos sugeridos/activos + respuestas para copiar.
- **Respuestas siempre copy-paste, nunca auto-envío.** Coherente con la doctrina de Secretary
  ("envíos a terceros requieren OK explícito"). El input de WhatsApp no se auto-rellena en v1.

### Pieza 3 — Objetivos, primitivo nuevo de Secretary

Jerarquía de tres niveles, persistida en `$SECRETARY_INSTANCE/knowledge/objectives/` (markdown + frontmatter,
enlazada con wikilinks a personas/organizaciones):

- **L0 — Estrategia** (empresa / personal): pocos, estables, de largo plazo. Ej.: *"posicionar
  doc2struct en estudios contables"*, *"conseguir rol de director en LATAM"*.
- **L1 — Objetivo de relación / conversación**: por contacto o por hilo, colgado de un L0. Ej.:
  *"cerrar la propuesta ERP con Luna/Ágora"* → cuelga de un L0 de ingresos.
- **L2 — Tareas / movimientos**: concretos y accionables — preguntas que hacer, pedidos, info
  que confirmar o compartir. **Se integran con `acciones.md`** (no duplican el sistema de
  acciones; lo extienden con el vínculo al objetivo).

Cada objetivo: `id`, `nivel`, `parent`, `entidad` (wikilink), `estado` (sugerido/activo/cerrado),
`origen` (quién lo propuso: relay vs el operador). **El relay solo sugiere; el operador confirma** (🚧
compuerta). Un objetivo sugerido no guía respuestas hasta que el operador lo activa.

### Pieza 4 — El relay (corazón de la propuesta)

Bucle, por conversación abierta, corriendo en `secd` (razonamiento) y pintado en Axon:

1. **Observar** — Axon manda mensajes recientes; `secd` añade la tarjeta de contexto + objetivos
   activos.
2. **Detectar intención** — el agente infiere qué está pasando en el chat y qué busca el operador.
3. **Sugerir objetivos** — propone objetivos al nivel que corresponda, colgados hacia arriba de
   un L0 de estrategia. El operador acepta/edita/rechaza (compuerta). Lo aceptado queda activo.
4. **Derivar tareas (L2)** — bajo un objetivo activo, surfacea movimientos concretos (preguntas
   a hacer, info a confirmar).
5. **Sugerir respuestas** — borradores **para copiar/pegar** que avanzan el objetivo/tarea
   activos, **en la voz del operador** (reglas de estilo servidas por `secd`). Cada respuesta se
   anota con *qué objetivo o tarea avanza*.
6. **Capturar resultado** — cuando el operador copia una respuesta o el chat avanza, el relay actualiza
   el estado de tarea/objetivo y escribe hechos durables a Secretary (`POST /signal` → wiki lazy).

**Proveedor LLM:** mover el razonamiento del relay a **Claude (Anthropic)** para alinear voz y
reglas con el resto de Secretary; conservar Whisper para transcripción. *(Decisión secundaria,
recomendada; ver Riesgos para el costo de migración desde GPT-4o-mini.)*

---

## Modelo operativo: captura atendida y modo de escucha

A diferencia de los otros extractores (correo, reuniones, drive) —**silenciosos y desatendidos**,
corren en schedule sin el operador—, Axon es un **conector atendido**: para capturar y, sobre todo,
para **decidir**, tiene que estar encendido y el operador presente. No es un defecto, es el punto:
capturar mensajes en horarios que no puede atender sirve de poco si en el momento no puede
decidir **si responde y qué responde**. El valor de Axon está en la decisión en vivo, no en el
archivo silencioso.

**Consecuencia sobre D2 (captura).** Jubilar Baileys y dejar a Axon como única captura significa
que la memoria de WhatsApp de Secretary pasa a ser **lo que el operador efectivamente atiende**, no
"todo lo que entra". Es un cambio de modelo del extractor: de *completo y silencioso* a *parcial
y atendido*. Se acepta a propósito (hoy, además, Baileys lleva 12 corridas secas: la captura
silenciosa ya no existe en la práctica). El **modo de escucha** es la palanca para las pocas
conversaciones que sí justifican cobertura sin atención plena. *(Alternativa descartada por
ahora: mantener una captura headless delgada solo para completitud de la wiki — reabre D2; queda
como opción futura si la pérdida de cobertura duele.)*

### Tres niveles de presencia

| Nivel | Qué corre | Atención del operador | Ejemplo |
|---|---|---|---|
| **Daemon** | `secd` siempre encendido | ninguna | sirve contexto e índice de entidades |
| **Escucha** | Chrome abierto + conversaciones fijadas con playbook | semi — recibe avisos | "dejo armada la negociación con X" |
| **Activo** | el operador leyendo/respondiendo un chat | plena | conversación en curso |

### Modo de escucha + playbooks

Un **playbook** es un objetivo de conversación (L1) **activado**, con sus tareas (L2) y los
movimientos que el relay tiene preparados — atado a una conversación concreta. Es lo que
convierte los objetivos (Pieza 3) de estáticos en operativos.

Flujo:
1. El operador **fija** una o varias conversaciones en modo escucha y les asocia su playbook (objetivo
   activo + tareas).
2. Con Chrome abierto, Axon mantiene esas conversaciones conectadas; **no requiere** que el operador
   las esté mirando.
3. Cuando entra un mensaje en una conversación fijada, el relay lo corre **contra el playbook**:
   evalúa qué tarea avanza, prepara la respuesta sugerida en la voz del operador, y emite un **aviso
   tier-notice** (👀: "nuevo mensaje en [chat] · playbook [X] · respuesta lista").
4. El operador llega, revisa la sugerencia ya preparada y decide. **Copiar/enviar sigue siendo su
   gesto (🚧 compuerta); nada se envía solo, ni siquiera en escucha.**

Así las conversaciones que importan quedan "armadas": cuando el operador puede atender, el trabajo de
contexto y borrador ya está hecho y alineado al objetivo. Las demás siguen el modo activo normal.

---

## User scenarios

### US-1 — Ver el contexto de Secretary mientras leo un chat (P1)
**Como** El operador
**Quiero** que al abrir un chat de WhatsApp, Axon me muestre quién es esa persona según mi wiki,
sus organizaciones y las acciones que tengo abiertas con ella
**Para** responder con todo el contexto, no solo con los últimos mensajes visibles
**Criterio de aceptación:** al abrir un chat con un contacto que tiene artículo de wiki, el
sidebar muestra resumen de la entidad + acciones abiertas en < 2s; si no tiene artículo, lo
marca como `pendiente_wiki`.

**Por qué P1:** entrega valor solo (el puente de lectura) y es el cimiento de todo lo demás.
**Test independiente:** abrir 3 chats conocidos y verificar que la tarjeta calza con la wiki.

### US-2 — El relay me sugiere objetivos para la conversación (P2)
**Como** El operador
**Quiero** que el agente detecte hacia dónde va la conversación y me proponga objetivos (de
relación y tareas concretas), colgados de mi estrategia
**Para** no perder de vista qué quiero lograr con ese contacto más allá del mensaje de hoy
**Criterio de aceptación:** el relay propone ≥1 objetivo de nivel apropiado con su vínculo a un
L0; el operador puede aceptar/editar/rechazar; lo aceptado queda persistido en `knowledge/objectives/`.

### US-3 — Respuestas sugeridas que avanzan un objetivo (P2)
**Como** El operador
**Quiero** que las respuestas que me sugiere para copiar/pegar estén guiadas por el objetivo
activo y vengan anotadas con qué objetivo/tarea cumplen
**Para** que cada mensaje empuje algo, y en mi voz
**Criterio de aceptación:** con un objetivo activo, cada sugerencia indica el objetivo/tarea que
avanza y respeta las reglas de estilo del operador (tuteo neutro, sin voseo).

### US-4 — La conversación alimenta la memoria de largo plazo (P3)
**Como** El operador
**Quiero** que lo durable que surge en el chat (un hecho nuevo, un acuerdo, un cierre de tarea)
se registre en Secretary
**Para** que la wiki y las acciones queden al día sin que yo lo transcriba
**Criterio de aceptación:** al cerrar una tarea o marcar un hecho, `secd` escribe la señal y
queda como anotación lazy en el artículo correcto; `wiki-update` la integra después.

### US-5 — Una sola captura, que sí alimenta a Secretary (P3)
**Como** El operador
**Quiero** que la captura de Axon (la que funciona) reemplace al extractor Baileys roto y deje
los mensajes donde las rutinas los consumen
**Para** dejar de mantener dos capturas y arreglar la captura programada
**Criterio de aceptación:** los chats leídos en Axon aparecen en
`extractors/whatsapp/memory/chats.md` con el mismo formato que usaba `whatsapp-monitor`
(incluido `pendiente_wiki: true`), y una corrida de `wiki-update` los integra sin tocar su
código; el extractor Baileys queda retirado/documentado como jubilado (`contract.yaml` con
`routine: retired`, no `pausado`).

### US-6 — Dejar una conversación en modo escucha siguiendo su playbook (P4)
**Como** El operador
**Quiero** fijar ciertas conversaciones para que Axon las siga según el playbook que definí
(objetivo + tareas) y me avise con la respuesta ya preparada cuando entre un mensaje
**Para** no tener que estar mirando el chat, pero llegar con el borrador listo y alineado al
objetivo cuando sí puedo atender
**Criterio de aceptación:** al fijar una conversación con un objetivo activo, un mensaje entrante
dispara un aviso tier-notice con la respuesta sugerida lista; el envío sigue requiriendo el gesto
del operador.

### Edge cases
- Contacto sin entidad en la wiki → tarjeta mínima + marca `pendiente_wiki: true`.
- `secd` caído → Axon degrada a su comportamiento actual (solo DOM + OpenAI), sin romperse.
- Chat de grupo (Axon hoy no los soporta) → fuera de alcance v1; documentarlo.
- Conflicto de objetivos (dos activos que tiran distinto) → el relay lo señala, no decide solo.
- Número que mapea a varias entidades → `secd` pide desambiguación, no adivina.

---

## Requisitos funcionales

- **FR-1.** `secd` escucha solo en `127.0.0.1`, autentica por token, resuelve datos vía
  `SECRETARY_INSTANCE`.
- **FR-2.** `GET /context?chatId` resuelve entidad y devuelve tarjeta (entidad + acciones +
  objetivos + reglas de estilo).
- **FR-3.** Axon pinta la tarjeta de contexto en el sidebar al abrir un chat, con fallback a su
  modo actual si `secd` no responde.
- **FR-4.** Store de objetivos en `$SECRETARY_INSTANCE/knowledge/objectives/` con jerarquía L0/L1/L2 y vínculo a
  `acciones.md`; CRUD vía `secd`.
- **FR-5.** El relay sugiere objetivos y respuestas; **toda activación de objetivo y toda
  respuesta requieren acción explícita del operador** (copiar / confirmar). Nada se envía solo.
- **FR-6.** Las respuestas sugeridas obedecen las reglas de estilo del operador servidas por `secd`.
- **FR-7.** `POST /capture` persiste conversaciones en `extractors/whatsapp/memory/` (formato
  del contrato de extractor: `chats.md` + `acciones.md` + `summaries/`, con `pendiente_wiki:
  true`) consumible sin cambios por `wiki-update`; el extractor Baileys se retira formalmente
  (contrato marcado `retired`, no solo `pausado`).
- **FR-8.** `POST /signal` registra hechos durables como anotación lazy de wiki (`sec-write`).
- **FR-9.** Axon permite **fijar conversaciones en modo escucha** con un playbook asociado; un
  mensaje entrante en una fijada corre el relay contra el playbook y emite un aviso tier-notice
  con la respuesta lista. El envío sigue requiriendo el gesto del operador.

---

## Fases (slicing MVP-first)

- **P1 — Puente de lectura.** `secd` + `GET /context` + tarjeta en Axon. Entrega "ver contexto
  de Secretary mientras veo un chat". Independiente y demostrable. **Estado 2026-07-02:**
  implementado — `secd/daemon-mvp` sirve `/context`/`/objectives`/`/health` (397 entidades
  indexadas); Axon lo integra en `secretary/bridge-rebase-main` (PR #2 en `axon`, aún draft).
- **P3 — Captura unificada + write-back.** `POST /capture` (jubila Baileys) + `POST /signal`
  (alimenta wiki), reescritos contra el contrato de extractor (ver Pieza 1). **Reprioridad
  2026-07-02: se adelanta, no espera a P2.** Antes cerraba el lazo con la memoria de largo plazo
  mientras Supabase cubría la persistencia básica; con Supabase muerto, P3 es la única captura
  que Axon tendrá — sin ella no hay memoria de WhatsApp en absoluto, ni siquiera la mala.
- **P2 — Relay + objetivos.** Primitivo de objetivos + ciclo de relay (sugerir objetivos y
  respuestas guiadas). El corazón de la propuesta; puede seguir después de P1+P3.
- **P4 — Modo de escucha + playbooks.** Fijar conversaciones, correr el relay contra el playbook
  ante mensajes entrantes y avisar (tier-notice) con la respuesta lista. Es lo más avanzado:
  depende de objetivos (P2) y de la captura conectada (P3).

---

## Riesgos y preguntas abiertas

- **Arranque de `secd`:** ¿login item, parte del runtime de Secretary, o manual? Sin esto, el
  puente no está disponible cuando el operador navega. *(Decidir antes de P1.)*
- **MV3 + localhost:** la extensión necesita `host_permissions` para `http://localhost:PORT` y
  `secd` debe permitir el origen de la extensión por CORS. Validar viabilidad temprano.
- **MV3 + detección en segundo plano (modo escucha):** el service worker de MV3 es efímero y el
  content script solo vive con la pestaña abierta. Detectar mensajes entrantes en conversaciones
  fijadas sin que el operador las mire requiere mantener la pestaña de WhatsApp Web viva (y, quizá, un
  keep-alive del worker). Riesgo central de P4: validar que la detección sobreviva al ciclo de
  vida de MV3 antes de prometer escucha confiable.
- **Migración LLM (OpenAI → Claude):** reescribir los prompts del relay y el cliente; costo y
  caching. Se puede hacer en P2 sin bloquear P1.
- **Esquema de objetivos vs `acciones.md`:** definir cómo se enlazan sin duplicar el sistema de
  acciones existente. Riesgo de dos fuentes de verdad para "tareas".
- **Privacidad:** `secd` expone wiki/memory por localhost; token obligatorio y bind a loopback.
  Revisar que ninguna página web pueda alcanzarlo.
- **secretary-core es público a futuro:** `secd` va en el engine (inglés, genérico); los datos y
  el índice de entidades quedan en la instancia. No filtrar datos reales al engine.
- **Grupos de WhatsApp:** Axon no los soporta hoy; v1 sigue 1-a-1.
- **Subsistemas de Axon huérfanos por la caída de Supabase (2026-07-02):** el mini-agente
  OpenAI (historial de conversación para `buildConversationContext`), el login/cuenta de usuario
  (`ui/welcome.html`) y el WIP de RAG (`schema/*.sql`, `services/ragClient.js`,
  `services/supabaseClient.js`) dependían de ese proyecto y hoy no tienen backend. **Fuera de
  alcance de este RFC** decidir su destino (recrear Supabase, migrar a `secd`/instancia local, o
  retirarlos); lo único que este RFC resuelve es que la captura de WhatsApp (D2/P3) no depende
  de ninguno de ellos. Requiere una decisión separada antes de que esas pantallas dejen de
  mostrar error.

---

## Fuera de alcance (v1)

- Auto-rellenar / auto-enviar en el input de WhatsApp (sigue siendo copy-paste).
- Soporte de grupos.
- LinkedIn (Axon lo toca, pero el realineamiento a Secretary se acota a WhatsApp en v1).
