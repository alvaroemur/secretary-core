# Fase 2 — Caches regenerables

Se borran **sin preguntar**: son reconstruibles por la herramienta que los generó, sin pérdida de
datos ni de historial. Verificar antes que la app no esté en medio de una operación (p. ej. no
borrar cache de Chrome con una descarga activa).

## 2.1 Lista de rutas seguras (probadas en dos corridas: 2026-07-06 y 2026-08-07)

```bash
# Updaters de apps (ShipIt y similares) — se regeneran en el próximo update
find ~/Library/Caches -maxdepth 1 -iname "*.ShipIt" -exec rm -rf {} \;

# Paquetes de desarrollo — todo regenerable por el gestor correspondiente
rm -rf ~/.npm/_cacache ~/.npm/_npx
rm -rf ~/.cache/puppeteer
rm -rf ~/Library/Caches/ms-playwright ~/Library/Caches/ms-playwright-go
rm -rf ~/Library/Caches/go-build
rm -rf ~/Library/Caches/node-gyp
rm -rf ~/Library/Caches/pip

# Cache de apps con actualizador propio (Spotify, Antigravity IDE, OpenAI Atlas, etc.)
rm -rf ~/Library/Caches/com.spotify.client
rm -rf ~/Library/Caches/com.openai.atlas
rm -rf ~/Library/Caches/com.google.antigravity-ide.ShipIt

# Homebrew — limpia versiones viejas de fórmulas
brew cleanup -s 2>/dev/null
```

## 2.2 Con cuidado (verificar app cerrada)

```bash
# Cache de Chrome — solo si Chrome no tiene una sesión activa importante
pgrep -x "Google Chrome" >/dev/null && echo "Chrome corriendo — evaluar antes de tocar su cache"
rm -rf ~/Library/Caches/Google/Chrome/Default/Cache*
```

En la corrida de agosto el cache de Chrome ya estaba en 19M (se regenera chico solo) — no vale
la pena forzarlo con la app abierta. Saltar si el tamaño ya es bajo.

## 2.3 Nunca en esta fase

- `~/.cache/uv` — cache de paquetes Python **en uso activo** por herramientas corrientes, no es
  basura acumulada. No borrar salvo que crezca sin control y se investigue antes.
- `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` — no es cache, es
  historial de sesiones (chats, checkpoints). Ver nota en `00-orientacion/playbook.md`.
- Cualquier cache de una app con una sesión de trabajo abierta en este momento.

## 2.4 Cierre de fase

Medir el delta y anotarlo para el reporte final:

```bash
df -h /System/Volumes/Data | tail -1
```
