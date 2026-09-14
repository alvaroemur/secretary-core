---
id: "010"
slug: extractor-skills
layer: L3
status: fase 2 completa
last_reviewed: 2026-07-27
implemented:
  - ~/.claude/skills/sec-mail/SKILL.md
  - ~/.claude/skills/sec-meeting/SKILL.md
  - ~/.claude/skills/sec-drive/SKILL.md
  - ~/.claude/skills/sec-whatsapp/SKILL.md
  - ~/.claude/skills/sec-workspace/SKILL.md
  - secretary/fresh.py
gaps: []
---

# Feature 010 — Arquitectura fresh-first para extractores

**Estado:** `fase 2 completa` — familia `sec-mail`, `sec-meeting`, `sec-drive`, `sec-whatsapp`, `sec-workspace` operativa.  
**Origen:** pedido del operador para operar correo, reuniones, Drive y workspaces con frescura garantizada en sesión interactiva.

## Problema

La familia `sec-*` cubre recall (`sec-recall`), escritura (`sec-write`), composición (`sec-compose`) y pulso (`pulse`), pero **no hay primitivos por medio externo** que garanticen lectura fresca antes de actuar. Hoy:

- Correo: solo la rutina vespertina `revision-correo` barre Gmail; sesiones improvisan `gog` sin contrato.
- Reuniones: Tactiq sube a Drive en minutos; `reuniones-update` corre :00 pero el resumen vive en PR hasta merge.
- Drive: `drive-sync` (Cowork espejos) y `drive-crawler` (índice/propuestas) no están unificados bajo un skill de secretary.
- Workspaces Cowork: `pm-trainee` audita semanalmente; no hay skill invocable en sesión.

Resultado: `sec-recall` puede responder con wiki correcta pero **correo/reunión desactualizados**, o perder captura en ramas `auto-*`.

## Solución

Familia de skills **`sec-<medio>`** con patrón común de tres pasos (doctrina: `extractor-ops.md` (instance canon)):

1. **Paso 0 — Atómico:** leer fuente viva + estado rutina + evidencia en PR `auto-*` sin merge.
2. **Paso 1 — Recall:** `sec-recall` sobre memoria consolidada.
3. **Paso 2 — Acción:** solo si hace falta (draft, compose, write, disparar rutina).

```
                    ┌─────────────────┐
  Usuario ─────────►│ sec-<medio>     │
                    │  Paso 0 fresh   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ sec-recall      │
                    │  Paso 1         │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         sec-compose    sec-write      gog/draft
         (borrador)    (memoria)      (acción)
```

## Árbol de skills

| Skill | Estado | Triggers | Responsabilidad |
|-------|--------|----------|-----------------|
| `sec-mail` | **MVP** | `/sec-mail`, "lee mi correo", "borrador para X", hilo Gmail | Read + draft vía `gog`; firma y cuentas declarativas |
| `sec-meeting` | **MVP** | `/sec-meeting`, "¿ya procesó la reunión?", "transcripción de…" | Freshness + probe Tactiq + pointer a `reuniones-update` |
| `sec-drive` | **MVP** | "qué hay en Drive de…", organizar | Read índice + enlace `drive-sync` + propuestas `drive-crawler` |
| `sec-whatsapp` | **MVP** | "whatsapp con X" | Read inbox/memory; borrador (stream pausado, reportado explícitamente) |
| `sec-workspace` | **MVP** | "ordena Cowork", drift estructural | Auditar `<cowork-root>/` vs `ordenamiento-repo.md` + `pm-trainee` |

Skills existentes que **no duplican** sino que complementan:

| Skill / rutina | Rol |
|----------------|-----|
| `sec-recall` | Paso 1 universal; delega Paso 0 a `sec-<medio>` |
| `sec-compose` | Borradores relacionales (email/WhatsApp); `sec-mail` puede invocarlo tras read |
| `drive-sync` | Escritura en Docs/Sheets espejados (Cowork); ver § Drive |
| `revision-correo` | Batch vespertino; fuente de `estado.md` y memos |
| `reuniones-update` | Batch :00; única escritora de `extractors/meetings/` |
| `drive-crawler` | Batch índice; solo propone organización |
| `pm-trainee` | Batch semanal auditoría carpetas |

