---
id: "012"
slug: instance-layout-extractors-knowledge
layer: L0
status: implementado
last_reviewed: 2026-07-02
implemented:
  - $SECRETARY_INSTANCE/extractors/
  - $SECRETARY_INSTANCE/loops/
  - $SECRETARY_INSTANCE/knowledge/
  - $SECRETARY_INSTANCE/.secretary.yml
gaps:
  - secd/lib/objectives.mjs aún apunta a objetivos/ (no knowledge/objectives/)
  - secd/lib/memory.mjs y resolver.mjs paths legacy (wiki/, reuniones/, whatsapp/)
  - PR secretary-core #14 cerró modules CLI; paths secd pendientes
---

# Feature 012 — Layout de instancia: `extractors/` + `knowledge/`

**Estado:** `implementado` (instancia, PR #364) — follow-up engine `secd` paths vía YAML **pendiente** (no incluido en merge #14)  
**Origen:** sesión de diseño post-spec 011 — vocabulario inglés SOTA, descomponer `memoria/` sobrecargada, alinear con harness (#364).  
**Relacionado:** PR [#364](https://github.com/<instance-repo>/pull/364) (governance rename) · spec 011 · spec 010 (`sec-*` fresh-first) · spec 009 (CLI paths) · spec 007 (Axon × secd)

## Decisiones cerradas

*(Confirmado 2026-07-01 — «knowledge ya está decidido»)*

| Decisión | Estado |
|----------|--------|
| `memoria/` → `knowledge/` | **APPROVED** — rename del contenedor de consolidación |
| `extractores/` → `extractors/` | **APPROVED** — rename mecánico del contenedor |
| Módulos internos extractors | **AMENDED** — inglés: `mail`, `meetings`, `whatsapp`, `drive`; paths sistema en inglés (`state.md`, `summaries/`, …) |
| Plano `loops/` | **APPROVED** — `job-search` sale de extractors; workflows cerrados |
| Seis hijos de `knowledge/` | **APPROVED** — stubs + migración (§7) |
| 10.1.1 objectives subdirs | **DECIDIDO** — inglés: `strategy/`, `relations/` (contenido FM español) |
| 10.1.2 indices en git | **DECIDIDO** — opción B: gitignore + rebuild |
| 10.1.3 embeddings | **DECIDIDO** — opción B: stub/manifest only |
| 10.1.4 playbooks vs rules | **DECIDIDO** — opción C ligera: convención + denylist; sin CI nuevo |
| 10.2.1 módulos internos | **AMENDED** — inglés (`mail`, `meetings`, …); paths sistema en inglés |

**Follow-up engine (pendiente — no en merge #14):** `secretary-core/secd/lib/objectives.mjs` — hoy `join(instance, 'objetivos')`; destino `knowledge/objectives` vía `paths.knowledge.objectives.*`. Igual para `memory.mjs` (`wiki/articulos` → `knowledge/wiki/articulos`) y `resolver.mjs` (paths extractors en inglés).

Hijos de `knowledge/` aprobados:

1. **`wiki/`** — prosa enciclopédica (existente; `git mv` desde `memoria/wiki/`)
2. **`objectives/`** — store secd L0/L1 (promover scaffold `objetivos/`)
3. **`catalog/`** — taxonomías estructuradas
4. **`indices/`** — índices generados (resolver, entity→slug, recall)
5. **`embeddings/`** — metadatos índice RAG de la instancia
6. **`playbooks/`** — procedimiento durable, no invocable

> **Vocabulario en este documento:** donde importa la transición, se citan **nombres viejos** (pre-#364 / pre-012) y **nombres nuevos** (post-merge). Vocabulario **primario** asumido tras #364 + 012:
> `canon/{rules,operational,playbooks}/`, `subsystem/`, `extractors/`, `knowledge/`.

---

## 1. Problema / motivación

### 1.1 `memoria/` sobrecargada

Hoy `memoria/` (futuro `knowledge/`) es un contenedor de **un solo hijo útil** (`wiki/`). El nombre sugiere «todo lo que secretary sabe», pero en la práctica mezcla roles distintos que el engine y `secd` ya tratan por separado:

| Rol cognitivo | Hoy | Problema |
|---------------|-----|----------|
| Prosa durable (personas, orgs, temas) | `memoria/wiki/articulos/` | Correcto pero es **una** KB entre varias |
| Objetivos de relación / estrategia | *scaffold* `objetivos/` en raíz (esperado por `secd`, **no existe** en instancia) | Fuera del árbol gobernado; path español inconsistente |
| Índices generados (resolver Axon, entity→slug) | En RAM en `secd/lib/resolver.mjs` | No persistido; se reconstruye en cada arranque |
| Taxonomías estructuradas | Dispersas en wiki + `*/memory/entidades.md` | Sin hogar para catálogos explícitos |
| Metadatos RAG / embeddings | No existe carpeta | Discutido en reuniones RAG; sin sitio canónico |
| Procedimientos durables (no skills invocables) | Mezclados con skills en `~/.claude/` o rules | Riesgo de prompt injection (ver §1.3) |

La constitución y el operativo (`canon/operational/sorting/sistemas-ordenamiento.md` post-#364; hoy `policies/sistemas-ordenamiento.md`) describen **captura** (`extractores/`) vs **consolidación** (`memoria/wiki/`). Falta nombrar el **plano knowledge** completo: varias KBs con contratos de lectura/escritura distintos.

### 1.2 `extractores/` en español

El engine (`secretary-core`), la documentación canónica y el vocabulario harness usan **extractors**. La carpeta física `extractores/` rompe consistencia con:

- Constitución §6 y specs en inglés en `canon/rules/`
- Claves YAML y CLI (`secretary config path …`)
- PRs y scopes de commit (`extractores` vs `extractors`)

El rename es **mecánico** (git mv + YAML + referencias), pero toca muchos consumidores — merece fase propia.

### 1.3 Contexto RAG (qué se discutió y qué iría en `knowledge/embeddings/`)

Referencias primarias en la instancia:

| Fuente | Qué aporta al diseño |
|--------|----------------------|
| ``extractors/meetings/summaries/2025-11-21-revision-sistema-rag.md`` (instance path) |
| ``extractors/meetings/summaries/2026-02-12-revision-sistema-rag.md`` (instance path) |
| ``_diseño/specs/L2-memoria/006-sec-compose/spec.md`` (instance path) | `sec-compose` se beneficia de grafo wikilinks + **embeddings** para ancla conversacional; hoy grep/recall, futuro más preciso |
| ``_diseño/specs/L3-captura/010-extractor-skills/spec.md`` (instance path) | `GET /recall?q=` vía `secd`; recall determinista vía `secretary recall` |

**Qué NO es `knowledge/embeddings/`:** no reemplaza la wiki ni los `*/memory/` de extractores. Es la capa de **metadatos de índice vectorial** cuando la instancia hospeda (o referencia) un índice RAG:

- Manifiesto de chunks: `source_path`, `chunk_id`, offsets, `embedding_model`, `embedded_at`
- Punteros a almacén externo (pgvector, sqlite-vec, archivo binario) si los vectores no viven en git
- Versión del índice y job de rebuild (última corrida, artículos incluidos, hash del corpus)
- Config de retrieval (top-k, filtros por categoría wiki, boost por frescura de extractor)

**Qué SÍ permanece fuera:** embeddings de proyectos cliente (client project embeddings) viven en sus workspaces Cowork/Dev; secretary solo documenta la **decisión arquitectónica** en wiki/playbooks si aplica a el operador.

**Relación con `canon/playbooks/`:** los playbooks durables (procedimientos en prosa, checklists, «cómo hacemos X») son **corpus legible por agentes** pero **no invocables** como skill. La reunión 2026-02-12 advierte que texto procedural malicioso puede ejecutarse si el agente lo trata como instrucción — gobernanza: playbooks bajo CI/review, distintos de `~/.claude/skills/` y de `canon/rules/` canónicas.

---

## 2. Árbol objetivo de `$SECRETARY_INSTANCE/`

Asume **#364 mergeado** (governance) + **012** (extractors + knowledge).

```
$SECRETARY_INSTANCE/
├── .secretary.yml          # fuente de verdad de paths (claves en inglés)
├── CLAUDE.md · AGENTS.md
│
├── canon/                  # frontiers: rules + operational + playbooks
│   ├── rules/              # canónico — reglas de cualquier instance (antes doctrines/)
│   ├── operational/        # tablas operativas indexadas en YAML (antes policies/)
│   └── playbooks/          # runbooks de instancia (antes knowledge/playbooks/)
├── templates/
├── references/
├── _diseño/                # diseño personal — no canónico
│
├── extractors/             # captura por fuente externa (antes extractores/)
│   ├── mail/               # antes correo
│   ├── whatsapp/
│   ├── meetings/           # antes reuniones
│   └── drive/
│
├── loops/                  # workflows cerrados (job-search reclassificado)
│   └── job-search/
│       ├── inbox.md
│       ├── sources-web/    # antes fuentes-web
│       └── applications.md # antes postulaciones.md
│
├── knowledge/              # consolidación y KBs durables (antes memoria/)
│   ├── wiki/               # prosa enciclopédica (antes memoria/wiki/)
│   ├── objectives/         # store secd L0/L1 (antes scaffold objetivos/ en raíz)
│   ├── catalog/            # taxonomías estructuradas
│   ├── indices/            # índices generados (resolver, entity→slug, …)
│   ├── embeddings/         # metadatos índice RAG (si instance-hosted)
│   └── playbooks/          # procedimiento durable, no invocable
│
├── subsystem/              # meta del subsistema (antes operaciones/)
│   ├── housekeeping/
│   ├── wip/
│   ├── heartbeat/
│   └── routines/
│
├── scripts/ci/
└── .cursor/
```

**Aliases YAML (una release):** mantener claves deprecated documentadas en #364 (`paths.doctrines` → `paths.rules`, etc.) y añadir para 012 (`paths.extractores` → `paths.extractors`, `paths.memoria` → `paths.knowledge`).

---

## 3. Cada KB bajo `knowledge/`

### 3.1 `knowledge/wiki/` (existente)

| | |
|---|---|
| **Propósito** | Prosa durable: personas, organizaciones, temas, módulos. Destilado del pipeline ETL. |
| **Quién escribe** | Bibliotecario (`wiki-update`), `sec-write` / `wiki-write`, integración `sec-sys-integrate` |
| **Quién lee** | `sec-recall`, `secretary recall`, `secd` `GET /recall`, pulse, briefing, humanos (HTML en `output/`) |
| **Formato** | Markdown + frontmatter; wikilinks `categoria/slug`; `memoria/wiki/comentarios/` → `knowledge/wiki/comentarios/` |
| **Migración** | `git mv memoria/wiki knowledge/wiki`; actualizar `paths.wiki.*` en YAML |

Subárbol sin cambio semántico: `articulos/`, `memory/` (log Bibliotecario), `comentarios/`, `output/` (generado).

### 3.2 `knowledge/objectives/` (promover scaffold secd)

| | |
|---|---|
| **Propósito** | Objetivos de relación (L1) y estrategia (L0) vinculados a entidades wiki. Alimenta context card Axon y relay. |
| **Quién escribe** | `secd` `POST /objectives`, relay LLM (origen `relay`), sesiones humanas, futuro `sec-write` con destino objectives |
| **Quién lee** | `secd` `GET /objectives`, `GET /context`, `relay.mjs`, pulse (futuro) |
| **Formato** | Markdown + frontmatter (`id`, `nivel`, `titulo`, `parent`, `entidad`, `estado`, `origen`, `ambito`, `acciones`); schema en `knowledge/objectives/_schema.md` |
| **Migración** | Hoy: `secd/lib/objectives.mjs` apunta a `join(instance, 'objetivos')` — **no hay archivos** en instancia. Crear árbol `knowledge/objectives/{estrategia,relaciones}/` + actualizar engine a `knowledge/objectives` vía `secretary config path` |

**Estado actual del scaffold (`secd/`):**

```javascript
// objectives.mjs — storeDir(instance) → join(instance, 'objetivos')
// L0 → objetivos/estrategia/, L1 → objetivos/relaciones/
```

Endpoints en `server.mjs`:

| Método | Ruta | Comportamiento |
|--------|------|----------------|
| GET | `/objectives?entity=&estado=&nivel=` | `queryObjectives()` — filtra por wikilink entidad, estado, nivel |
| POST | `/objectives` | `upsertObjective()` — daemon minta `obj-YYYYMMDD-NNN` y fecha |
| GET | `/context` | Ensambla card: summary wiki + acciones abiertas + objectives activos/sugeridos |

`knowledge/objectives/` es el **store canónico durable**; `secd` deja de asumir carpeta española en raíz.

### 3.3 `knowledge/catalog/`

| | |
|---|---|
| **Propósito** | Taxonomías explícitas: tipos de entidad, etiquetas controladas, ontologías ligeras (ej. estados de pipeline comercial, categorías de programa). |
| **Quién escribe** | Sesiones de gobernanza, `wiki-update` cuando promueve desde `entidades.md`, futuro validador |
| **Quién lee** | Resolver, `sec-recall`, rutinas que necesitan enum cerrado |
| **Formato** | YAML o MD tabular con frontmatter; una entrada por taxonomía |
| **Migración** | **Nuevo stub** — extraer gradualmente listas duplicadas en wiki infobox y `*/memory/entidades.md` |

### 3.4 `knowledge/indices/`

| | |
|---|---|
| **Propósito** | Índices **generados** y cache persistido: entity→slug, alias WhatsApp→persona, jid map, índice invertido recall |
| **Quién escribe** | `secd` al rebuild, `wiki-update` post-build, job `secretary index` (futuro CLI) |
| **Quién lee** | `secd/lib/resolver.mjs`, Axon bridge, `secretary recall --format json` |
| **Formato** | JSON/JSONL versionado; `resolver-v1.json`, `recall-index.json`; regenerable — **puede** ir a `.gitignore` parcial o commitarse según política de frescura |
| **Migración** | Hoy `buildIndex()` solo en RAM (`resolver.mjs`); persistir salida bajo `knowledge/indices/` y cargar si fresca |

**Nota:** `memory.mjs` en secd hoy usa path legacy `join(instance, 'wiki', 'articulos', …)` — debe resolverse vía YAML (`paths.wiki.articles`) → `knowledge/wiki/articulos/`.

### 3.5 `knowledge/embeddings/`

| | |
|---|---|
| **Propósito** | Metadatos del índice RAG **de la instancia personal** (no proyectos Cowork): manifiesto de chunks, modelo, punteros a store vectorial |
| **Quién escribe** | Job de embedding post `wiki-update` o comando explícito; **no** extractores |
| **Quién lee** | `secd` recall híbrido (futuro), `sec-recall` paso semántico, `sec-compose` ancla conversacional |
| **Formato** | `manifest.json` + sidecars por corpus (`wiki/`, opcional `playbooks/`); vectores en subdir gitignored si local |
| **Migración** | **Nuevo stub** — sin índice hoy; documentar en README de carpeta; alinear con visión RAG (esquema cognitivo + retrieval, no reemplazar wiki) |

### 3.6 `canon/playbooks/`

| | |
|---|---|
| **Propósito** | Conocimiento **procedural durable**: «cómo corre revision-correo», runbooks de instancia, checklists de onboarding — legible por agentes, **no** invocable como `/skill` |
| **Quién escribe** | Sesiones de diseño, promoción desde `_diseño/` cuando estabiliza |
| **Quién lee** | Rutinas (como referencia), agentes con permiso explícito, RAG |
| **Formato** | Markdown; sin hooks de ejecución; revisión humana obligatoria (anti prompt-injection) |
| **Migración** | **Nuevo stub** — distinto de `~/.claude/scheduled-tasks/*/SKILL.md` (invocables) y de `canon/rules/` (normativo global) |

---

## 4. Rename `extractores/` → `extractors/` + inglés interno

### 4.1 Alcance

- Carpeta raíz: `extractores/` → `extractors/`
- Módulos internos: `correo`→`mail`, `reuniones`→`meetings`; paths sistema en inglés (`state.md`, `summaries/`, `drafts/`, `policy.md`, …)
- **Reclasificación:** `job-search` → `loops/job-search/` (no es captura pura de fuente externa)
- Subcarpeta `memory/` sin cambio semántico dentro de cada módulo extractor

### 4.2 Plano `loops/`

| Workflow | Rutina | Paths |
|----------|--------|-------|
| `job-search` | `job-search-crawler` | `inbox.md`, `sources-web/`, `applications.md`, `state.md` (opcional) |

Alineado con constitución §2.2 (Extractors vs Loops).

### 4.3 `.secretary.yml`

```yaml
paths:
  extractors:
    mail:
      memory: extractors/mail/memory
      state: extractors/mail/state.md
      # …
  loops:
    job_search:
      inbox: loops/job-search/inbox.md
      sources_web: loops/job-search/sources-web
      applications: loops/job-search/applications.md

  # Alias deprecated (una release): paths.mail.*, paths.extractores.*, paths.job_search.*
```

Todas las rutinas y skills deben usar `secretary config path <key>` — no hardcodear paths legacy.

### 4.4 Consumidores a actualizar

- `validate_ordenamiento.py`, `validate_paths.py`
- `CLAUDE.md`, `AGENTS.md`, `canon/operational/sorting/sistemas-ordenamiento.md` §2
- Playbooks en `~/.claude/scheduled-tasks/` (texto de PR paths)
- `manifest.yaml`, `inject-heartbeat-freshness.sh`
- Diagramas `_diseño/arquitectura/*.mmd`
- `secretary-core`: rutinas, tests, docs que citen `extractores/`

---

## 5. Relación `extractors/*/memory` vs `knowledge/*` (pipeline ETL)

Regla vigente en `canon/rules/layout/etl.md` — sin cambio semántico, solo paths:

```
Fuente externa
    │
    ▼
extractors/<módulo>/          ← rutina captura (PR auto-*)
    ├── resumenes/ logs/ …    ← evidencia estructurada
    └── memory/               ← entidades, acciones, señales module-local
    │
    │  wiki-update / sec-write / sec-sys-integrate
    ▼
knowledge/
    ├── wiki/articulos/       ← hechos durables destilados
    ├── objectives/           ← intención relacional (vía secd / humano)
    ├── catalog/              ← taxonomías promovidas
    └── indices/ embeddings/  ← derivados generados (no editar a mano)
```

| Zona | Mutabilidad | TTL | Ejemplo |
|------|-------------|-----|---------|
| `extractors/*/memory/` | Append-heavy; rutina del módulo | Días–semanas hasta consolidate | `acciones.md`, `entidades.md` |
| `knowledge/wiki/` | Merge editorial; Bibliotecario | Años | `personas/foo.md` |
| `knowledge/objectives/` | Upsert por id | Meses | `obj-20260610-001.md` |
| `knowledge/indices/` | Regenerado | Horas | `resolver-v1.json` |
| `subsystem/heartbeat/` | Corto plazo operativo | Horas–días | `latest.md` |

**No cruzan dominios:** un extractor no escribe en `knowledge/` directamente (salvo scaffolds `secd` `/signal` → whatsapp memory, que siguen siendo captura).

---

## 6. Integración `secd`: objectives, recall, resolver

| Capacidad secd | Fuente de datos hoy | Destino post-012 |
|----------------|---------------------|------------------|
| `GET /recall?q=` | Wiki articles vía `memory.mjs` (path legacy `wiki/articulos`) | `knowledge/wiki/articulos/` vía YAML |
| Resolver (Axon) | `buildIndex()` RAM desde wiki + `whatsapp/memory/chats.md` | Wiki + **cache** `knowledge/indices/resolver-*.json`; chats siguen en `extractors/whatsapp/memory/` |
| `GET/POST /objectives` | `objetivos/{estrategia,relaciones}/` (scaffold, vacío) | `knowledge/objectives/{strategy,relations}/` o mantener subdirs español **solo dentro** de objectives — ver §10.1 |
| `GET /context` | Compone wiki + actions + objectives | Sin cambio de contrato HTTP; cambian paths internos |
| `/signal`, `/capture` | Scaffold → whatsapp paths | `extractors/whatsapp/…` post-rename |

**Acciones engine (fuera de este spec, listadas para trazabilidad):**

1. `objectives.mjs` → resolver path con `paths.knowledge.objectives` (o CLI)
2. `memory.mjs` → dejar de asumir `wiki/` en raíz de instance
3. `resolver.mjs` → leer/escribir `knowledge/indices/`; invalidar en wiki-update
4. Tests `secd/test/run.mjs` contra instancia con `knowledge/objectives/` poblado

---

## 7. Fases de migración (después de merge #364)

```
✅ 0. #364 — canon/rules/ + operational/ + subsystem/  (mergeado)
         │
         ▼
✅ 1. Fase extractors — git mv extractores/ → extractors/
         YAML paths + aliases extractores
         CI validate_ordenamiento + validate_paths
         Actualizar playbooks rutinas y refs en repo
         │
         ▼
✅ 2. Fase knowledge — git mv memoria/ → knowledge/
         git mv memoria/wiki → knowledge/wiki
         YAML paths.wiki → bajo paths.knowledge.wiki
         migrate_paths.py + wikilinks en docs si aplica
         │
         ▼
✅ 3. Fase KB nuevas — stubs + writers
         knowledge/objectives/ + wire secd (engine follow-up PR)
         knowledge/catalog/, indices/, embeddings/, playbooks/ (README + stubs)
         Actualizar operational/sistemas-ordenamiento §2 allowlist
```

**Orden estricto:** 0 → 1 → 2 → 3. No mezclar fase 1 y 2 en un solo PR (confunde review y rollback).

**Worktree:** cada fase en rama `hilo/012-*`; checkout principal `$SECRETARY_INSTANCE` permanece en `main` (disciplina worktree).

---

## 8. CI / `validate_ordenamiento`

Cambios en `scripts/ci/validate_ordenamiento.py` (post-#364 + 012):

| Validación | Hoy (main) | Post-#364 | Post-012 |
|------------|------------|-----------|----------|
| Raíz allowlist | `doctrines`, `policies`, `extractores`, `memoria`, `operaciones` | `rules`, `operational`, `subsystem`, … | + `extractors`, `knowledge`; − nombres viejos |
| Legacy denylist | `correo/`, `wiki/` en raíz, … | igual | + `extractores/`, `memoria/`, `objetivos/` en raíz |
| Hijos `extractors/` | `validate_extractors()` | módulos `mail`, `meetings`, `whatsapp`, `drive` |
| Hijos `loops/` | — | `validate_loops()` — `job-search` |
| Hijos `knowledge/` | `validate_memoria()` solo `wiki` | — | `wiki`, `objectives`, `catalog`, `indices`, `embeddings`, `playbooks` |
| Hijos `subsystem/` | `validate_operaciones()` | rename | `housekeeping`, `wip`, `heartbeat`, `routines` |

`validate_paths.py`: patrones duplicados `extractores/.../extractores/` → actualizar a `extractors/`.

`validate_wikilinks.py`: sin cambio de resolver lógico; paths de artículos vía YAML.

`migrate_paths.py`: reglas de sustitución para batch en skills/docs externos.

---

## 9. Impacto skills / rutinas

| Consumidor | Impacto |
|------------|---------|
| **Rutinas extractores** (`revision-correo`, `reuniones-update`, `drive-crawler`, `whatsapp-monitor`) | Paths PR `extractors/<módulo>/auto-*`; prompts con rutas absolutas |
| **`job-search-crawler`** | Paths PR `loops/job-search/auto-*` |
| **`wiki-update`** | Lee `extractors/*/memory/`; escribe `knowledge/wiki/`; rebuild `output/` |
| **`sec-heartbeat`** | Lee extractors + `subsystem/heartbeat/`; refs en YAML |
| **`housekeeping`** | `subsystem/housekeeping/` |
| **`secretary-briefing`**, **`pulse`** | Brief + heartbeat; recall paths |
| **Skills `sec-recall`, `sec-write`, `sec-mail`, `sec-meeting`, `sec-compose`** | `secretary config path`; texto de política `operational/sistemas-ordenamiento` |
| **`dispatch-executor`** | Allowlist repos sin cambio; solo si issue cita paths viejos |
| **`pm-trainee`** | Allowlist árbol instance |
| **`secd` + Axon** | objectives, resolver, recall → knowledge/* |
| **`secretary` CLI** | Nuevas claves config; aliases una release |
| **Playbooks `~/.claude/scheduled-tasks/`** | Actualización manual o script migrate_paths en ventana de release |

---

## 10. Sub-decisiones de implementación (cerradas 2026-07-01)

Todas las sub-decisiones de §10 original quedaron **DECIDIDO**. Detalle histórico (opciones A/B/C) conservado en git history de este spec.

| # | Tema | Decisión |
|---|------|----------|
| 10.1.1 | Subdirs objectives | **B/C** — `knowledge/objectives/{strategy,relations}/`; claves YAML `paths.knowledge.objectives.strategy` · `relations` |
| 10.1.2 | Indices en git | **B** — `knowledge/indices/*.json` gitignored; rebuild en boot |
| 10.1.3 | Embeddings | **B** — `manifest.json` stub; sin store vectorial día 1 |
| 10.1.4 | Playbooks vs rules | **C ligera** — README + allowlist CI; `validate_playbooks.py` diferido |
| 10.2.1 | Módulos extractors | **B** — inglés (`mail`, `meetings`, …); paths sistema en inglés; `job-search` → `loops/` |

---

## 11. Alcance — implementado vs follow-up

**En PR 012 (instancia):**

- `git mv` módulos extractors a inglés; `job-search` → `loops/job-search/`
- Stubs KB: `objectives/`, `catalog/`, `indices/`, `embeddings/`, `playbooks/`
- `.secretary.yml` (`paths.extractors.*`, `paths.loops.*`) + aliases; CI; `canon/operational/sorting/sistemas-ordenamiento.md` §2
- Constitución §2 Extractors vs Loops

**Follow-up (secretary-core — pendiente):**

- `secd/lib/objectives.mjs`, `memory.mjs`, `resolver.mjs` — paths vía YAML (`paths.knowledge.*`, `paths.extractors.*`); merge #14 cubrió **modules** CLI, no estos paths
- Skills `~/.claude/scheduled-tasks/` — ventana migrate_paths o manual
- Rebuild wiki HTML (Bibliotecario)

**Legacy en checkout local (no tracked):** `correo/` y `operaciones/routines/` en raíz del árbol principal — denylist CI; logs → `subsystem/routines/`.

---

## Referencias

- Instance PR #364 — `doctrines`→`rules`, `policies`→`operational`, `operaciones`→`subsystem`
- Spec 011 (sistemas-ordenamiento) — permanece en la instancia (no es engine)
- Instance canon: `canon/operational/sorting/sistemas-ordenamiento.md`, `canon/rules/layout/etl.md`
- [`secd/README.md`](../../secd/README.md)
- [`secd/lib/objectives.mjs`](../../secd/lib/objectives.mjs)
- Meeting summaries that informed the design stay in the instance extractor store
