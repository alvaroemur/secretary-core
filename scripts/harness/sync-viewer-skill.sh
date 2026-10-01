#!/usr/bin/env bash
# sync-viewer-skill.sh — PostToolUse hook for Edit/Write on viewer HTML files.
# Detects changes to arquitectura.html, compares against canonical hash,
# and outputs context for Claude about skill updates and outdated repos.
#
# Input: reads $CLAUDE_TOOL_INPUT for the file path that was edited/written.
# Output: plaintext to stdout when action is needed.

set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/visual-thinking"
REPOS_FILE="$SKILL_DIR/viewer-repos.txt"
HASH_FILE="$SKILL_DIR/.viewer-canonical-hash"

# --- extract file path from tool input ---
FILE_PATH=""
if [ -n "${CLAUDE_TOOL_INPUT:-}" ]; then
  FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || echo "")
fi

# only act on arquitectura.html files
case "$FILE_PATH" in
  */arquitectura.html) ;;
  *) exit 0 ;;
esac

# --- compute hash of the file just changed ---
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi
THIS_HASH=$(shasum -a 256 "$FILE_PATH" | cut -d' ' -f1)

# --- load previous canonical hash ---
PREV_HASH=""
if [ -f "$HASH_FILE" ]; then
  PREV_HASH=$(cat "$HASH_FILE")
fi

# --- determine which repo this file belongs to ---
# Extract repo name: handle worktrees (.claude/worktrees/xxx/) and direct paths
REPO_NAME=$(echo "$FILE_PATH" | python3 -c "
import sys, re
p = sys.stdin.read().strip()
# worktree pattern: .../Dev/<repo>/.claude/worktrees/<name>/...
m = re.search(r'/Dev/([^/]+)/\.claude/worktrees/', p)
if m:
    print(m.group(1))
else:
    # direct pattern: .../Dev/<repo>/...
    m = re.search(r'/Dev/([^/]+)/', p)
    if m:
        print(m.group(1))
    else:
        print('')
" 2>/dev/null || echo "")

# --- check canonical repo name (first entry in repos file) ---
CANONICAL_REPO=""
if [ -f "$REPOS_FILE" ]; then
  CANONICAL_PATH=$(grep -v '^#' "$REPOS_FILE" | grep -v '^\s*$' | head -1)
  CANONICAL_REPO=$(echo "$CANONICAL_PATH" | sed 's|.*/Dev/||' | sed 's|/docs/arquitectura.html||')
fi

# --- did the canonical viewer change? ---
CANONICAL_CHANGED="false"
if [ "$REPO_NAME" = "$CANONICAL_REPO" ]; then
  if [ "$THIS_HASH" != "$PREV_HASH" ]; then
    CANONICAL_CHANGED="true"
    echo "$THIS_HASH" > "$HASH_FILE"
  fi
fi

# --- find outdated repos (compare against current canonical hash) ---
CURRENT_CANONICAL_HASH="$THIS_HASH"
if [ "$CANONICAL_CHANGED" = "false" ] && [ -n "$PREV_HASH" ]; then
  CURRENT_CANONICAL_HASH="$PREV_HASH"
fi

OUTDATED=""
if [ -f "$REPOS_FILE" ]; then
  while IFS= read -r REPO_VIEWER; do
    # skip comments and blanks
    case "$REPO_VIEWER" in '#'*|'') continue ;; esac
    # skip canonical (first entry)
    if [ -z "$OUTDATED" ] && [ "$(echo "$REPO_VIEWER" | sed 's|.*/Dev/||' | sed 's|/docs/arquitectura.html||')" = "$CANONICAL_REPO" ]; then
      OUTDATED="checked"
      continue
    fi
    if [ -f "$REPO_VIEWER" ]; then
      REPO_HASH=$(shasum -a 256 "$REPO_VIEWER" | cut -d' ' -f1)
      if [ "$REPO_HASH" != "$CURRENT_CANONICAL_HASH" ]; then
        R_NAME=$(echo "$REPO_VIEWER" | sed 's|.*/Dev/||' | sed 's|/docs/arquitectura.html||')
        OUTDATED="$OUTDATED|$R_NAME"
      fi
    else
      R_NAME=$(echo "$REPO_VIEWER" | sed 's|.*/Dev/||' | sed 's|/docs/arquitectura.html||')
      OUTDATED="$OUTDATED|$R_NAME(missing)"
    fi
  done < "$REPOS_FILE"
fi

# clean up OUTDATED — remove leading "checked|"
OUTDATED=$(echo "$OUTDATED" | sed 's/^checked//' | sed 's/^|//')

# --- only output if something interesting happened ---
if [ "$CANONICAL_CHANGED" = "true" ] || [ -n "$OUTDATED" ]; then
  echo "viewer sync check:"
  if [ "$CANONICAL_CHANGED" = "true" ]; then
    echo "  canonical viewer changed (repo: $REPO_NAME). Review ~/.claude/skills/visual-thinking/SKILL.md — update Paso 5 if new viewer features were added."
  fi
  if [ -n "$OUTDATED" ]; then
    echo "  outdated viewers: $OUTDATED"
    echo "  action: propose spawn_task for each outdated repo to copy the updated arquitectura.html and adapt its DIAGRAMS array."
  fi
fi
