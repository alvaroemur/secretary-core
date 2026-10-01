#!/bin/bash
# Stop hook: propone actualizaciones a CLAUDE.md tras cada sesión.
# Throttle: máximo una vez cada 30 minutos por directorio de trabajo.
# Corre una sesión headless de Claude que revisa cambios y sugiere updates.

set -euo pipefail

# --- Guard anti-recursion: un reflect headless no debe spawnear otro reflect ---
if [ -n "${CLAUDE_REFLECT_ACTIVE:-}" ]; then
    exit 0
fi

REVIEW_DIR="$HOME/.claude/reviews"
mkdir -p "$REVIEW_DIR"

CWD="${CLAUDE_CWD:-$(pwd)}"

# --- Throttle: no correr si ya se revisó este directorio hace menos de 30 min ---
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

# --- Detectar cambios ---
find_git_root() {
    local dir="$1"
    while [ "$dir" != "/" ]; do
        [ -d "$dir/.git" ] || [ -f "$dir/.git" ] && echo "$dir" && return
        dir=$(dirname "$dir")
    done
}

GIT_ROOT=$(find_git_root "$CWD")
CHANGED_FILES=""
CLAUDE_MDS=""

if [ -n "$GIT_ROOT" ]; then
    CHANGED_FILES=$(cd "$GIT_ROOT" && git diff --name-only 2>/dev/null; git diff --name-only --cached 2>/dev/null)
    if [ -z "$CHANGED_FILES" ]; then
        CHANGED_FILES=$(cd "$GIT_ROOT" && git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
    fi
    CLAUDE_MDS=$(find "$GIT_ROOT" -maxdepth 3 -name "CLAUDE.md" 2>/dev/null | head -10)
else
    CLAUDE_MDS=$(find "$CWD" -maxdepth 3 -name "CLAUDE.md" 2>/dev/null | head -10)
fi

# Sin cambios reales → no gastar una sesión headless
if [ -z "$CHANGED_FILES" ]; then
    exit 0
fi

# --- Construir prompt y correr ---
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REVIEW_FILE="$REVIEW_DIR/claudemd-review-$TIMESTAMP.md"

PROMPT="Eres un revisor de CLAUDE.md. Analiza los archivos que cambiaron y los CLAUDE.md existentes.

Directorio de trabajo: $CWD

Archivos modificados:
$CHANGED_FILES

CLAUDE.md encontrados:
$CLAUDE_MDS

Tu tarea:
1. ¿Algún CLAUDE.md existente necesita actualizarse por los cambios hechos? (nueva convención, estructura que cambió, comando nuevo, etc.)
2. ¿Falta un CLAUDE.md en algún directorio que ahora lo necesita?
3. ¿Alguna instrucción existente quedó obsoleta?

Si no hay cambios necesarios, di 'Sin cambios necesarios' y explica brevemente por qué.
Si hay cambios, lista cada uno con: archivo, sección, cambio propuesto.

Sé conciso. Máximo 30 líneas."

# Sesión headless en background para no bloquear.
# permission-mode auto (clasificador por accion) en vez de skip-permissions; dirs acotados.
ADD_DIRS=(--add-dir "$CWD" --add-dir "$REVIEW_DIR")
[ -n "$GIT_ROOT" ] && ADD_DIRS+=(--add-dir "$GIT_ROOT")

(CLAUDE_REFLECT_ACTIVE=1 claude --print --permission-mode auto "${ADD_DIRS[@]}" -p "$PROMPT" > "$REVIEW_FILE" 2>/dev/null || true

# Limpiar si no produjo contenido útil
if [ -s "$REVIEW_FILE" ]; then
    LINE_COUNT=$(wc -l < "$REVIEW_FILE")
    [ "$LINE_COUNT" -le 2 ] && rm -f "$REVIEW_FILE"
else
    rm -f "$REVIEW_FILE"
fi) &

# Registrar timestamp del lock
date +%s > "$LOCK_FILE"

exit 0
