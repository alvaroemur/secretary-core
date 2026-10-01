#!/bin/bash
# Stop hook: extrae memorias de largo plazo de la sesion y las persiste en la wiki personal.
# Gemelo de stop-reflect-claudemd.sh, pero apunta a ~/Cowork/secretary/wiki via el skill wiki-write.
#
# Diferencia clave con el de CLAUDE.md: aqui SI escribe solo (wiki-write es merge-safe e idempotente),
# pero NO commitea ni corre el build -- deja los cambios en el repo de la wiki para que Alvaro revise.
#
# Throttle: maximo una vez cada 30 minutos por directorio de trabajo (lock namespace propio).
# Guard anti-recursion: si la sesion actual ya es un reflect headless, no hacer nada.

set -euo pipefail

# --- Guard anti-recursion: un reflect no debe spawnear otro reflect ---
if [ -n "${CLAUDE_REFLECT_ACTIVE:-}" ]; then
    exit 0
fi

# --- Leer input del hook (JSON por stdin): transcript_path, cwd, stop_hook_active ---
INPUT="$(cat 2>/dev/null || true)"

read_json() {
    python3 -c "import sys,json
try:
    d=json.loads(sys.stdin.read() or '{}')
    print(d.get('$1','') or '')
except Exception:
    print('')" <<<"$INPUT" 2>/dev/null || echo ""
}

TRANSCRIPT_PATH="$(read_json transcript_path)"
CWD_JSON="$(read_json cwd)"
STOP_ACTIVE="$(read_json stop_hook_active)"

if [ "$STOP_ACTIVE" = "True" ] || [ "$STOP_ACTIVE" = "true" ]; then
    exit 0
fi

CWD="${CWD_JSON:-${CLAUDE_CWD:-$(pwd)}}"

WIKI_ROOT="$HOME/Cowork/secretary/wiki"
SKILL_PATH="$HOME/.worksystem/.claude/skills/wiki-write/SKILL.md"

[ -d "$WIKI_ROOT/articulos" ] || exit 0
[ -f "$SKILL_PATH" ] || exit 0

# --- Throttle: no correr si ya se extrajo de este directorio hace menos de 30 min ---
REVIEW_DIR="$HOME/.claude/reviews/wiki"
LOCK_DIR="$REVIEW_DIR/.locks"
mkdir -p "$LOCK_DIR"
LOCK_KEY=$(echo "$CWD" | md5 -q 2>/dev/null || echo "$CWD" | md5sum | cut -d' ' -f1)
LOCK_FILE="$LOCK_DIR/$LOCK_KEY"

if [ -f "$LOCK_FILE" ]; then
    LAST_RUN=$(cat "$LOCK_FILE")
    NOW=$(date +%s)
    ELAPSED=$((NOW - LAST_RUN))
    if [ "$ELAPSED" -lt 1800 ]; then
        exit 0
    fi
fi

# --- Pre-filtro barato: necesitamos un transcript con contenido real ---
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -s "$TRANSCRIPT_PATH" ]; then
    exit 0
fi
LINES=$(wc -l < "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
if [ "$LINES" -lt 8 ]; then
    exit 0
fi

# --- Construir prompt y correr headless en background ---
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$REVIEW_DIR/wiki-reflect-$TIMESTAMP.md"

PROMPT="Eres un extractor de memoria de largo plazo para la wiki personal de Alvaro Mur.

Acabo una sesion de trabajo. Tu unica tarea: destilar de ella los HECHOS DURABLES y persistirlos en la wiki.

Contexto:
- Directorio de trabajo de la sesion: $CWD
- Transcript de la sesion (JSONL): $TRANSCRIPT_PATH
- Procedimiento de escritura OBLIGATORIO: lee y sigue al pie de la letra $SKILL_PATH (skill wiki-write). La raiz de la wiki es $WIKI_ROOT.

Procedimiento:
1. Lee el transcript para entender que paso en la sesion.
2. TRIAGE -- quedate SOLO con memoria de largo plazo, es decir hechos con vigencia mas alla de esta tarea:
   - personas, organizaciones, proyectos/temas y sus relaciones;
   - decisiones, compromisos o definiciones con efecto duradero;
   - preferencias, procesos o convenciones estables que valga la pena recordar.
   DESCARTA: detalles efimeros de la tarea, mecanica de codigo o debugging (eso vive en git/CLAUDE.md),
   pasos one-off, y cualquier cosa que no vayas a querer recordar dentro de un mes.
3. Si NO hay nada durable, escribe una sola linea 'Nada que persistir' y termina. Mejor no escribir que meter ruido.
4. Para cada hecho durable, identifica el articulo destino (persona/organizacion/tema) y aplica wiki-write:
   - Usa un fuente_id ESTABLE por articulo: 'sesiones'. Asi las corridas futuras mergean en el mismo bloque auto.
   - CUMULATIVO: al actualizar el bloque <!-- auto:sesiones --> de un articulo, PRESERVA los hechos que ya estaban
     y ANADE los nuevos. Nunca borres hechos previos (solo ves el transcript de hoy, no el historico).
   - Sintetiza en tercera persona neutra, castellano con tuteo (nunca voseo). No copies texto literal de fuentes.
   - Registra el cambio en $WIKI_ROOT/memory/indice.md como indica el skill.
5. Maximo 3 articulos por sesion. Si hay mas candidatos, prioriza los mas relevantes.

PROHIBIDO: ejecutar build, hacer git add/commit/push, borrar articulos, o tocar contenido fuera de bloques auto.
Deja los cambios sin commitear en el repo de la wiki; Alvaro los revisa.

Al final, reporta en <=15 lineas: que articulos tocaste, que hechos anadiste, y advertencias."

(
    CLAUDE_REFLECT_ACTIVE=1 claude --print --permission-mode auto \
        --add-dir "$WIKI_ROOT" \
        --add-dir "$(dirname "$TRANSCRIPT_PATH")" \
        --add-dir "$(dirname "$SKILL_PATH")" \
        -p "$PROMPT" > "$LOG_FILE" 2>/dev/null || true

    if [ -s "$LOG_FILE" ]; then
        if grep -qi "nada que persistir" "$LOG_FILE" && [ "$(wc -l < "$LOG_FILE")" -le 3 ]; then
            rm -f "$LOG_FILE"
        fi
    else
        rm -f "$LOG_FILE"
    fi
) &

date +%s > "$LOCK_FILE"

exit 0