## Integración CLI / scripts

| Necesidad | Invocación |
|-----------|------------|
| Frescura por módulo | `secretary fresh mail\|meeting\|drive\|whatsapp\|all [--format json\|table]` |
| Frescura heartbeat | `extractor-freshness.sh` → delega a `secretary fresh all --format markdown` |
| Recall wiki (HTTP) | `secd` → `GET http://127.0.0.1:8910/recall?q=` (ver `secd/README.md`) |
| Recall determinista | `secretary recall <query> --format json` |
| Paths instancia | `secretary config path <key>` · `SECRETARY_INSTANCE=$SECRETARY_INSTANCE` |
| Gmail / Drive / Calendar | `gog` con `--account` según `.secretary.yml` → `accounts` |
| PRs captura | incluidos en `secretary fresh` (`auto_pr`); manual: `gh pr list` + filtro `auto-*` |
| Leer archivo en PR | `git -C $SECRETARY_INSTANCE show origin/<branch>:<path>` |

---

## Sub-spec: `sec-mail`

### Misión

Leer Gmail con datos más recientes que `estado.md` y crear borradores en hilo con firma y cuenta correctas. **Nunca enviar.**

### Inputs declarativos

| Campo | Obligatorio | Valores |
|-------|-------------|---------|
| `intent` | sí | `read` \| `thread` \| `draft` \| `search` |
| `account` | no | `personal` (default) \| `work` → resuelve a email en `.secretary.yml` |
| `query` | según intent | Gmail search syntax |
| `thread_id` | `thread`/`draft` | ID de hilo |
| `to` / `cc` / `bcc` | `draft` | Listas separadas por coma |
| `subject` | `draft` | Asunto (prefijar `Re:` si reply) |
| `body` | `draft` | Cuerpo sin firma (el skill añade bloque firma) |
| `reply_to_message_id` | `draft` en hilo | **Obligatorio** para reply — de `thread get --plain` |
| `tone` | no | `warm` (default) \| `formal` — ver `settings.md` |

### Paso 0 — comandos canónicos

```bash
# Paso 0 atómico (reemplaza extractor-freshness.sh en skills)
secretary fresh mail --format json
secretary fresh meeting
```

### Lectura

```bash
# Barrido compacto (preferir --plain, no --json)
gog gmail search 'newer_than:1d -in:chats' --max 50 --plain --no-input
gog gmail search 'in:inbox is:unread' --max 30 --plain --no-input --account="$ACC_PERSONAL"

# Hilo (triage)
gog gmail thread get <threadId> --plain --no-input
# Cuerpo completo para redactar
gog gmail thread get <threadId> --plain --full --no-input

# Enviados sin respuesta (seguimiento)
gog gmail search 'in:sent newer_than:7d' --max 50 --plain --no-input
```

### Borrador

```bash
# Reply en hilo (SIEMPRE --reply-to-message-id)
gog gmail drafts create \
  --to "dest@example.com" \
  --cc "cc@example.com" \
  --subject "Re: asunto original" \
  --body-file /tmp/borrador.md \
  --reply-to-message-id <messageId> \
  --account "$ACC_PERSONAL" \
  --json --no-input
```

Espejo local (ubicación según `canon/operational/sorting/ubicacion-borradores.md`):

- Triage rutina → `paths.mail.drafts` (`extractors/mail/drafts/`)
- Entregable de proyecto → Cowork (`paths.operational.ubicacion_borradores`)

### Firma de correo (el operador)

Aplicar reglas en `paths.mail.settings` (`extractors/mail/settings.md`). Work account: via `accounts.work` + `--account`.

### Barandas

- **NUNCA** `gog gmail labels modify … --add TRASH`
- Archivar = `--remove INBOX` (solo rutina `revision-correo` o orden explícita)
- Envío (`gog gmail send` o UI) → **OK explícito** del operador
- Invitaciones calendario: reportar, no aceptar/rechazar automáticamente

### Integración

- Tras read de hilo con persona en wiki → `sec-recall` + opcional `sec-compose` (canal: email)
- Si el borrador responde a ítem del brief → ofrecer `sec-status.sh`

---

## Sub-spec: `sec-meeting`

### Misión

