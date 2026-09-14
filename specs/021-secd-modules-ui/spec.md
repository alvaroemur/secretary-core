---
id: "021"
slug: secd-modules-ui
layer: L5
status: implementado
last_reviewed: 2026-07-03
implemented:
  - $SECRETARY_INSTANCE/subsystem/portal/modules.html
  - secd/lib/modules.mjs
gaps:
  - integración portal 019 aggregator
  - PUT contract desde UI
---

# Spec — Feature 021: secd modules UI

**Estado:** `implementado (v1)` — panel HTML local + API spec 015
**Origen:** GitHub [#426](https://github.com/<instance-repo>/issues/426)

## Problema

`GET /modules` existe en secd pero no hay vista operador para auditar salud de extractores/loops.

## Solución v1

- `subsystem/portal/modules.html` — fetch autenticado a `/modules` y `/modules/:id/health`
- `subsystem/portal/README.md` — servir con `python3 -m http.server`

## API consumer

| Method | Route | Uso UI |
|--------|-------|--------|
| GET | `/modules` | Tabla principal |
| GET | `/modules/:id/health` | Drill-down criterios |

Auth: Bearer desde `<instance>/.secd/token`.

## Success criteria

- SC-1: Refresh lista módulos con secd activo.
- SC-2: Gaps de `contract_health` visibles como warn/fail.
- SC-3: Read-only — sin PUT en v1.

## Fase 2

Integrar en portal 019; edición contract con compuerta humana.
