---
name: drive-crawler
description: Indexa archivos del Drive, genera consolidados para wiki-update, y propone mejoras de organización
---

Indexa los archivos nuevos o modificados en el Google Drive de Álvaro, genera evidencias para que la rutina wiki-update las integre a la wiki personal, y propone mejoras de organización del Drive. El resultado de la corrida se entrega como un **Pull Request** que actúa de reporte.

## W. WORKTREE AISLADO (hacer ANTES que nada)

Esta corrida NO escribe en la copia de trabajo principal. Crea un worktree efímero, trabaja ahí, y al final abre un PR.

**IMPORTANTE — construir SOBRE el estado más reciente (chaining), no siempre desde `main`.**
Si quedó un PR de drive abierto de una corrida previa que aún no se mergeó, esta corrida lo
**continúa** (parte de su rama) y al final lo **reemplaza** (cierra el viejo). Así `estado.md` y los
consolidados se acumulan corrida a corrida aunque nadie mergee a diario, y nunca hay más de un PR de
drive abierto. Solo cuando NO hay PR de drive abierto se parte de `origin/main` (caso normal tras un
merge). Esto evita el bug histórico: antes cada corrida partía de `main` sin ver el trabajo previo y
repetía el barrido inicial generando PRs casi-iguales.

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=drive
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"

