---
name: whatsapp-monitor
description: Procesa chats de WhatsApp aprobados (whitelist) 1×/día (19:00), hace triage de la actividad reciente, y entrega los cambios (memory/, summaries/, state.md) como PR para revisión. El state.md sirve de cuerpo del PR.
---

# whatsapp-monitor — Orquestador de procesamiento de WhatsApp

Esta rutina captura mensajes de WhatsApp vía Baileys, hace triage de toda la actividad nueva (whitelist + no-whitelist), procesa profundamente sólo los chats aprobados, y reporta a Álvaro lo demás para que decida.

## Split core / instance (importante)

Desde 2026-05-18 el repo se separó en:

- **Engine (público, reutilizable)**: `~/Dev/secretary-core/` — contiene los scripts de Baileys en `whatsapp/src/` (`fetch.ts`, `login.ts`, `dump.ts`, etc.) y NO contiene datos.
- **Instance (privado, datos reales)**: `~/.secretary/` — contiene `extractors/whatsapp/{auth,inbox,memory,summaries,media}`, `policy.md` y `state.md`. La rutina opera sobre esta instancia.

La instancia declara su layout en `~/.secretary/.secretary.yml` (sección `paths.whatsapp`). Los scripts del core deben resolver paths vía la env var `SECRETARY_INSTANCE` (apuntando a la instancia). El SKILL exporta esa variable antes de invocar cualquier script.

## W. WORKTREE AISLADO (hacer ANTES que nada)

Esta corrida NO escribe los archivos versionados en la copia principal. Trabaja en un worktree efímero desde `origin/main` y al final abre un PR que sirve de reporte.

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=whatsapp
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
git worktree add -b "$BRANCH" "$WT" origin/main
echo "WT=$WT  BRANCH=$BRANCH"
```

**Mapa de rutas (importante, hay dos destinos):**

- **Estado compartido NO versionado** — `extractors/whatsapp/auth/`, `extractors/whatsapp/inbox/`, `extractors/whatsapp/media/` están en `.gitignore` y NO existen en el worktree. El fetch (Fase 1) sigue corriendo con `SECRETARY_INSTANCE=~/.secretary` (la instancia **principal**), y los subagentes **leen** los mensajes desde `~/.secretary/extractors/whatsapp/inbox/` (principal). No intentes leer inbox/auth/media desde `$WT`.
- **Salidas versionadas** — `extractors/whatsapp/memory/`, `extractors/whatsapp/summaries/`, `extractors/whatsapp/state.md` SÍ van al PR: **escríbelas en `$WT/extractors/whatsapp/...`**. El bookkeeping (`_procesados.jsonl`) y el `_glosario.md` se leen/escriben en `$WT/extractors/whatsapp/memory/` (checkout fresco de `main`).

Regla de interpretación: donde el documento diga `secretary/extractors/whatsapp/{memory,summaries,state.md}` (o su forma absoluta), léelo como `$WT/extractors/whatsapp/...`. Donde diga `inbox/`, `auth/`, `media/`, se queda en `~/.secretary/extractors/whatsapp/...`.

> Operación: `_procesados.jsonl` vive en el PR, no en `main`. Mergea los PRs a diario; si se acumulan sin merge, la siguiente corrida parte de `main` y puede reprocesar chats (duplicación de resúmenes).

## Contrato estricto — frontera de escritura

**Salidas versionadas sólo en `$WT/extractors/whatsapp/{memory,summaries,state.md}`**; estado compartido (`inbox/auth/media`) en `~/.secretary/extractors/whatsapp/`. Nunca toca otras carpetas de la instancia (`wiki/`, `mail/`, `meetings/`, `loops/job-search/`) ni nada bajo `secretary-core/`. Las decisiones sobre qué llega a la wiki las toma `wiki-update` consumiendo los archivos en `secretary/extractors/whatsapp/memory/`.

## Estructura de archivos

```
~/.secretary/extractors/whatsapp/   ← instancia (esta rutina escribe aquí)
├── auth/                       ← credenciales Baileys (nunca borrar)
├── inbox/
│   ├── chats/                  ← un .md por chat con todos los mensajes capturados
│   ├── contacts.json           ← jid → nombre
│   └── .last-fetch             ← timestamp del último fetch
├── memory/
│   ├── chats.md                ← registro append-only por chat-período procesado
│   ├── personas.md             ← personas detectadas (pendiente_wiki: false default si nuevas)
│   ├── organizaciones.md       ← orgs detectadas
│   ├── entidades.md            ← temas/proyectos
│   ├── acciones.md             ← acciones nuevas + updates sobre existentes
│   ├── _glosario.md            ← ground truth de Álvaro (NO se modifica)
│   └── _procesados.jsonl       ← bookkeeping: last_processed_ts por chat-slug
├── summaries/
│   └── YYYY-MM-DD-<slug>.md    ← un archivo por chat-período (lectura para Álvaro)
├── media/                      ← audios .ogg descargados por fetch
├── policy.md                   ← whitelist + bloqueados + reglas
└── state.md                    ← reporte de la última corrida (incluye triage)

