#!/bin/bash
# SessionStart hook: report git sync status across tracked repos.
# Emits a row when: any of (ahead/behind/dirty) != 0, OR branch is non-main.
# Output grouped by plano: Dev/ = código, Cowork/ = gestión.
# For non-main branches, queries gh to show open/merged PR status.

REPOS=(
    # doc2struct + submódulos
    "$HOME/Dev/doc2struct"
    "$HOME/Dev/doc2struct/doc2struct-go"
    "$HOME/Dev/doc2struct/aliantza-compras-python"
    "$HOME/Dev/doc2struct/doc2struct_eval"

    # otros productos técnicos en Dev/
    "$HOME/Dev/clab-admin-rpa"
    "$HOME/Dev/inspiro-agents"
    "$HOME/Dev/workwatch"
    "$HOME/Dev/ennui-solutions-web"

    # workspaces gestión (Cowork/)
    "$HOME/Cowork/inspiro"
    "$HOME/Cowork/ennui"

    # sistema secretary
    "$HOME/Dev/secretary-core"
    "$HOME/.secretary"
)

# Per-plano accumulators (bash 3.2 has no associative arrays).
DEV_OUT=""
COWORK_OUT=""
SECRETARY_OUT=""
OTHER_OUT=""

# Fixed column widths.
NAMEW=24
BRANCHW=20

# Validador de paquetes Spec Kit (cowork-secretary#1146). Mismo criterio que CI; solo
# corre en repos con .specify/ y si el validador y PyYAML están disponibles.
SPECIFY_VALIDATOR="$HOME/.secretary/scripts/ci/validate_specify.py"
SPECIFY_READY=false
[ -f "$SPECIFY_VALIDATOR" ] && python3 -c 'import yaml' 2>/dev/null && SPECIFY_READY=true

for dir in "${REPOS[@]}"; do
    [ -d "$dir/.git" ] || [ -f "$dir/.git" ] || continue
    name=$(basename "$dir")
    cd "$dir" || continue
    git fetch --quiet 2>/dev/null

    branch=$(git branch --show-current 2>/dev/null || echo "?")
    ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
    behind=$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "?")
    dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
    # Drift contra main (no contra el upstream de la rama): el número que importa
    # para la frescura de lecturas. Una rama vieja lee estado pasado.
    main_ref=$(git rev-parse --verify --quiet origin/main >/dev/null 2>&1 && echo origin/main || echo origin/master)
    behind_main=$(git rev-list --count "HEAD..$main_ref" 2>/dev/null || echo "0")

    # Determine if we're on a "trunk" branch (main/master).
    on_trunk=false
    [[ "$branch" == "main" || "$branch" == "master" ]] && on_trunk=true

    # Paquete Spec Kit incompleto. Un repo sin .specify/ es lo normal (alcance bajo demanda).
    specify_note=""
    if $SPECIFY_READY && [ -d "$dir/.specify" ]; then
        python3 "$SPECIFY_VALIDATOR" "$dir" >/dev/null 2>&1 || specify_note="  ⚠️ Spec Kit incompleto (validate_specify.py)"
    fi

    # Skip if perfectly clean, synced, and on trunk.
    if $on_trunk && [ "$ahead" = "0" ] && [ "$behind" = "0" ] && [ "$dirty" = "0" ] && [ -z "$specify_note" ]; then
        continue
    fi

    # PR status — only meaningful for non-trunk branches.
    pr_info=""
    if ! $on_trunk && [ -n "$branch" ] && [ "$branch" != "?" ]; then
        open_pr=$(timeout 5 gh pr list --head "$branch" --json number,isDraft --limit 1 2>/dev/null)
        if [ -n "$open_pr" ] && [ "$open_pr" != "[]" ]; then
            pr_num=$(printf '%s' "$open_pr" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'])" 2>/dev/null)
            is_draft=$(printf '%s' "$open_pr" | python3 -c "import sys,json; d=json.load(sys.stdin); print('draft' if d[0]['isDraft'] else 'open')" 2>/dev/null)
            pr_info="  PR=#${pr_num}(${is_draft})"
        else
            merged_pr=$(timeout 5 gh pr list --head "$branch" --state merged --json number --limit 1 2>/dev/null)
            if [ -n "$merged_pr" ] && [ "$merged_pr" != "[]" ]; then
                pr_num=$(printf '%s' "$merged_pr" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'])" 2>/dev/null)
                pr_info="  PR=#${pr_num}(mergeado — poda OK)"
            else
                pr_info="  (sin PR)"
            fi
        fi
    fi

    # WIP note from last session, if exists.
    wip_file="$HOME/.secretary/wip/${name}.md"
    wip_note=""
    if [ -f "$wip_file" ]; then
        wip_note=$(grep -A1 "^## WIP" "$wip_file" 2>/dev/null | tail -1 | sed 's/^[[:space:]]*//')
        [ -n "$wip_note" ] && wip_note="  WIP: ${wip_note}"
    fi

    # Aviso de frescura: rama no-trunk atrás de main → las lecturas de estado
    # desde el working tree mienten (leen el pasado).
    main_note=""
    if ! $on_trunk && [ "$behind_main" != "0" ]; then
        main_note="  ⚠️ ${behind_main} detrás de main (lecturas stale)"
    fi

    # Real trailing newline via $'\n'.
    row=$(printf "  %-${NAMEW}s [%-${BRANCHW}s]  ahead=%s behind=%s dirty=%s%s%s%s%s" \
        "$name" "$branch" "$ahead" "$behind" "$dirty" "$pr_info" "$wip_note" "$main_note" "$specify_note")

    case "$dir" in
        "$HOME/.secretary"|"$HOME/.secretary/"*) SECRETARY_OUT="${SECRETARY_OUT}${row}"$'\n' ;;
        "$HOME/Dev/"*)        DEV_OUT="${DEV_OUT}${row}"$'\n' ;;
        "$HOME/Cowork/"*)     COWORK_OUT="${COWORK_OUT}${row}"$'\n' ;;
        *)                    OTHER_OUT="${OTHER_OUT}${row}"$'\n' ;;
    esac
done

# Print only non-empty planos, each under a visual header.
if [ -n "$DEV_OUT" ] || [ -n "$COWORK_OUT" ] || [ -n "$SECRETARY_OUT" ] || [ -n "$OTHER_OUT" ]; then
    printf "repo sync check:\n"
    [ -n "$DEV_OUT" ]       && { printf "Dev/ (código)\n";         printf "%s" "$DEV_OUT"; }
    [ -n "$COWORK_OUT" ]    && { printf "Cowork/ (gestión)\n";     printf "%s" "$COWORK_OUT"; }
    [ -n "$SECRETARY_OUT" ] && { printf ".secretary/ (sistema)\n"; printf "%s" "$SECRETARY_OUT"; }
    [ -n "$OTHER_OUT" ]     && { printf "Otros\n";                 printf "%s" "$OTHER_OUT"; }
fi

exit 0