Detectar reunión recién terminada aún no en memoria oficial, comprobar si la transcripción Tactiq ya está en Drive, leer resumen tentativo en PR `auto-*`, y **disparar** análisis (`reuniones-update`) si hace falta.

### Constantes

| Variable | Valor |
|----------|-------|
| `TACTIQ_ROOT` | `YOUR_TACTIQ_FOLDER_ID` |
| Estabilidad Tactiq | No procesar si `modifiedTime` < 10 min |
| Shell vacío | `fileSize < 3000` bytes |
| Cadencia rutina | `:00` laboral 9–21 + catch-up 22:00 (America/Lima) |

### Inputs declarativos

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `intent` | sí | `fresh` \| `probe` \| `recall` \| `trigger` |
| `meeting_ref` | no | Título, participante, `event_id`, o ventana `last_2h` |
| `date` | no | `YYYY-MM-DD` (default: hoy Lima) |

### Paso 0 — freshness

```bash
secretary fresh meeting --format json
# reuniones es alias de meeting
```

### Probe transcripción (antes de que mergee reuniones-update)

```bash
TACTIQ_ROOT=YOUR_TACTIQ_FOLDER_ID

# Docs nuevos en raíz Tactiq (no en procesadas/descartadas)
gog drive ls --parent="$TACTIQ_ROOT" --json --account=<gog-account> --no-input \
  | jq '[.files[]? | select(.mimeType=="application/vnd.google-apps.document") | {id,name,modifiedTime,size}]'

# Metadata de candidato
gog drive get <fileId> --json --account=<gog-account> --no-input
```

Cruzar con calendario (reunión que terminó hace <2h):

```bash
# Primary + work account si está registrada
gog calendar events primary --from today --to tomorrow --plain --account=<gog-account>
gog calendar list --account=<gog-account> --plain
```

### Árbol de decisión

```
¿Evento en calendario terminó hace <2h?
  no → sec-recall normal
  sí → ¿Doc en TACTIQ_ROOT raíz, estable (>10min), >3KB?
    no → "esperando Tactiq" + próximo slot reuniones-update
    sí → ¿drive_id en _procesados.jsonl (main)?
      no → ¿En PR reuniones/auto-*?
        sí → leer resumen tentativo (git show)
        no → intent=trigger → invocar reuniones-update (o pedir a el operador)
      sí → sec-recall + resumen en main/PR
```

### `intent=recall`

1. Ejecutar Paso 0 + probe si `meeting_ref` apunta a reunión reciente.
2. `sec-recall` sobre participantes/tema.
3. Marcar evidencia de PR como `⏳ tentativo (PR #N)`.

### `intent=trigger`

Sesión **no escribe** en `extractors/meetings/`. Opciones:

1. Informar próximo `:00` y mostrar candidatos en Drive.
2. Si el operador pide procesar ya: lanzar skill/rutina `reuniones-update` (worktree + PR).
3. Post-proceso: ofrecer merge del PR (`babysit` / `sec-merge`).

### Integración sec-recall

`sec-recall` con asunto de reunión → delegar a `sec-meeting` si la pregunta implica "¿ya está la transcripción?" o "¿qué pasó en la reunión de hace una hora?".

---

## Sub-spec: `sec-drive`

### Misión

Leer estado fresco del índice Drive y operar espejos locales; **nunca** mover/borrar archivos en Drive desde sesión salvo vía `drive-sync` con manifiesto.

### Dos caminos

| Camino | Skill / rutina | Escritura |
|--------|----------------|-----------|
| **Índice + organización** | `drive-crawler` (batch) | Solo propuestas en PR `drive/auto-*` |
| **Docs/Sheets espejados** | `drive-sync` | `cowork sync fetch/sync` con `.drivesync.yaml` |

### Paso 0

```bash
secretary fresh drive
```

### Lectura puntual

```bash
gog drive search "name contains 'término'" --account=<gog-account> --max 10 --plain
gog drive get <fileId> --json --account=<gog-account>
```

Ver doctrina Drive: `../../L4-drive/003-doctrina-drive/README.md` (instance spec L4), skill `drive-sync`.

---

## Sub-spec: `sec-whatsapp`

Stream `whatsapp-monitor` **pausado**. Paso 0: `extractors/whatsapp/memory/`, `state.md`, `secd` `GET /context?name=` si Axon activo. Borradores copy-ready; envío → OK explícito. Política: `extractors/whatsapp/policy.md`.