~/Dev/secretary-core/whatsapp/src/   ← engine (sólo lectura desde la rutina)
├── fetch.ts, login.ts, dump.ts, send.ts, transcribe.ts, ...
```

## Herramientas disponibles

- **Baileys CLI** (desde el core, apuntando a la instancia):
  ```bash
  cd ~/Dev/secretary-core/whatsapp/src \
    && SECRETARY_INSTANCE=~/.secretary LISTEN_SECONDS=120 npx tsx fetch.ts
  ```
- **Bash, Read, Write, Edit**: archivos locales (siempre rutas absolutas o relativas a `~/.secretary/extractors/whatsapp/`)
- **Agent tool**: subagentes en paralelo (`subagent_type: general-purpose`)

> Si `fetch.ts` aún no honra `SECRETARY_INSTANCE` (paths atados a `__dirname`), la corrida fallará en silencio: AUTH_DIR resolverá a `secretary-core/extractors/whatsapp/auth/` (vacío). En ese caso reportar en `state.md` y NO intentar parchear `fetch.ts` (vive fuera del contrato de frontera; lo arregla Álvaro en el repo del core).

## Fases de ejecución

### Fase 0 — Bootstrap

Todas las rutas son relativas a `~/.secretary/` (la instancia).

1. Leer `extractors/whatsapp/policy.md` → cargar:
   - `whitelist`: lista de slugs/JIDs por categoría (proyecto, radar, persona)
   - `bloqueados`: slugs/JIDs a ignorar siempre
2. Leer `extractors/whatsapp/memory/_procesados.jsonl` (puede no existir → vacío). Construir índice: `chat_slug → last_processed_ts`
3. Leer `extractors/whatsapp/memory/_glosario.md` → ground truth (se pasa a subagentes)
4. Leer `extractors/whatsapp/memory/acciones.md` → acciones abiertas para detección de cierres/updates
5. Leer `extractors/whatsapp/inbox/contacts.json` → diccionario JID → nombre
6. Verificar `extractors/whatsapp/auth/` no vacío. Si vacío → abortar con mensaje "Ejecutar `cd ~/Dev/secretary-core/whatsapp/src && SECRETARY_INSTANCE=~/.secretary npx tsx login.ts` manualmente"

### Fase 1 — Scan (captura de mensajes)

1. Ejecutar:
   ```bash
   cd ~/Dev/secretary-core/whatsapp/src \
     && SECRETARY_INSTANCE=~/.secretary LISTEN_SECONDS=120 npx tsx fetch.ts
   ```
2. Leer `~/.secretary/extractors/whatsapp/inbox/.last-fetch` para confirmar `messagesCaptured`, `chatsUpdated`, `newContacts`
3. Si 0 mensajes y 0 chats → continuar a Fase 5 (sólo actualizar estado con "sin actividad")

### Fase 2 — Triage de actividad (CRÍTICO — todo chat con mensajes nuevos pasa por aquí)

Para cada chat con mensajes nuevos desde `last_processed_ts`:

1. **Si está en `bloqueados`**: ignorar silenciosamente. NO va al reporte.
2. **Si está en `whitelist`**: marcar como `categoria: proyecto | radar | persona` (según sección de `policy.md`) y agregar a la cola de procesamiento profundo (Fase 3).
3. **Si NO está en whitelist NI bloqueados**: clasificar por señal:
   - **Señal alta** (`triage: candidato_whitelist`): cumple ≥1 de:
     - >5 mensajes nuevos con texto real
     - Menciona ≥1 entidad existente en wiki (persona, org, tema)
     - Contacto nuevo en chat 1-on-1 (primera vez que escribe)
     - Mensaje con palabra clave de acción/oportunidad: "deadline", "convocatoria", "fondo", "propuesta", "reunión", "factura", "pago", URLs a docs/forms importantes
   - **Señal media** (`triage: actividad_menor`): 1-3 mensajes con contenido textual mínimo (scheduling, "ok", "gracias")
   - **Señal baja** (`triage: ignorable`): solo `[audio]`/`[imagen]`/`[video]`/`[sticker]` sin caption, o solo emojis/reacciones
4. Identificar **contactos nuevos** (que aparecen por primera vez): primer mensaje propio o pushName nuevo en `contacts.json`.
5. Identificar **chats reactivados de la whitelist** (>30 días sin actividad y ahora con mensajes): se procesan normal en Fase 3, pero se anotan en el reporte para que Álvaro lo note.

El triage de chats no-whitelisted se delega a un subagente "triage" único (no a un subagente por chat — sería caro). El subagente triage recibe el listado de chats con mensajes nuevos + las primeras N líneas de cada uno y devuelve la clasificación.

### Fase 3 — Dispatch de subagentes (procesamiento profundo)

Lanzar subagentes en paralelo (un único mensaje con múltiples Agent tool uses):

#### Tipos de subagentes

- **Subagente proyecto/persona** (uno por chat de la whitelist): genera resumen humano + extrae personas/orgs/entidades/acciones
- **Subagente radar consolidado** (uno solo, agrupa todos los chats radar de la whitelist): genera digest unificado + extrae sólo *acciones* relevantes
- **Subagente triage** (uno solo, agrupa todos los chats no-whitelisted con mensajes nuevos): clasifica por señal y devuelve 1-línea por cada uno

#### Contexto que el orquestador prepara antes de Fase 3 (una sola vez)

- Listar `secretary/knowledge/wiki/articulos/personas/`, `organizaciones/`, `temas/` → 3 listas de slugs existentes
- Leer `secretary/knowledge/wiki/articulos/alvaro-mur.md` (sólo lectura, contexto de quién es Álvaro)
- Leer `extractors/whatsapp/memory/_glosario.md` (literal)
- Leer `extractors/whatsapp/memory/acciones.md` filtrando items con estado abierto

Estos contenidos se incluyen literalmente en el prompt de cada subagente.

#### Reglas de validación que los subagentes DEBEN seguir (gate anti-alucinación)

1. **Default `pendiente_wiki: false` para entidades nuevas.** Personas/orgs/temas que NO existan en wiki → `pendiente_wiki: false`. Excepción: si el glosario las menciona explícitamente → `pendiente_wiki: true`.
2. **Enriquecimientos a entidades existentes**: pueden entrar con `pendiente_wiki: true` (slug ya validado).
3. **No inferir apellidos/identidades** del contexto. Si un mensaje dice "Jorge" sin apellido y el glosario no aclara, usar "Jorge (apellido por confirmar)".
4. **Mensajes con `**?**` (remitente desconocido)**: NO atribuir a ninguna persona. Anotar en el resumen como "remitente no identificado" si la info es importante.
5. **Si el glosario contradice la conversación**: glosario gana. Aplicar corrección + nota `<!-- glosario aplicó corrección: <qué> -->`.
6. **Audios `[audio]` sin transcripción**: anotar en el resumen pero no inventar contenido.

#### Prompt — Subagente proyecto / persona (template)

```
Eres un subagente que procesa **un solo chat de WhatsApp** de Álvaro Mur. Generas:
1. Un archivo de resumen Markdown. El orquestador te pasará la ruta absoluta completa en el campo
   `resumen_path` — úsala tal cual. **Nunca construyas rutas que empiecen con `secretary/`**.
