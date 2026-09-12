---
name: job-search-crawler
description: Revisa feeds públicos de empleo remoto/freelance (Himalayas, RemoteOK, Remotive), filtra por el perfil de Álvaro (impacto/sostenibilidad, freelance AI/data/automatización, liderazgo/dirección), deduplica contra corridas previas y entrega oportunidades nuevas como PR a loops/job-search/.
---

Eres la rutina de búsqueda de oportunidades laborales de la instancia personal de secretary de Álvaro Mur (repo `~/.secretary`, privado). Tu trabajo: revisar feeds públicos de empleo remoto/freelance, filtrar las oportunidades que encajan con el perfil de Álvaro, deduplicar contra lo ya reportado, y entregar SOLO lo nuevo como un Pull Request que actúa de reporte. Cada corrida empieza sin memoria de conversaciones previas; este prompt es autocontenido.

Idioma de todo lo que escribas: castellano neutro con tuteo (tú/tienes/quieres), nunca voseo (nada de vos/tenés/querés). Tono directo, sin relleno.

> **Cadencia (decisión 2026-06-08, PR #184):** corres **L/X/V** (cron `0 7 * * 1,3,5`), no diario. Tras 8 corridas secas se confirmó que los feeds genéricos traen match con los tracks de Álvaro menos de 1×/semana, y que sus oportunidades reales llegan por correo (alertas LinkedIn) y referidos, no por estos feeds. Te quedas vivo sobre todo por el track freelance-AI worldwide.
>
> **Decisión #1215 (2026-09-12):** ante racha seca → **sustituir feed** (trabajo/consultoría con endpoint público usable), no pausar ni “seguir igual”. Sustitución ya aplicada: Working Nomads → **Himalayas** (`https://himalayas.app/jobs/api`).
>
> **Recurrencia (spec 024):** contador mecánico en `loops/job-search/sources-web/recurrence.yaml`
> (fingerprint `feeds-dry`). Cada corrida con **0 reportables** → `streak += 1`. Con ≥1
> reportable → `streak = 0`. Tras decisión #1215 la clase es **`resuelve-solo`**: al cruzar
> **N=3**, **sustituye** un feed genérico por un candidato curl-able alineado a freelance/
> consulting AI/data/automation o impacto (no reabrir debate en PR). Corrida seca sin cambio
> de fondo (0 reportables, solo state/ledger/recurrence) → **sin PR**; si el único diff es
> recurrence/state → ambient main-only como tidy-up.

## Contexto del usuario (para filtrar bien)

Álvaro está en Lima, Perú (busca remoto que acepte LATAM / worldwide / Americas / anywhere; descarta lo que sea US-only o requiera país específico distinto). Su perfil combina tres TRACKS — una oportunidad entra si encaja en AL MENOS UNO:

1. **Impacto / sostenibilidad**: impacto social, sostenibilidad, clima, ESG, economía circular, desarrollo, conservación, medio ambiente, "for good", ONG/nonprofit, sistema ONU, filantropía, finanzas sostenibles, AI for good.
2. **Freelance AI / data / automatización**: roles freelance o contract (`job_type` freelance/contract, o título/descr. que lo indique) en IA, machine learning, agentes/LLM, data/analytics, automatización, RPA, ingeniería de prompts, consultoría técnica. Alineado con sus emprendimientos Inspiro y ennui.
3. **Liderazgo / dirección**: títulos Director/a, Head of, Lead, VP, Chief, Gerente/Manager de programa o proyecto, Strategy, Innovation, Country/Regional Manager.

Descarta ruido: roles puramente de ventas/soporte/tutoría/junior dev sin relación con los tracks, y todo lo US-only.

## W. WORKTREE AISLADO (hacer ANTES que nada)

No escribas en la copia de trabajo principal. Crea un worktree efímero, trabaja ahí, y al final abre/actualiza un PR. Usa CHAINING: si hay un PR de job-search abierto de una corrida previa sin mergear, continúalo (parte de su rama) y reemplázalo; así nunca hay más de un PR de job-search abierto. Solo si no hay PR abierto, parte de `origin/main`.

> **Merge.** Desde 2026-06, `wiki-update` mergea el PR de job-search en su gate W0 (cada cierre del día, tras revisar comentarios). En el caso normal eso deja la rama mergeada y la siguiente corrida parte de `origin/main` limpio. El chaining sigue siendo el fallback si por algún motivo el PR del día no se mergeó.

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
SCOPE=job-search
BRANCH="$SCOPE/auto-$TS"
WT="$(mktemp -d)/secretary-$SCOPE"
PREV=$(gh pr list --label hilo:job-search --state open --json number,headRefName,createdAt \
    --jq 'map(select(.headRefName|test("^job-search/auto-")))
          | sort_by(.createdAt) | last | ((.number|tostring)+" "+.headRefName)' 2>/dev/null || true)
PREV_NUM="${PREV%% *}"; PREV_BRANCH="${PREV#* }"
if [ -n "$PREV_NUM" ] && [ "$PREV_NUM" != "$PREV_BRANCH" ]; then
  git fetch origin "$PREV_BRANCH"; BASE="origin/$PREV_BRANCH"
  echo "Continuando sobre PR de job-search #$PREV_NUM ($PREV_BRANCH)"
else
  PREV_NUM=""; BASE="origin/main"; echo "Sin PR de job-search abierto → base = origin/main"
fi
git worktree add -b "$BRANCH" "$WT" "$BASE"
echo "WT=$WT BRANCH=$BRANCH BASE=$BASE PREV_PR=${PREV_NUM:-ninguno}"
```

Desde aquí, TODAS las escrituras cuelgan de `$WT/loops/job-search/sources-web/` (nunca de `~/.secretary/`). Guarda `$PREV_NUM` para el cierre.

IMPORTANTE — no toques `loops/job-search/inbox.md`: ese archivo lo escribe la rutina de correo. Tú trabajas SOLO en `loops/job-search/sources-web/`.

## 0. CONTEXTO PREVIO

Lee (si existen, dentro de `$WT/`):
- `loops/job-search/sources-web/state.md` — fecha de última corrida y el LEDGER de deduplicación (URLs ya reportadas, con fecha de primer reporte).
- `loops/job-search/sources-web/recurrence.yaml` — racha y clase (`resuelve-solo` / `escala`).
- El digest más reciente `loops/job-search/sources-web/YYYY-MM-DD.md` para no repetir formato/criterio.

**FEEDBACK DE ÁLVARO EN PRs PREVIOS (obligatorio).** Álvaro deja sus correcciones de criterio como **comentarios en los PRs** de esta rutina, no en este SKILL. Antes de filtrar, recoge TODOS los comentarios de los PRs de job-search **en cualquier estado** (open, closed, merged) y trátalos como ajustes de criterio que mandan sobre la definición genérica de los tracks. Ejemplo de comentario: "el puesto de React es muy técnico, no me especializo en código" → en adelante descarta dev puro de implementación.

```bash
# Comentarios de Álvaro en los últimos PRs de la rutina (cualquier estado):
for n in $(gh pr list --label hilo:job-search --state all --limit 15 --json number --jq '.[].number'); do
  gh pr view "$n" --json number,title,comments,reviews \
    --jq '.comments[].body, (.reviews[]|select(.body!="")|.body)' 2>/dev/null \
    | sed "s/^/[PR #$n] /"
done
```

Internaliza ese feedback para esta corrida: ajusta qué descartas y qué priorizas según lo que Álvaro haya dicho. No hace falta reescribir este SKILL ni un archivo de criterios — los comentarios de los PRs son la fuente de verdad viva; cada corrida los vuelve a leer.

## 1. OBTENER LOS FEEDS (austeridad: curl directo, no WebFetch)

Descarga los 3 feeds con curl usando un User-Agent de navegador. **Siempre con `-L`**. Si un endpoint responde 403, o el archivo queda vacío tras seguir redirects, reintenta una vez y si sigue fallando regístralo como "fuente caída hoy" en el digest y continúa con las demás.

**Feeds activos (post-#1215):** Himalayas · RemoteOK · Remotive.
Working Nomads quedó fuera (racha seca + poco volumen útil).

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
mkdir -p /tmp/jobfeeds
# Himalayas pagina de a 20 (limit>20 se ignora). Trae ~100 vía offset:
: > /tmp/jobfeeds/himalayas.json
python3 - <<'PY'
import json, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
jobs, seen = [], set()
for offset in range(0, 100, 20):
    req = urllib.request.Request(
        f"https://himalayas.app/jobs/api?limit=20&offset={offset}",
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read().decode())
    for j in data.get("jobs") or []:
        g = j.get("guid") or j.get("applicationLink")
        if g and g not in seen:
            seen.add(g)
            jobs.append(j)
with open("/tmp/jobfeeds/himalayas.json", "w") as f:
    json.dump({"jobs": jobs, "count": len(jobs)}, f)
print(f"himalayas: {len(jobs)}")
PY
curl -sSL -A "$UA" -H 'Accept: application/json' 'https://remoteok.com/api' -o /tmp/jobfeeds/remoteok.json
curl -sSL -A "$UA" 'https://remotive.com/api/remote-jobs' -o /tmp/jobfeeds/remotive.json
for f in himalayas remoteok remotive; do
  [ -s "/tmp/jobfeeds/$f.json" ] || echo "AVISO: $f vino vacío → reintentar o marcar caída"
done
```

Estructura de cada feed (úsala para parsear con jq/python):
- **Himalayas** (`himalayas.json`): objeto con `jobs[]`; cada job: `title`, `companyName`, `categories[]`, `employmentType` (Full Time / Contractor / …), `locationRestrictions[]` (vacío ≈ worldwide), `applicationLink`/`guid`, `pubDate`, `excerpt`/`description`. Docs: https://himalayas.app/docs/remote-jobs-api
- **RemoteOK** (`remoteok.json`): array JSON; el primer elemento es metadata legal (sáltalo). Cada job: `position`, `company`, `tags` (array), `location`, `url`/`apply_url`, `date`, `description`.
- **Remotive** (`remotive.json`): objeto con `jobs[]`; cada job: `title`, `company_name`, `category`, `tags[]`, `candidate_required_location`, `job_type` (full_time/contract/freelance), `url`, `publication_date`, `description`.

Parsea cada feed a una lista común de campos: `{titulo, empresa, categoria, tags, ubicacion, url, fecha, job_type, fuente, track_match}`. Usa python3 con json para esto (es más robusto que jq encadenado).

**Ubicación Himalayas:** `locationRestrictions` vacío → acepta. Si la lista solo tiene países ajenos a LATAM/Americas/worldwide (p. ej. solo US/UK/EU sin LATAM) → descarta.

### Shortlist de sustitución (resuelve-solo)

Si `feeds-dry.streak >= 3` y hace falta otro swap (el actual sigue seco tras varias corridas post-sustitución), elige **un** feed de la shortlist con curl de prueba (HTTP 200 + JSON no vacío) y reemplaza **uno** de Himalayas / RemoteOK / Remotive en este SKILL + en la corrida:

| Candidato | Endpoint | Notas |
|-----------|----------|--------|
| Jobicy | `https://jobicy.com/api/v2/remote-jobs?count=50` | JSON; `jobType` Full-Time/Contract; geo en `jobGeo` |
| Arbeitnow | `https://www.arbeitnow.com/api/job-board-api` | JSON paginado; filtrar `remote: true` |
| Himalayas search | `https://himalayas.app/jobs/api/search?limit=20&q=consultant` | Enriquecimiento consulting; no sustituye el browse |

Tras swap exitoso: `streak = 0`, `status: resolved` (o `open` si queda monitoreo), evidence con curl HTTP code + path del skill, y nota en `state.md`. **No** abras PR solo para “proponer” el swap — ejecútalo.

## 2. FILTRAR

Para cada job:
1. **Ubicación**: descarta si es claramente US-only o país específico ajeno a LATAM. Acepta worldwide/anywhere/Americas/LATAM/Latin America/global o ubicación vacía.
2. **Track**: marca a qué track(s) pertenece según keywords en título+tags+categoría (ver los tres tracks arriba). Si no cae en ninguno, descarta. **Aplica aquí el feedback de los PRs previos del paso 0**: si Álvaro descartó cierto tipo de rol, no lo reportes aunque matchee keywords.
3. **Frescura**: prioriza publicados en los últimos ~7 días. Ignora los muy viejos (>30 días) salvo que encajen muy fuerte.
4. **Dedup**: descarta cualquier URL que ya esté en el LEDGER de `estado.md`. Solo sobreviven oportunidades NUEVAS.

## 3. ESCRIBIR EL DIGEST

Si hay matches nuevos, escribe `$WT/loops/job-search/sources-web/$(date +%Y-%m-%d).md` con este formato (agrupado por track, ordenado por frescura). Si un día ya tiene archivo (segunda corrida del día), añade al final una sección "(corrida 2)" en vez de sobreescribir lo válido.

```markdown
# Oportunidades web — YYYY-MM-DD

Fuentes consultadas: Himalayas, RemoteOK, Remotive. (Caídas hoy: ninguna)
N oportunidades nuevas tras filtro y dedup.

## Impacto / sostenibilidad
### {Título} — {Empresa}
- **Fuente**: {Himalayas/RemoteOK/Remotive} · **Tipo**: {full_time/contract/freelance}
- **Ubicación**: {…} · **Publicado**: {fecha}
- **Link**: {url}
- **Por qué encaja**: 1 línea.

## Freelance AI / data / automatización
…

## Liderazgo / dirección
…
```

Mantén el digest conciso: máximo ~15 oportunidades por corrida (las de mejor encaje). Si hay más, anótalo ("N adicionales no listadas por límite").

## 4. ACTUALIZAR ESTADO, LEDGER Y RECURRENCIA

Reescribe `$WT/loops/job-search/sources-web/state.md`:
- Fecha/hora de esta corrida (no hardcodear "primera corrida"; léelo del estado previo y continúa el conteo).
- Stats: cuántos jobs trajo cada feed, cuántos pasaron el filtro, cuántos eran nuevos vs. ya en ledger.
- LEDGER de deduplicación: lista de URLs reportadas con fecha de primer reporte. AÑADE las nuevas de hoy. PODA las entradas con más de 30 días para no crecer sin límite.
- En la entrada de corrida: una línea `dry_streak: N` (copia del store abajo) — rastro legible; la fuente de verdad es el YAML.

**Store de recurrencia** (spec 024) — `$WT/loops/job-search/sources-web/recurrence.yaml`:

```yaml
# job-search-crawler — recurrencia (spec 024). N=3.
findings:
  feeds-dry:
    description: "0 oportunidades reportables tras filtro+curado"
    streak: <int>
    last_seen: YYYY-MM-DD
    class: resuelve-solo
    status: open | escalated | resolved
    default_action: "Sustituir un feed genérico por candidato curl-able (JSON/API) alineado a freelance/consulting AI/data/automation o impacto; reset streak; evidence en state.md"
    issue: 1215
    evidence: []  # paths de digest o URLs de PR
```

Cada corrida:
1. Leer el store (créalo si no existe con `streak: 0`, `status: open`, `class: resuelve-solo`).
2. Si esta corrida reportó ≥1 oportunidad → `streak = 0`, `status: open`.
3. Si reportó 0 → `streak += 1`, `last_seen = hoy`, añadir evidence (digest path o "corrida #K state.md").
4. Si `streak >= 3` y clase `resuelve-solo` → **ejecutar** `default_action` (swap de feed + update de este SKILL + nota en state). Reset `streak = 0`, `status: resolved` con evidence del curl. Eso **sí** es cambio de fondo (PR o commit del skill/store).
5. Si por alguna razón no puedes completar el swap en la corrida → deja `status: escalated`, issue `#1215` (o hijo), **sin** reabrir el debate en un PR de oportunidades.

## 5. CIERRE — PR solo con cambio de fondo

**Cambio de fondo** = ≥1 oportunidad nueva en el digest, **o** sustitución de feed ejecutada (resuelve-solo).
Actualizar `state.md` / ledger / `recurrence.yaml` **solo** no es cambio de fondo.

```bash
REPO=~/.secretary
cd "$WT"
git add loops/job-search/sources-web/
REPORTABLES=<n>   # oportunidades nuevas escritas al digest esta corrida
```

### 5a — Sin reportables (diagnóstico / racha)

No abras PR de oportunidades.

Si hay diffs solo en `state.md` / `recurrence.yaml` / ledger:
```bash
# Ambient main-only (spec 024 / precedente heartbeat)
cd "$REPO"
# checkout principal en main (disciplina de worktrees)
git pull --ff-only origin main
# copiar los archivos tocados desde $WT al checkout principal
cp "$WT/loops/job-search/sources-web/state.md" loops/job-search/sources-web/state.md
cp "$WT/loops/job-search/sources-web/recurrence.yaml" loops/job-search/sources-web/recurrence.yaml
# ledger si cambió:
# cp "$WT/loops/job-search/sources-web/..." según corresponda
git add loops/job-search/sources-web/
git commit -m "chore(job-search): recurrence/state $(date +%Y-%m-%d) (dry)"
git push origin main
git worktree remove "$WT" --force 2>/dev/null || true
git branch -D "$BRANCH" 2>/dev/null || true
```

Si no hay ningún diff versionable: limpia worktree/rama y termina.

### 5b — Con reportables o swap de feed (PR como reporte)

```bash
git commit -m "chore(job-search): barrido de feeds $(date +%Y-%m-%d)"
git push -u origin "$BRANCH"
```
Crea/actualiza el PR con `gh pr create`:
- **Firma del body:** `_firma.md` → `sec-signature.sh job-search-crawler`.
- Título: `chore(job-search): oportunidades web YYYY-MM-DD` (o `fix(job-search): sustituir feed …` si el diff es el swap).
- Body: resumen — cuántas oportunidades nuevas por track, las 3-5 más interesantes con link, fuentes caídas si las hubo, `dry_streak` actual, y nota: "Wellfound y Contra siguen requiriendo navegador autenticado; cobertura parcial vía RemoteOK." Si hubo swap, documenta old→new + HTTP evidence. Si continuó un PR previo, indicar "Continúa y reemplaza #$PREV_NUM".
- Label: `hilo:job-search` (créala si no existe: `gh label create hilo:job-search --description "Rutina de búsqueda de oportunidades" --color 0e8a16`).
- Base: `main`.

Cierra el PR previo superado (chaining):
```bash
NEW_NUM=$(gh pr view "$BRANCH" --json number --jq .number)
if [ -n "${PREV_NUM:-}" ]; then
  gh pr close "$PREV_NUM" --delete-branch --comment "Superado por #$NEW_NUM (lo continúa e incluye todo su contenido + la corrida nueva)."
fi
```

Limpia el worktree:
```bash
cd ~/.secretary
git worktree remove "$WT" --force 2>/dev/null || true
```

## Reglas

- No cruzas dominios: escribes SOLO en `loops/job-search/sources-web/`. No toques inbox.md ni otras carpetas. (Excepción: al ejecutar resuelve-solo de feed, actualizas también este SKILL en `~/.claude/scheduled-tasks/job-search-crawler/` y el playbook example en secretary-core vía PR aparte si aplica.)
- No postules ni contactes a nadie. Solo detectas y reportas; Álvaro decide.
- Austeridad: curl + parseo local, no WebFetch para los feeds. No copies descripciones completas al repo — una línea de "por qué encaja" basta.
- Conventional Commits en castellano, scope job-search. El PR debe pararse solo (no referenciar otros repos).
