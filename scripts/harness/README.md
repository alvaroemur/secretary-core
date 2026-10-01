# Scripts del Harness de Claude Code

Este directorio contiene la versión canónica y controlada por git de los scripts que operan en `~/.claude/scripts/`.

## Propósito

Cerrar el gap identificado en [cowork-secretary#1213](https://github.com/alvaroemur/cowork-secretary/issues/1213): evitar que los scripts del harness se editen directamente en caliente fuera de control de versiones, previniendo colisiones entre sesiones paralelas y asegurando historial, trazabilidad y rollback.

## Inventario de Scripts

| Script | Rol / Evento | Descripción |
|---|---|---|
| `cowork-nativos-check.sh` | Hook / Verificación | Valida la integridad de entregables nativos en Cowork. |
| `git-main-guard.py` | Hook Pre-Commit | Protege la rama `main` contra commits directos no autorizados. |
| `repos-sync-check.sh` | SessionStart Hook | Verifica sincronización de repositorios y paquetes al abrir sesión. |
| `sec-acc-fold.sh` | Operativo / Acciones | Pliega y archiva acciones procesadas. |
| `sec-haptic.sh` | Feedback / Notificación | Emite señales hápticas en macOS al completar tareas. |
| `sec-signature.sh` | Firma de Agente | Inyecta la firma institucional estandarizada en commits/PRs. |
| `sec-status.sh` | Diagnóstico | Informa el estado y salud operativa de la instancia Secretary. |
| `stop-reflect-claudemd.sh` | Stop Hook | Reflexión y auditoría de cambios en archivos `CLAUDE.md`. |
| `stop-reflect-wiki.sh` | Stop Hook | Verifica si la sesión produjo señales para la wiki. |
| `sync-viewer-skill.sh` | Skill / Visual | Sincroniza diagramas y vistas con el visor interactivo. |

## Regla de Mantenimiento

Toda modificación a estos scripts debe realizarse en este directorio (`scripts/harness/`) mediante PR a `secretary-core`.
