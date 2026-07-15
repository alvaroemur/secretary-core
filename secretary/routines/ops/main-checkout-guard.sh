#!/usr/bin/env bash
# Detecta cambios tracked en main fuera de subsystem/heartbeat/.
# Uso: main-checkout-guard.sh [repo]
#   stdout: líneas porcelain (una por path sucio) o vacío si limpio
#   exit 0 = limpio para heartbeat; exit 1 = bloqueado
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

REPO="${1:-${SECRETARY_INSTANCE:-$HOME/.secretary}}"

cd "$REPO"
DIRTY="$(git status --porcelain)"
NON_HB="$(printf '%s\n' "$DIRTY" | grep -v '^??' | grep -v ' subsystem/heartbeat/' | grep -v '^$' || true)"

if [[ -n "$NON_HB" ]]; then
  printf '%s\n' "$NON_HB"
  exit 1
fi

exit 0
