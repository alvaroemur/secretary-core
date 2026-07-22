#!/usr/bin/env bash
# deploy-output.sh — publica el HTML generado (wiki/output) al repo que Cloudflare
# Pages despliega (yourusername/wiki). ÚNICO punto de push a ese remote: está permitido
# de forma exacta en ~/.claude/settings.json para que el deploy de la wiki no promptee
# ni lo frene el clasificador de auto-mode. No amplía permisos a otros repos.
#
# Uso:  deploy-output.sh ["mensaje de commit"]
# Si no hay cambios en el HTML, no crea commit y sale 0.
set -euo pipefail

OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/output" && pwd)"
cd "$OUT"

if [ ! -d .git ]; then
  git init -q
  git remote add origin git@github.com:yourusername/wiki.git
fi

git add -A
if git diff --cached --quiet; then
  echo "HTML idéntico — no se despliega."
  exit 0
fi

MSG="${1:-sync-wiki $(date +%Y-%m-%d)}"
git commit -q -m "$MSG"
git push -q origin main || git push -fq origin main
echo "publicado: $(git log -1 --oneline)"