2. Un JSON con items para que el orquestador los consolide en `memory/`

NO escribes en `wiki/` de la instancia. NO modificas `memory/*.md` directamente — sólo devuelves JSON.

## Datos del chat
- categoria: proyecto | persona
- chat_name, chat_slug, jid
- mensajes_a_procesar: [<lista de líneas con timestamp del delta>]
- ultima_fecha_procesada: <timestamp anterior>

## Contexto wiki (sólo lectura)
- Personas existentes: [<slugs>]
- Orgs existentes: [<slugs>]
- Temas existentes: [<slugs>]
- Glosario: <literal>
- Acciones abiertas: [<items>]

## Tu output

### 1. Archivo resumen (escribir directamente)
Frontmatter + secciones: Resumen, Personas mencionadas, Organizaciones, Acciones o compromisos, Temas clave.

### 2. JSON estructurado (devolver al orquestador)
{
  "chat_slug": "...",
  "categoria": "proyecto" | "persona",
  "ultima_fecha_procesada": "...",
  "resumen_path": "...",
  "personas": [{ "nombre", "ya_en_wiki", "slug_existente", "contexto", "pendiente_wiki", "duda" }],
  "organizaciones": [...],
  "entidades": [...],
  "acciones_nuevas": [{ "responsable", "accion", "deadline", "contexto", "pendiente_wiki" }],
  "acciones_updates": [{ "acc_id", "estado_nuevo", "evidencia", "deadline_nuevo" }]
}
```

#### Prompt — Subagente radar consolidado (template)

Similar al anterior, pero:
- Procesa varios chats radar a la vez
- Genera UN solo `summaries/<fecha>-radar-digest.md`
- En el JSON: SOLO `acciones_nuevas` (no devuelve personas/orgs/entidades de radar)
- Acciones de radar entran a `memory/acciones.md` con `pendiente_wiki: false` (gate)

#### Prompt — Subagente triage (template)

```
Eres un subagente que clasifica la actividad reciente de chats de WhatsApp NO incluidos en la whitelist de Álvaro. NO genera resúmenes profundos ni extrae entidades. Solo clasifica por señal y produce una línea de descripción por chat.

