# Contributing to secretary-core

This repository follows the canonical worksystem workflow conventions.

## Workflow Conventions
- **Conventional Commits**: Use `<type>(<scope>): <subject>` format. The scope is the work thread.
- **Branching**: One branch per thread. Push draft PRs, move to ready when finished. No direct commits to `main`.
- **Issues**: Use issues for non-trivial or parked work. Use labels for threads/series and real references.
- **Worktrees**: Use git worktrees for parallel threads to avoid switching branches in the same working directory.

## Valid Scopes (secretary-core)
Use one of these scopes for your commits:
- `wiki`: Generador estático, plugins, templates de wiki, parsing.
- `routines`: Router, instalador, métricas, invoke (harness).
- `whatsapp`: Integración con Baileys, parsers, extractores.
- `mail`: Revisión de correo, rulesets, templates.
- `core`: Infraestructura base del engine (configuración, logs).
- `docs`: Documentación, policies, guías, READMEs.
- `skills`: Skills y playbooks espejados.