# ¿Hay un PR de drive abierto de una corrida previa? → continuar sobre él (chaining).
PREV=$(gh pr list --label hilo:drive --state open --json number,headRefName,createdAt \
    --jq 'map(select(.headRefName|test("^drive/(auto|consolidado)-")))
          | sort_by(.createdAt) | last | ((.number|tostring)+" "+.headRefName)' 2>/dev/null || true)
PREV_NUM="${PREV%% *}"; PREV_BRANCH="${PREV#* }"
if [ -n "$PREV_NUM" ] && [ "$PREV_NUM" != "$PREV_BRANCH" ]; then
  git fetch origin "$PREV_BRANCH"
  BASE="origin/$PREV_BRANCH"
  echo "Continuando sobre PR de drive #$PREV_NUM ($PREV_BRANCH)"
else
  PREV_NUM=""; BASE="origin/main"
  echo "Sin PR de drive abierto → base = origin/main"
fi
git worktree add -b "$BRANCH" "$WT" "$BASE"
echo "WT=$WT  BRANCH=$BRANCH  BASE=$BASE  PREV_PR=${PREV_NUM:-ninguno}"
```

A partir de aquí, **todas las rutas de ESCRITURA cuelgan de `$WT/`** (`$WT/extractors/drive/state.md`, `$WT/extractors/drive/memory/...`), nunca de `~/.secretary/`. Las lecturas de contexto (wiki, estado previo) también desde `$WT/`. Guardá `$PREV_NUM` — se usa en el cierre (W2) para cerrar el PR superado.

## 0. PREPARACIÓN

### Variables de entorno — raíces del Drive

```bash
GDRIVE="$HOME/Library/CloudStorage/GoogleDrive-your.personal.email@gmail.com"
MY_DRIVE="$GDRIVE/My Drive"
SHARED="$GDRIVE/Shared drives"
INSPIRO="$SHARED/Inspiro Drive"
MISIONES="$SHARED/👩🏽‍🚀 MISIONES"
COMERCIAL="$SHARED/💰 COMERCIAL"
```

**Multi-cuenta.** El crawler cubre la cuenta personal (`your.personal.email@gmail.com`) siempre, y la
corporativa (`your.work.email@company.com`) cuando esté registrada. Para las llamadas a la API de Drive
de inspiro, añadir `--account=your.work.email@company.com`. Verificar disponibilidad igual que en `revision-correo`:

```bash
INSPIRO_ACTIVE=false
if gog drive ls --account=your.work.email@company.com --max 1 --json --no-input 2>/dev/null | grep -q '"id"'; then
  INSPIRO_ACTIVE=true
fi
```

Si `INSPIRO_ACTIVE=false`: crawlear solo la cuenta personal y anotar en el reporte:
"⚠️ `your.work.email@company.com` no registrada — inspiro.pe vía Drive local únicamente".

### Mapa de zonas — política de crawling

El Drive tiene 4 raíces. Cada zona tiene una política: **delta** (crawleada en cada corrida), **backfill** (procesada una vez, luego estática) o **mapa** (solo se registra su existencia, sin leer contenido).

#### My Drive

| Zona | Política | Notas |
|---|---|---|
| `$MY_DRIVE/🚀 Vida profesional/` | **delta** | ya activa desde mayo 2026 |
| `$MY_DRIVE/🌱 Personal/✍️ Ensayos/` | **skip** | escritura personal de Álvaro — no indexar (indicación 2026-06-08) |
| `$MY_DRIVE/🌱 Personal/💵 Finanzas/ANALISIS INGRESOS.xlsx` | **backfill** | complementa drivesync finanzas |
| `$MY_DRIVE/📂 Registros/LLM Enriched summaries/` | **backfill** | resúmenes de reuniones sep-oct 2025 (pre-Tactiq) → wiki reuniones |
| `$MY_DRIVE/📂 Registros/Hedy Transcription/` | **backfill** | 3 transcripciones nov-dic 2025 → wiki reuniones |
| `$MY_DRIVE/🤖 AI & Data Science/` | **mapa** | repos históricos (axon, ion, neuron, InboxPipe, ennui-dendrita, ssh-mcp) — no crawlear contenido; solo registrar existencia en estado.md |
| `$MY_DRIVE/Finanzas/` | **mapa** | cubierta por drivesync; no crawlear |
| `$MY_DRIVE/🌱 Personal/` (resto) | **mapa** | sensible/personal; NO crawlear. Excepción: 💵 Finanzas arriba (Ensayos ya es skip) |
| `$MY_DRIVE/📘 Aprendizaje/` | **mapa** | archivos PUCP 2008-2011, dinámicas — estático, sin valor wiki activo |
| `$MY_DRIVE/🛡️ Backups antiguos/` | **skip** | Google Photos + backups de laptops viejas |
| `$MY_DRIVE/root` (archivos sueltos) | **delta** | analizar ~50/corrida para propuestas de organización (Paso 4); no leer contenido salvo casos especiales |

**Zonas sensibles — skip absoluto (ni metadata):**
- `$MY_DRIVE/🌱 Personal/Passwords.gsheet`
- `$MY_DRIVE/alvaro_keys/`
- `$MY_DRIVE/🌱 Personal/🏠 Pichurrias/` (finanzas compartidas personales)
- `$MY_DRIVE/🤖 AI & Data Science/ssh-mcp/.env` (credenciales)
- `$MY_DRIVE/🌱 Personal/🐶 Cecilia/` (documentos veterinarios)

#### Inspiro Drive — delta activo

| Zona | Política | Notas |
|---|---|---|
| `$INSPIRO/1 PRODUCTOS/2025*/`, `2026*/` | **delta** | productos activos |
| `$INSPIRO/4 CRECEMOS/CRM Inspiro.gsheet` | **delta** | CRM de Inspiro |
| `$INSPIRO/4 CRECEMOS/Oportunidades.gsheet` | **delta** | pipeline comercial |
| `$INSPIRO/4 CRECEMOS/` (resto) | **delta** | propuestas, testimonios, plantillas |
| `$INSPIRO/5 CO CREAMOS/2025*/`, `2026*/` | **delta** | proyectos activos |
| `$INSPIRO/2 FUNDACIONAL/` | **backfill** | doctrina de Inspiro → wiki org |
| `$INSPIRO/6 HERRAMIENTAS/` | **backfill** | base de conocimiento (best practices, KPIs, procedimientos tipo) |
| `$INSPIRO/5 CO CREAMOS/Z_*` | **mapa** | ~40 proyectos cerrados 2017-2025; solo registrar lista de clientes |
| `$INSPIRO/0 BRANDING/` | **mapa** | assets gráficos, no datos |
| `$INSPIRO/3 ADMINISTRACION/` | **mapa** | contratos, contabilidad — sensible; solo metadata de existencia |
| `$INSPIRO/DEPURADOS/` | **skip** | archivos marcados para eliminar |
| `$INSPIRO/Ordenar/` | **mapa** | pendiente de organizar; revisar una vez en backfill |

#### MISIONES (CreativeLab) — backfill histórico

| Zona | Política | Notas |
|---|---|---|
| `$MISIONES/MISIONES 2013-2023/` | **backfill** | ~100 proyectos cerrados → extraer clientes/org para wiki |
| `$MISIONES/MISIONES PERU/` | **backfill** | ~17 proyectos peruanos de CreativeLab |
| `$MISIONES/🦄 CONTROL DE MISIONES/🦄 BAÚL DE MISIONES.gsheet` | **backfill** | tracker maestro de proyectos |
| `$MISIONES/🦄 CONTROL DE MISIONES/DIRECTRICES/` | **backfill** | doctrina operativa de CreativeLab |
| `$MISIONES/🛠 RECURSOS/🤖 AUTOMATIZACIONES/` | **backfill** | herramientas que Álvaro construyó para CreativeLab |
| `$MISIONES/🚀 EN MARCHA/` | **backfill** | verificar si siguen activos o son residuos del traspaso |
| `$MISIONES/OTRAS MISIONES/` | **mapa** | proyectos varios sin completar la metadata; lista de clientes |
| `$MISIONES/🚫 MISIONES EN PAUSA/` | **mapa** | 1 proyecto pausado |

#### COMERCIAL (CreativeLab) — backfill histórico

| Zona | Política | Notas |
|---|---|---|
| `$COMERCIAL/🏃 Propuestas/` | **backfill** | propuestas 2014-2024; historia comercial → wiki org y clientes |
| `$COMERCIAL/Repositorio de contratos CreativeLab.gsheet` | **backfill** | índice de contratos |
| `$COMERCIAL/CreativeLab _ Deck comercial completo 20230501.pdf` | **backfill** | deck de ventas → wiki org CreativeLab |

---

**Regla de prioridad entre políticas:**

- `delta` corre en CADA corrida diaria.
- `backfill` corre solo si la zona NO tiene entrada en `estado.md` como "procesada". Una vez procesada, se marca y no se toca más (salvo que el crawler detecte cambios recientes en esa zona con `find -newer`).
- `mapa` solo registra existencia (nombre, tipo, fecha más reciente del `find`) en `estado.md`; nunca lee contenido.
- `skip` no aparece ni en el find.

### Herramientas — dos vías de acceso al Drive

**Vía A — Filesystem (preferir cuando sea posible, es más rápida y no consume tokens de MCP):**

Google Drive está montado en streaming en:
```
DRIVE="$HOME/Library/CloudStorage/GoogleDrive-your.personal.email@gmail.com/My Drive"
```

Puedes usar `ls`, `find`, `stat`, `cat`, `head` directamente sobre `$DRIVE`. Los archivos nativos de Google (Docs, Sheets, Slides) aparecen como stubs `.gdoc`, `.gsheet`, `.gslides` — estos NO son legibles via filesystem (son JSON con un link), pero sí puedes:
- Listar estructura de carpetas y archivos (`ls`, `find`)
- Leer fechas de modificación (`stat -f '%Sm' -t '%Y-%m-%d'` o `find -newer`)
- Leer contenido de archivos NO nativos: PDFs, .docx, .xlsx, .csv, .txt, .md (con `cat`/`head`)
- Contar archivos, detectar duplicados, archivos sueltos, nombramientos inconsistentes

**Vía B — MCP de Google Drive (usar solo cuando filesystem no alcanza):**

Herramientas MCP (prefijo `mcp__0152ec35-ec64-4894-9e7c-2260d61b50e2__`):
- `search_files` — buscar por query (parentId, modifiedTime, mimeType, fullText)
- `list_recent_files` — listar recientes por orden
- `get_file_metadata` — metadata de un archivo
- `read_file_content` — contenido como texto natural (**austero**: solo para archivos nativos de Google que no se pueden leer vía filesystem)

**Regla de decisión:**
1. Para listar, contar, detectar estructura → filesystem siempre
2. Para leer contenido de .pdf, .docx, .xlsx, .csv, .txt → filesystem (`cat`/`head`)
3. Para leer contenido de .gdoc, .gsheet, .gslides → MCP `read_file_content` (única vía)
4. Para buscar por contenido (fullText) → MCP `search_files`

### Contexto — leer antes de actuar

1. **Estado de la rutina**: `$WT/extractors/drive/state.md` — contiene la fecha de la última corrida exitosa y el inventario de carpetas/archivos ya indexados.
2. **Wiki personal**: `$WT/knowledge/wiki/articulos/` — consultar para no duplicar info que ya está en la wiki (personas, organizaciones, temas).
3. **Memoria de corridas anteriores**: los 2-3 archivos más recientes en `$WT/extractors/drive/memory/`.

## 1. DETECCIÓN DE CAMBIOS (fase metadata — bajo costo de tokens)

**Preferir filesystem para esta fase:**

```bash
# My Drive — zonas delta activas
find "$MY_DRIVE/🚀 Vida profesional" \
     "$MY_DRIVE/🌱 Personal/✍️ Ensayos" \
     -newer /tmp/drive-last-run-marker -type f 2>/dev/null

# Inspiro Drive — zonas delta activas
find "$INSPIRO/1 PRODUCTOS" \
     "$INSPIRO/4 CRECEMOS" \
     "$INSPIRO/5 CO CREAMOS" \
     -not -path "*/Z_*" \
     -newer /tmp/drive-last-run-marker -type f 2>/dev/null

# Root de My Drive — archivos sueltos (para propuestas de organización)
find "$MY_DRIVE" -maxdepth 1 -type f \
     -not -name ".DS_Store" \
     -newer /tmp/drive-last-run-marker 2>/dev/null
```

Para backfill pendiente, chequear en `estado.md` qué zonas de tipo `backfill` no tienen entrada de "procesada" y añadirlas al find de esta corrida (máximo 1-2 zonas de backfill por corrida para no exceder el límite de 20 archivos con contenido).

Si no existe el marker, usar `find ... -mtime -1` para las últimas 24h. Crear/actualizar el marker al final de cada corrida.

Como fallback (o para primera corrida amplia), complementar con MCP:
```
modifiedTime > '{LAST_RUN_ISO}' and owner = 'me'
```

**Cómo saber si es realmente la primera corrida:** leer `$WT/extractors/drive/state.md`. Como el worktree
parte del PR de drive más reciente (chaining) o de `main` ya con corridas mergeadas, si `estado.md`
registra alguna corrida previa **NO es primera corrida** → hacer detección incremental con el marker
(`find -newer`), no el barrido amplio. Solo si `estado.md` no registra ninguna corrida previa (stub
inicial) se hace el barrido inicial. Nunca asumir "primera corrida" por reflejo.

Si es la primera corrida (estado.md sin ninguna corrida previa registrada), hacer un barrido inicial más amplio:
- Arrancar por las carpetas de alto valor:
  - `🚀 Vida profesional` (id: `YOUR_DRIVE_FOLDER_ID`) — proyectos, perfil, consultorías, contratos
  - `🌱 Personal` (id: `YOUR_DRIVE_FOLDER_ID`) — finanzas, ensayos, documentos
  - `📂 Registros` (id: `YOUR_DRIVE_FOLDER_ID`) — Obsidian, registros
- Luego archivos sueltos en root que sean docs/sheets/presentations
- En la primera corrida, procesar por **lotes** para no explotar tokens: empezar por los más recientes (últimos 6 meses), luego ir hacia atrás en corridas sucesivas.

### Filtro de tipos (CRÍTICO para austeridad)

**SÍ indexar** (leer contenido):
- `application/vnd.google-apps.document` (.gdoc → leer vía MCP)
- `application/vnd.google-apps.spreadsheet` (.gsheet → leer vía MCP)
- `application/vnd.google-apps.presentation` (.gslides → leer vía MCP)
- `application/pdf` (.pdf → intentar vía filesystem primero, MCP como fallback)
- `application/vnd.openxmlformats-officedocument.*` (.docx, .xlsx, .pptx → filesystem)
- `text/plain`, `text/csv` (.txt, .csv → filesystem, solo si tienen títulos informativos)

**NO indexar** (solo registrar metadata):
- `image/*`, `video/*`, `audio/*` — registrar que existen, no leer contenido
- `application/zip`, `application/x-*` — skip
- `application/vnd.google-apps.form` — solo registrar título
- `application/vnd.google-apps.folder` — solo como estructura

**SKIP completo** (ni metadata):
- Carpeta `🛡️ Backups antiguos` (id: `YOUR_DRIVE_FOLDER_ID`)
- Carpeta `Randomness` (id: `YOUR_DRIVE_FOLDER_ID`)
- Carpeta `Tactiq Transcription` (id: `YOUR_TACTIQ_FOLDER_ID`) — ya cubierta por reuniones-update
- Carpeta `Meet Recordings` (id: `YOUR_DRIVE_FOLDER_ID`) — videos, no legibles
- Archivos con título "Untitled document" o "Untitled spreadsheet" — registrar pero no leer

**SKIP de contenido — carpetas que son espejo de WIP local de Álvaro (feedback PR #59):**

Algunas carpetas que aparecen en el Drive son en realidad **espejos** de trabajo en curso que
Álvaro mantiene localmente bajo `~/Cowork/` (notas, guiones de mentoría, drafts). Tratarlas
como fuentes externas contamina la wiki con borradores. Para estas carpetas: registrar solo
**metadata** (nombre, tipo, fecha), **NO leer contenido vía MCP**, **NO generar entradas de
personas/proyectos/organizaciones** en `extractors/drive/memory/`, **NO proponer reorganización** del Drive
sobre ellas.

Carpetas conocidas con esta naturaleza (mantener esta lista al día):
- `Mentoría Adultos Imparables — Andre Pantoja/` (espejo de `~/.secretary/mentoria/adultos-imparables/andre/`)

**Cómo detectar espejos nuevos en futuras corridas**: antes de leer contenido de una carpeta
del root del Drive cuyo nombre no esté en el inventario previo, hacer `ls ~/Cowork/` y
subdirectorios buscando un equivalente por nombre o tema (mentoría, propuestas, drafts).
Si lo hay → tratar como espejo (solo metadata) y añadir la carpeta a esta lista. La regla
general: **si el contenido lo está produciendo Álvaro mismo, no es fuente — es WIP**.

## 2. LECTURA SELECTIVA (fase contenido — gasto controlado)

Para cada archivo que pasó el filtro y es nuevo/modificado:

1. Verificar si ya está en el inventario (estado.md) con el mismo `modifiedTime` → skip si no cambió.
2. Elegir vía de lectura según tipo (filesystem vs. MCP, ver regla de decisión arriba).
3. Extraer información valiosa:
   - **Sobre personas**: roles, relaciones, datos de contacto
   - **Sobre organizaciones**: qué hacen, relación con Álvaro
   - **Sobre proyectos**: estado, decisiones, deliverables
   - **Datos biográficos**: experiencias, logros, timeline
   - **Documentos financieros/legales**: solo metadata + resumen breve (NO copiar montos ni datos sensibles)

### Límite de tokens por corrida

- Máximo **20 archivos leídos con contenido** por corrida (archivos leídos vía filesystem no cuentan contra el límite de MCP, pero sí contra el de 20 para mantener el PR manejable). Si hay más pendientes, priorizar por:
  1. Archivos modificados más recientemente
  2. Carpetas de mayor valor (Vida profesional > Personal > Registros)
  3. Docs/Sheets > PDFs > otros
- Registrar los pendientes en estado.md para la siguiente corrida.

## 3. GENERACIÓN DE CONSOLIDADOS

Escribir evidencias en `$WT/extractors/drive/memory/` siguiendo el mismo patrón que correo y whatsapp:

### `extractors/drive/memory/YYYY-MM-DD.md` (memo diario)

Solo información **durable y no derivable** del Drive:
- Archivos nuevos o significativamente modificados (título, carpeta, tipo, resumen de 1-2 líneas)
- Datos sobre personas u organizaciones descubiertos en documentos
- Proyectos o iniciativas mencionados en docs que no aparecen en la wiki
- Documentos relevantes que podrían alimentar artículos específicos de la wiki

NO guardar: contenido completo de archivos, estructura de carpetas ya conocida, archivos triviales.

### `extractors/drive/memory/personas.md` (consolidado acumulativo)

Formato idéntico al de `extractors/mail/memory/personas.md`:
```
## Nombre Persona
- fuente: drive — "Título del documento" (YYYY-MM-DD)
- rol/dato descubierto
- relación con Álvaro (si se detecta)
```

### `extractors/drive/memory/organizaciones.md` (consolidado acumulativo)

Formato idéntico al de `extractors/mail/memory/organizaciones.md`.

### `extractors/drive/memory/proyectos.md` (consolidado acumulativo)

Para proyectos e iniciativas descubiertos en documentos:
```
## Nombre Proyecto
- fuente: drive — "Título del documento" (YYYY-MM-DD)
- descripción breve
- estado (si se puede inferir del doc)
- personas/orgs involucradas
```

### `extractors/drive/memory/documentos-clave.md` (consolidado acumulativo)

Índice de documentos del Drive que son valiosos como referencia:
```
## Título del documento
- id: {fileId}
- carpeta: {ruta}
- tipo: {mimeType simplificado}
- modificado: {fecha}
- resumen: 1-2 líneas de qué contiene
- relevancia: por qué es valioso para la wiki/secretary
```

## 4. PROPUESTAS DE ORGANIZACIÓN DEL DRIVE

En cada corrida, además de indexar, analizar la estructura del Drive y proponer mejoras concretas. Escribir las propuestas en `$WT/extractors/drive/organizacion.md` (archivo acumulativo, no reescribir — añadir sección con fecha).

### Qué detectar

**Archivos sueltos en root (prioridad alta):**
El root del Drive tiene ~343 archivos sueltos. Para cada uno, proponer a qué carpeta existente debería moverse. Agrupar por afinidad:
- Archivos de consultorías/proyectos → `🚀 Vida profesional/💼 Consultorías y proyectos temporales/`
- Archivos financieros/contables → `🌱 Personal/💵 Finanzas/`
- Documentos personales/legales → `🌱 Personal/`
- Propuestas/presentaciones de Inspiro → `🚀 Vida profesional/🌸 Inspiro/`
- Archivos de ennui → `🚀 Vida profesional/🌱 ennui/`
- CSVs de importación contable → `🌱 Personal/💵 Finanzas/`
- Fotos/imágenes sueltas → `🌱 Personal/📸 Fotos/`

**Duplicados y versiones:**
- Archivos con el mismo nombre o nombre + "(1)" → proponer cuál conservar
- Múltiples versiones del mismo documento → proponer consolidar

**Nombramientos inconsistentes:**
- Archivos sin fecha en el nombre cuando deberían tenerla
- Archivos sin contexto en el título (e.g. "Untitled document")
- Mezcla de convenciones de fecha (YYYYMMDD vs YYYY-MM-DD vs DD.MM.YYYY)

**Carpetas que podrían crearse:**
- Si hay un cluster de archivos sueltos sobre el mismo tema, sugerir una carpeta nueva

**Archivos obsoletos o basura:**
- Archivos muy antiguos que no han sido accedidos en años y están sueltos en root
- Stubs vacíos, archivos de prueba, exports temporales

**Residuos de uploads y temporales (prioridad alta — feedback de Álvaro, PR #27):**
Muchos archivos sueltos del root NO son documentos a archivar, sino **residuos**: uploads que
Álvaro hizo para importar tablas a Google Sheets, o copias que Drive genera automáticamente al
compartir. El hecho de estar sueltos en el root es señal de que probablemente son descartables.
- Patrones típicos de residuo: `import_file_to_*`, `*_export*.csv`, `Combined_*`, `consolidated_*`,
  `M_*.csv` / `Reg_*.csv` (tablas maestras subidas a Sheets), `*.xlsx.csv`, `Copy of *`,
  `Untitled *`, archivos con sufijo `(1)`/`(2)`/`(3)`.
- **Antes de proponer mover** un archivo de estos: verificar si ya fue **incorporado a otra cosa**
  (un Sheet, una carpeta de proyecto, un consolidado posterior) o si es un **duplicado/temporal**.
  Si lo es → proponerlo directamente en "candidatos a archivar/eliminar", NO en "mover".
- **Proponer borrar está bien** para estos casos: no hace falta encontrarles una carpeta destino.
  La rutina sigue sin borrar nada por su cuenta — solo lo propone para que Álvaro lo confirme.
- Cuando haya duda entre "mover" y "eliminar" para un archivo del root, **inclinarse por proponer
  eliminar** (con una nota de por qué parece residuo), salvo que el contenido sea claramente valioso.

### Formato del reporte

En `$WT/extractors/drive/organizacion.md`, añadir una sección por corrida:

```markdown
## YYYY-MM-DD — Propuestas de organización

### Archivos sueltos en root → mover
| Archivo | Destino sugerido | Motivo |
|---|---|---|
| `20230204 Firma contrato Shop Trendy LVA.pdf` | 🚀 Vida profesional/✍️ Contratos/ | contrato firmado |
| `mi_fibra_marzo.csv` | 🌱 Personal/💵 Finanzas/ | extracto bancario |

### Duplicados detectados
| Archivo A | Archivo B | Recomendación |
|---|---|---|

### Nombramientos a mejorar
| Archivo actual | Nombre sugerido | Motivo |
|---|---|---|

### Carpetas sugeridas
- (si aplica)

### Archivos candidatos a archivar/eliminar
| Archivo | Motivo |
|---|---|
```

### Ritmo de análisis

- No analizar todo en una sola corrida. Procesar **~50 archivos sueltos del root por día** (vía filesystem: rápido y sin tokens). En ~7 corridas se cubre todo el root.
- En corridas posteriores, rotar hacia subcarpetas que parezcan desordenadas.
- Las propuestas son SOLO propuestas — Álvaro las revisa en el PR y decide. La rutina **NUNCA mueve, renombra ni elimina archivos del Drive**.

## 5. ACTUALIZACIÓN DE ESTADO

### `extractors/drive/state.md`

Reescribir con:
- Fecha y hora de la corrida. **No hardcodear "corrida 1 / primera ejecución".** Leer el estado previo
  y, si ya había corridas, continuar el conteo (ej. "corrida N — 2026-05-23 08:09") o simplemente
  fechar la corrida. Marcar "primera ejecución" SOLO si de verdad no había estado previo.
- Archivos procesados en esta corrida (con contenido vs. solo metadata)
- Archivos pendientes para la siguiente corrida
- Inventario actualizado: hash de {fileId: modifiedTime} de archivos ya indexados (acumular sobre el
  inventario previo que vino en el base; no reiniciarlo)
- Estadísticas: total de archivos en Drive, indexados, pendientes
- Progreso de organización: cuántos archivos del root ya fueron evaluados (acumular sobre lo previo)

## 6. ARCHIVOS SENSIBLES — REGLA ESTRICTA

**NUNCA** copiar al repo contenido de:
- Archivos con "password", "contraseña", "credential", "token", "key" en el título
- Documentos financieros con montos específicos (registrar solo metadata)
- Documentos legales personales (DNI, pasaporte, declaraciones) — solo metadata
- El archivo "Passwords" (id: `YOUR_DRIVE_FOLDER_ID`) — **SKIP absoluto**
- La carpeta `alvaro_keys/` en el root — **SKIP absoluto**

Para estos, solo registrar: título, carpeta, tipo, fecha de modificación. Nada de contenido.

## W2. CIERRE — PR como reporte

Después de escribir todos los archivos:

```bash
cd "$WT"
git add drive/
git status
```

Si hay cambios:

```bash
git commit -m "chore(drive): indexación diaria $(date +%Y-%m-%d)"
git push -u origin "$BRANCH"
```

Abrir PR con `gh pr create`:
- **Firma del body:** `_firma.md` → `sec-signature.sh drive-crawler`.
- Título: `chore(drive): indexación diaria YYYY-MM-DD`
- Body: resumen de la corrida con secciones:
  - **Archivos indexados**: cuántos, cuáles los más relevantes
  - **Hallazgos para la wiki**: personas, orgs, proyectos descubiertos
  - **Propuestas de organización**: resumen de lo propuesto (mover N archivos, M duplicados, etc.)
  - **Pendientes**: qué queda para la próxima corrida
  - Si esta corrida **continuó** un PR previo (`$PREV_NUM`), indicarlo: "Continúa y reemplaza #$PREV_NUM".
- Label: `hilo:drive` (crear si no existe)
- Base: `main`

**Cerrar el PR previo superado (chaining).** Como este PR contiene todo lo del anterior + lo nuevo,
cerrar el viejo para que quede UN solo PR de drive abierto:

```bash
NEW_NUM=$(gh pr view "$BRANCH" --json number --jq .number)
if [ -n "${PREV_NUM:-}" ]; then
  gh pr close "$PREV_NUM" --delete-branch \
    --comment "Superado por #$NEW_NUM (lo continúa e incluye todo su contenido + la corrida nueva)."
fi
```

Limpiar worktree:
```bash
cd ~/.secretary
git worktree remove "$WT" --force 2>/dev/null || true
```

> **Ciclo de vida de los PRs de drive.** Por el chaining, normalmente hay **un único** PR de drive
> abierto que se va engordando corrida a corrida y reemplazando al anterior. Desde 2026-06, drive **sí**
> está en el gate W0 de auto-merge de `wiki-update`: cada cierre del día mergea el `drive/auto-*` más
> reciente (tras pasar el gate de comentarios) y cierra los más viejos. Desde 2026-06-06, `wiki-update`
> **sí consume** `extractors/drive/memory/` como fuente (sección 1.6 de su SKILL): integra personas, orgs,
> entidades y proyectos descubiertos por este crawler. El merge no ejecuta nada sobre Drive: las
> propuestas de mover/borrar siguen siendo eso, propuestas que Álvaro decide aplicar.

Si NO hay cambios (nada nuevo en Drive y nada que proponer), no crear PR. Solo limpiar el worktree.

## NOTAS DE AUSTERIDAD

- **Filesystem primero**: listar, contar, leer archivos no nativos vía filesystem. Cero tokens de MCP.
- **MCP solo para contenido nativo de Google** (.gdoc, .gsheet, .gslides) y búsquedas por fullText.
- Si un archivo ya fue indexado y no cambió (`modifiedTime` igual), NO releerlo.
- En la primera corrida, ser conservador: empezar por los 20 archivos más recientes de Vida profesional + 50 archivos del root para organización.
- Los consolidados son el producto. wiki-update se encarga de integrarlos. No duplicar ese trabajo.