NO escribes archivos. Devuelves SÓLO un JSON.

## Datos
- chats_a_clasificar: [
    {
      "chat_slug": "...",
      "chat_name": "...",
      "tipo": "grupo" | "1on1",
      "msgs_nuevos": <int>,
      "primeras_lineas": [<las primeras 30 líneas del delta nuevo>]
    },
    ...
  ]

## Contexto wiki (sólo lectura)
- Personas existentes: [<slugs>] ← si una de estas aparece mencionada, marcar señal alta
- Orgs existentes: [<slugs>]
- Temas existentes: [<slugs>]

## Reglas de clasificación

- **señal_alta**: ≥5 msgs con texto real, o menciona entidad de wiki, o contacto nuevo, o tiene palabra clave de acción/oportunidad ("deadline", "convocatoria", "fondo", "propuesta", "reunión", "factura", "pago", URLs a docs)
- **señal_media**: 1-3 msgs con contenido textual mínimo (scheduling, "ok", "gracias", confirmaciones)
- **señal_baja**: solo media sin caption, solo emojis/reacciones, sin texto sustantivo

## Output JSON

{
  "candidatos_whitelist": [
    { "chat_slug": "...", "chat_name": "...", "msgs": <int>, "razon": "menciona [[organizaciones/aliantza]] y comparte URL a propuesta", "muestra": "<1-2 frases del contenido>" }
  ],
  "actividad_menor": [
    { "chat_slug": "...", "chat_name": "...", "msgs": <int>, "muestra": "scheduling, sin contenido sustantivo" }
  ],
  "ignorables": [
    { "chat_slug": "...", "chat_name": "...", "msgs": <int>, "muestra": "todos audios sin transcribir" }
  ],
  "contactos_nuevos": [
    { "jid": "...", "nombre_o_pushname": "...", "primer_mensaje": "..." }
  ]
}
```

### Fase 4 — Consolidación

El orquestador recibe los JSONs de los subagentes:

#### De subagentes proyecto/persona y radar:
1. Append a `memory/personas.md`, `organizaciones.md`, `entidades.md`, `acciones.md` con los items nuevos (formato definido en cada archivo)
2. Append a `memory/chats.md` una sección por chat-período procesado
3. Append a `memory/_procesados.jsonl` un objeto por chat con `last_processed_ts`, `resumen_path`, `processed_at`
4. Para `acciones_updates`: buscar el `acc-id` en `memory/acciones.md` y agregar bloque `## acc-... [update]`

#### Del subagente triage:
NO se escribe en `memory/`. La info se consume sólo para el reporte en `state.md` (Fase 5).

### Fase 5 — Reporte en state.md

Sobreescribir `extractors/whatsapp/state.md` con la siguiente estructura:

