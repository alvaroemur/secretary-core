# Shared path layout for secretary/routines (phase 1 package).
# Source from any script under this tree:
#   # shellcheck source=_layout.sh
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_layout.sh"          # root
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"       # subdir
# shellcheck shell=bash

export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
# Prefer the repo that contains this file when SECRETARY_CORE is unset
_layout_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_core_guess="$(cd "$_layout_dir/../.." && pwd)"
export SECRETARY_CORE="${SECRETARY_CORE:-$_core_guess}"
export SECRETARY_ROUTINES_ROOT="${SECRETARY_ROUTINES_ROOT:-$_layout_dir}"

export ROUTINES_ROOT="$SECRETARY_ROUTINES_ROOT"
export ROUTINES_INVOKE="$ROUTINES_ROOT/invoke"
export ROUTINES_METRICS="$ROUTINES_ROOT/metrics"
export ROUTINES_OPS="$ROUTINES_ROOT/ops"
export ROUTINES_BACKFILL="$ROUTINES_ROOT/backfill"

INSTANCE="$SECRETARY_INSTANCE"
CORE="$SECRETARY_CORE"
