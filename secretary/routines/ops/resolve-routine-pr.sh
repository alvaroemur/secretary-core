#!/usr/bin/env bash
# Resolve PR linked to a routine run. Source from invoke-*.sh before parse-routine-metrics.
# Sets: ROUTINE_PR_NUMBER, ROUTINE_PR_URL, ROUTINE_HEAD_BRANCH, ROUTINE_PR_REPO
# usage: source resolve-routine-pr.sh <routine_id> <log_path> [workspace]
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

_resolve_pr_main() {
  local routine_id="${1:-}"
  local log_path="${2:-}"
  local workspace="${3:-${SECRETARY_INSTANCE:-$HOME/.secretary}}"

  if [[ -n "${ROUTINE_PR_NUMBER:-}" ]]; then
    return 0
  fi

  local repo_full="${ROUTINE_PR_REPO_FULL:-}"
  if [[ -z "$repo_full" ]] && command -v git >/dev/null 2>&1; then
    local remote
    remote="$(git -C "$workspace" remote get-url origin 2>/dev/null || true)"
    repo_full="$(printf '%s' "$remote" | sed -E 's#^git@github.com:##; s#^https://github.com/##; s#\.git$##')"
  fi
  repo_full="${repo_full:-alvaroemur/cowork-secretary}"
  local repo_slug="${repo_full##*/}"
  local owner="${repo_full%%/*}"

  local branch="${ROUTINE_HEAD_BRANCH:-${SECRETARY_BRANCH:-}}"
  local pr_url="${ROUTINE_PR_URL:-${PR_URL:-}}"
  local pr_number="${PR_NUMBER:-}"

  if [[ -f "$log_path" ]]; then
    if [[ -z "$branch" || "$branch" == "main" ]]; then
      local from_log
      from_log="$(grep -Eo 'BRANCH=[^[:space:]]+' "$log_path" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
      if [[ -n "$from_log" && "$from_log" != "main" ]]; then
        branch="$from_log"
      fi
    fi
    if [[ -z "$pr_url" ]]; then
      pr_url="$(grep -Eo 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' "$log_path" 2>/dev/null | tail -1 || true)"
    fi
  fi

  if [[ -n "$pr_url" && -z "$pr_number" ]]; then
    pr_number="$(printf '%s' "$pr_url" | sed -E 's#.*/pull/([0-9]+).*#\1#')"
  fi

  if [[ -n "$pr_number" && -z "$pr_url" ]] && command -v gh >/dev/null 2>&1; then
    pr_url="$(gh pr view "$pr_number" --repo "$repo_full" --json url --jq .url 2>/dev/null || true)"
  fi

  if [[ -z "$pr_number" && -n "$branch" && "$branch" != "main" ]] && command -v gh >/dev/null 2>&1; then
    local json
    json="$(gh pr list --repo "$repo_full" --state all --head "${owner}:${branch}" \
      --json number,url,headRefName,state,createdAt --limit 1 2>/dev/null || true)"
    if [[ -n "$json" && "$json" != "[]" ]]; then
      pr_number="$(printf '%s' "$json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["number"] if d else "")' 2>/dev/null || true)"
      if [[ -z "$pr_url" ]]; then
        pr_url="$(printf '%s' "$json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0].get("url","") if d else "")' 2>/dev/null || true)"
      fi
    fi
  fi

  if [[ -z "$pr_number" ]] && command -v gh >/dev/null 2>&1; then
    local hints
    hints="$(_routine_branch_hints "$routine_id")"
    if [[ -n "$hints" ]]; then
      json="$(gh pr list --repo "$repo_full" --state open \
        --json number,url,headRefName,createdAt --limit 40 2>/dev/null || true)"
      if [[ -n "$json" && "$json" != "[]" ]]; then
        read -r pr_number pr_url branch < <(
          ROUTINE_ID="$routine_id" HINTS="$hints" python3 -c '
import json, os, sys
hints = [h.strip() for h in os.environ.get("HINTS", "").split() if h.strip()]
rid = os.environ.get("ROUTINE_ID", "")
try:
    items = json.load(sys.stdin)
except json.JSONDecodeError:
    items = []
best = None
for pr in items:
    b = str(pr.get("headRefName") or "")
    bl = b.lower()
    if "/auto-" not in bl and not bl.startswith("auto-"):
        continue
    if hints and not any(h.lower() in bl for h in hints):
        if rid and rid.replace("-", "") not in bl.replace("-", ""):
            continue
    if best is None or str(pr.get("createdAt") or "") > str(best.get("createdAt") or ""):
        best = pr
if not best:
    print("  ")
else:
    print(best.get("number", ""), best.get("url", ""), best.get("headRefName", ""))
' <<<"$json"
        )
      fi
    fi
  fi

  if [[ -n "$pr_number" ]]; then
    export ROUTINE_PR_NUMBER="$pr_number"
    export ROUTINE_PR_URL="${pr_url:-https://github.com/${repo_full}/pull/${pr_number}}"
    export ROUTINE_PR_REPO="$repo_slug"
    if [[ -n "$branch" && "$branch" != "main" ]]; then
      export ROUTINE_HEAD_BRANCH="$branch"
    fi
  fi
}

_routine_branch_hints() {
  case "${1:-}" in
    drive-crawler) printf '%s' "drive/" ;;
    revision-correo) printf '%s' "correo/ mail/" ;;
    reuniones-update|reuniones-scheduler) printf '%s' "reuniones/ meetings/" ;;
    housekeeping) printf '%s' "housekeeping/" ;;
    secretary-briefing) printf '%s' "briefing/" ;;
    dispatch-executor) printf '%s' "dispatch/" ;;
    sec-heartbeat) printf '%s' "heartbeat/" ;;
    wiki-update) printf '%s' "wiki/" ;;
    pm-trainee|tidy-up) printf '%s' "tidy-up/ pm-trainee/" ;;
    job-search-crawler) printf '%s' "job-search/" ;;
    whatsapp-monitor) printf '%s' "whatsapp/" ;;
    *) printf '%s' "${1%%-*}/" ;;
  esac
}

_resolve_pr_main "$@"
