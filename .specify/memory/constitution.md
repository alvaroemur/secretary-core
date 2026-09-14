# Constitución — secretary-core

Principios que gobiernan specs, planes y tareas de este repositorio (engine público).
Complementa `CLAUDE.md` y `AGENTS.md`; no los reemplaza.

**Versión:** 1.0.0 · **Ratificada:** 2026-09-14 · **Última enmienda:** 2026-09-14

## Principios

### I. Public-ready

Este repo es público. Specs, planes, commits y PRs no incluyen rutas privadas del
operador, correos personales, claves, ni nombres de personas o negocios de la
instancia. Usar `$SECRETARY_INSTANCE`, `$SECRETARY_CORE`, placeholders y archivos
`.example`.

### II. Engine vs instancia

`secretary-core` es el engine (CLI, secd, playbooks.example, contratos de código).
La instancia (`$SECRETARY_INSTANCE`) guarda estado, memoria y datos reales.
Una spec de engine describe comportamiento portable; no fija layout personal.

### III. Spec Kit bajo demanda

El paquete `.specify/` vive en la raíz. Skills de corredores quedan fuera de git
(ver `.gitignore`). Sin extensión `git`: ramas y commits siguen Conventional Commits
y la disciplina de worktrees del repo. Hooks de `agent-context` deshabilitados —
el contexto de agente se cura a mano en `CLAUDE.md` / `AGENTS.md`.

### IV. Conservar estado al migrar

Documentos de diseño que pasan a spec aquí conservan el estado del original
(borrador, parcial, implementado). El original en la instancia queda como stub con
el material privado redactado y un link a la spec canónica en este repo.

### V. Alcance mínimo

Specs del engine no arrastran doctrina solo-de-instancia. Si un requisito depende
de datos privados, la spec describe el hook/config y deja el contenido en la
instancia.

## Gobernanza

- Todo PR de diseño verifica I–V.
- Enmiendas a esta constitución: bump de versión + nota Sync Impact al inicio.
- Pipeline: `specify → clarify → plan → tasks → implement` cuando el cambio lo
  justifique; no obligatorio para fixes triviales.

**Version**: 1.0.0 | **Ratified**: 2026-09-14 | **Last Amended**: 2026-09-14