---

## Sub-spec: `sec-workspace`

### Misión

Auditar `<cowork-root>/<org>/` contra reglas canónicas (`ordenamiento-repo.md`, `etl.md`, `<cowork-root>/CLAUDE.md`) y emitir propuestas como `pm-trainee` — **sin mover**.

### Reglas configurables (resumen)

- Trabajo de org externa → `<cowork-root>/<org>/proyectos/<slug>/`
- Entregables y borradores de proyecto → Cowork, no `.secretary`
- Design systems → `<cowork-root>/<org>/marca/`
- Promoción folder → repo solo con ciclo de vida propio (ver `etl.md`)

### Paso 0

```bash
python3 $SECRETARY_INSTANCE/scripts/ci/validate_ordenamiento.py  # solo .secretary
# Cowork: lectura <cowork-root>/CLAUDE.md + árbol manual o pm-trainee PR semanal
```

---

## Tabla de comandos canónicos (referencia rápida)

### Git / GitHub

| Operación | Comando |
|-----------|---------|
| Fetch main | `git -C $SECRETARY_INSTANCE fetch origin main -q` |
| Leer en main remoto | `git show origin/main:<path>` |
| Leer en PR | `git show origin/<branch>:<path>` |
| Listar PRs auto-* | `gh pr list --repo <instance-repo> --state open --json number,headRefName,title` |
| Diff PR | `gh pr diff <N> --repo <instance-repo>` |

### Correo (`gog`)

| Operación | Comando |
|-----------|---------|
| Search 24h | `gog gmail search 'newer_than:1d -in:chats' --max 100 --plain --no-input` |
| Inbox unread | `gog gmail search 'in:inbox is:unread' --max 30 --plain --no-input` |
| Thread triage | `gog gmail thread get <threadId> --plain --no-input` |
| Thread + cuerpo | `gog gmail thread get <threadId> --plain --full --no-input` |
| Sent 7d | `gog gmail search 'in:sent newer_than:7d' --max 50 --plain --no-input` |
| Draft reply | `gog gmail drafts create --to … --subject … --body-file … --reply-to-message-id <msgId> --json --no-input` |
| Archivar | `gog gmail labels modify <threadId> --remove INBOX --no-input` |
| **Prohibido** | `--add TRASH` |

### Reuniones (Drive + calendario)

| Operación | Comando |
|-----------|---------|
| Listar Tactiq pendientes | `gog drive ls --parent=YOUR_TACTIQ_FOLDER_ID --json` |
| Metadata doc | `gog drive get <fileId> --json` |
| Eventos hoy | `gog calendar events primary --from today --to tomorrow --plain` |
| Procesados local | `git show origin/main:extractors/meetings/memory/_procesados.jsonl \| tail` |

### Frescura global

```bash
secretary fresh all
secretary fresh all --format json
# Heartbeat: extractor-freshness.sh → secretary fresh all --format markdown
```

---

## Criterios de aceptación (MVP)

- [x] Doctrina `extractor-ops.md` publicada
- [x] Spec 010 con sub-specs mail, meeting, drive, workspace
- [x] `sec-mail` SKILL funcional (read + draft + firma + barandas)
- [x] `sec-meeting` SKILL funcional (fresh + probe + trigger pointer)
- [x] `sec-recall` actualizado con delegación Fresh-first
- [x] `drive-sync` con pointer al paradigma
- [x] `sec-drive`, `sec-whatsapp`, `sec-workspace` skills completos (fase 2)
- [x] Wrapper CLI `secretary fresh` (mail, meeting, drive, whatsapp, all)

## Decisiones

| ID | Decisión |
|----|----------|
| DD-1 | Paso 0 reutiliza scripts existentes; no nuevo engine Python en MVP |
| DD-2 | Sesión no escribe en `extractors/meetings/` — solo rutina |
| DD-3 | `drive-sync` permanece en Cowork pipeline; `sec-drive` lo referencia |
| DD-4 | Firma correo: reglas en `paths.mail.settings`; skills referencian, no duplican |
| DD-5 | Ubicación espejo MD: `canon/operational/sorting/ubicacion-borradores.md`; skills referencian vía `paths.operational` |
