---
id: "009"
slug: secretary-cli
layer: L0
status: mvp
last_reviewed: 2026-07-02
implemented:
  - secretary/
  - cli/README.md
---

# Spec 009 — `secretary` CLI

**Estado:** MVP implementado en `secretary-core/secretary/`  
**Instancia:** `$SECRETARY_INSTANCE` vía `SECRETARY_INSTANCE`

## Objetivo

Un entrypoint instalable (`pip install -e .`) que expone **operaciones
atómicas** del subsistema: resolver paths, persistir estado, validar, buscar memoria, build wiki.

Los skills (`sec-recall`, `pulse`, `sec-write`, …) siguen siendo la capa agentica; el CLI es
el paso determinista que evita re-parsear `.secretary.yml` y duplicar bash en cada skill.

## Comandos MVP

| Comando | Reemplaza / complementa |
|---------|-------------------------|
| `secretary config show\|path` | lectura manual de `.secretary.yml` |
| `secretary paths` | vista rápida de extractores |
| `secretary status` | `sec-status.sh` (delegación) |
| `secretary validate` | CI local / pre-PR |
| `secretary wiki build` | `SECRETARY_DATA=… python3 …/build.py` |
| `secretary recall` | paso 0 de `sec-recall` |
| `secretary fresh` | paso 0 fresh-first de `sec-mail`, `sec-meeting`, `sec-recall` |
| `secretary acc fold` | `sec-acc-fold.sh` (delegación) |

## Contrato

- Paths: claves con punto (`mail.memory`) → absolutos desde `paths` en `.secretary.yml`
- `SECRETARY_CORE` / `SECRETARY_INSTANCE` con expansión de `~`
- Exit codes: 0 ok, ≠0 error (validadores propagan su código)
- Sin LLM en el CLI

## Migración

1. Shell scripts delegan si `command -v secretary` (`sec-status.sh`, `sec-acc-fold.sh`)
2. Skills: sección **Atomic ops** con el comando equivalente
3. Fase 2: heartbeat, dispatch, serve, JSON global

Ver `cli/README.md`.
