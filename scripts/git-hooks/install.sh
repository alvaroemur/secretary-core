#!/usr/bin/env bash
# Install the global git hooks dispatcher: one symlink per hook name, all pointing
# at hook-dispatch in this checkout. Does not touch git config; prints the line to
# activate it.
set -eu

src="$(cd "$(dirname "$0")" && pwd)"
case "$src" in
  */.wt/*|*/worktrees/*)
    echo "Instala desde el checkout principal: los worktrees se borran al integrarse." >&2
    exit 1 ;;
esac
dest="${1:-${XDG_CONFIG_HOME:-$HOME/.config}/git/hooks}"
mkdir -p "$dest"
for hook in applypatch-msg pre-applypatch post-applypatch pre-commit pre-merge-commit \
  prepare-commit-msg commit-msg post-commit pre-rebase post-checkout post-merge \
  pre-push post-rewrite push-to-checkout; do
  ln -sfn "$src/hook-dispatch" "$dest/$hook"
done
chmod +x "$src/hook-dispatch" "$src/push_leak_guard.py"
echo "Hooks en $dest."
current="$(git config --global core.hooksPath || true)"
if [ "$current" = "$dest" ]; then
  echo "core.hooksPath ya apunta ahí."
else
  echo "Para activarlos: git config --global core.hooksPath \"$dest\""
fi