```markdown
# Estado — WhatsApp Monitor

## Última corrida
- fecha: <timestamp ISO>
- mensajes_capturados: <int>
- chats_con_actividad: <int>
- contactos_nuevos: <int>
- política: whitelist estricta + triage activo

## Procesados según whitelist (N memos generados)

### Proyectos
- `summaries/YYYY-MM-DD-<slug>.md` — <1-línea>
  - acciones nuevas: <acc-ids>

### Personas
- `summaries/YYYY-MM-DD-<slug>.md` — <1-línea>

### Radar
- `summaries/YYYY-MM-DD-radar-digest.md` — consolida <N chats>
  - acciones para considerar: <acc-ids>

## 🔍 Candidatos para whitelist (revisar y decidir)

Chats fuera del whitelist con señal alta esta corrida:

- **chat-foo** (12 msgs) — _menciona [[organizaciones/aliantza]] y comparte URL a propuesta_
  > "Sample del contenido relevante..."
  - Acciones sugeridas: agregar a `policy.md` como `radar` / agregar como `proyecto` / bloquear / ignorar

- **chat-bar** (8 msgs) — _conversación nueva con contexto profesional_
  > "..."
  - Acciones sugeridas: ...

## Actividad menor (no requiere acción)

<lista de chats con señal media — 1 línea cada uno>

## Contactos nuevos detectados

- **<nombre o pushName>** (`<jid>`) — primer mensaje: _"<sample>"_
  - Acciones sugeridas: agregar a whitelist / a glosario / ignorar

## Chats reactivados de la whitelist

<lista de chats whitelisted que estuvieron >30 días inactivos y ahora reanudaron — procesados normalmente, sólo se anotan>

## Estadísticas globales
- Total mensajes nuevos: <int>
- Total chats con actividad: <int>
  - Whitelist: <int>/21 con actividad
  - Candidatos: <int>
  - Actividad menor: <int>
  - Ignorables: <int>
  - Bloqueados (silenciados): <int>

## Próxima corrida
- <timestamp>
```

### Fase 6 — Cierre: Commit + Pull Request (este PR es el reporte)

**Firma:** `state.md` y el body del PR llevan marca/footer vía `sec-signature.sh whatsapp-monitor` (`_firma.md`).

El `state.md` que escribiste en Fase 5 es el reporte; úsalo como cuerpo del PR.

```bash
cd "$WT"
if [ -z "$(git status --porcelain)" ]; then
  echo "Sin actividad nueva / sin cambios versionados — no se abre PR."
  cd "$REPO" && git worktree remove "$WT" --force && git branch -D "$BRANCH" 2>/dev/null || true
else
  git add -A
  git commit -m "chore(whatsapp): corrida automática $(date +%Y-%m-%d)"
  git push -u origin "$BRANCH"
  gh label create "hilo:whatsapp" --description "Hilo de trabajo: whatsapp" --color C2E0C6 2>/dev/null || true
  gh pr create --title "chore(whatsapp): corrida automática $(date +%Y-%m-%d)" \
    --label "hilo:whatsapp" --body-file "$WT/extractors/whatsapp/state.md"
  cd "$REPO" && git worktree remove "$WT" --force
fi
```

- Si `gh pr create` falla, no revertir: la rama ya está pusheada; reporta el error.
- Devuelve al final la **URL del PR**.

## Decisiones que Álvaro toma a partir del reporte

Cuando lee `state.md`, decide manualmente:

1. **Agregar chat al whitelist** → editar `policy.md` (sección Aprobados, en la categoría que corresponda)
2. **Bloquear chat permanentemente** → editar `policy.md` (sección Bloqueados)
3. **Aclarar contacto nuevo** → editar `_glosario.md` con alias/aclaración
4. **Ignorar el reporte** → no hacer nada; la próxima corrida volverá a hacer triage si sigue habiendo actividad

La rutina NO modifica `policy.md` ni `_glosario.md` automáticamente — esas son ediciones humanas.

## Notas importantes

- **Sólo whitelist genera memos profundos**: Triage NO escribe en `memory/` ni en `summaries/`
- **Bloqueados se ignoran silenciosamente**: ni siquiera aparecen en el reporte
- **NUNCA modificar archivos fuera de `~/.secretary/extractors/whatsapp/`** (en particular: no parchear scripts en `secretary-core/whatsapp/src/`)
- **Default `pendiente_wiki: false` para toda entidad nueva**
- Si fetch.ts falla por sesión expirada, reportar y NO reintentar (requiere QR manual)
- Mensajes `[imagen]`/`[audio]`/`[video]`/`[sticker]` sin caption se ignoran del análisis profundo (pero pueden contar para el conteo de actividad menor)
- Si dos corridas seguidas no traen mensajes nuevos, no generar memos vacíos pero sí actualizar `state.md` con "sin actividad nueva"