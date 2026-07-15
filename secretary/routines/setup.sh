#!/usr/bin/env bash
# Thin wrapper — canonical setup lives in secretary-core CLI (`secretary routines setup`).
set -euo pipefail

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
export SECRETARY_INSTANCE="$INSTANCE"
exec secretary routines setup "$@"
