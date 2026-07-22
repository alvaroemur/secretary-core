---
name: sec-cowork-audit
description: >-
  Audit ~/Cowork/ project folders against canonical layout (sistemas-ordenamiento
  §3 profiles + skeleton, drive-cowork, etl.md). Proposes relocations like
  pm-trainee — never moves without OK. Triggers: "/sec-cowork-audit",
  "/sec-workspace", "ordena Cowork", "drift estructural", "dónde va este proyecto".
  Alias: sec-workspace still resolves here.
---

# sec-cowork-audit — Cowork portfolio layout audit

**Mission:** compare live `~/Cowork/` trees against instance ordering policy
(**profiles + numbered skeleton** §3) and emit a **proposal table** — no
filesystem mutations without explicit owner OK (same baranda as `pm-trainee`).

**Pair:** portfolio drift → this skill · single-folder skeleton → `sec-cowork-fit`.

Doctrine: `rules/skills-contract.md` · policy: `paths.operational.sistemas_ordenamiento`

**Alias:** `/sec-workspace` and skill name `sec-workspace` redirect here (compat stub).

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
ORDENAMIENTO=$(secretary config path operational.sistemas_ordenamiento)
ESQUELETO="$SECRETARY_INSTANCE/templates/esqueleto-proyecto-cowork.md"
```

| Constant | Resolution |
|----------|------------|
| `COWORK_ROOT` | `~/Cowork/` (owner layout — not in `.secretary.yml`) |
| `POLICY` | `$ORDENAMIENTO` §3–§3.4, §8 — profiles + skeleton (not four-folder minimum) |
| Templates | `$ESQUELETO`, `$SECRETARY_INSTANCE/templates/proceso-constitutivo.md` |
| Parent rules | `rules/etl.md`, `rules/drive-cowork.md`, `~/Cowork/CLAUDE.md` |

## Inputs

| Field | Values |
|-------|--------|
| `scope` | `all` (default) \| workspace slug (`inspiro`, `ennui`, `studio`) \| project path |
| `depth` | `shallow` (top-level + proyectos) \| `deep` (full tree, slow) |

## Loop

### Step 0 — Policy + instance CI (required)

```bash
secretary validate ordenamiento    # .secretary plane only
# Read policy sections (do not duplicate tables into the skill):
#   $ORDENAMIENTO §3–§3.4, §8
#   $ESQUELETO
#   rules/drive-cowork.md §3 (taxonomy) + §7 (workspace roles)
```

### Step 1 — Cowork tree scan

For each workspace under `~/Cowork/` (skip `_inbox` unless scope says otherwise):

1. List `proyectos/*/` (and nested `proyectos/clientes/<cliente>/<proyecto>/`).
2. Infer **perfil** per project when possible (path `clientes/` vs `propios/`, tree shape, README) — else flag "perfil ambiguous".
3. Against the inferred/declared profile, flag missing skeleton stages (§3.2):
   - **proyecto cliente:** `README.md`, `02-insumos/`, `03-ejecucion/`, `04-comunicaciones/`, `05-entregables/` (note `01-admin/` / `06-bitacora/` optional).
   - **producto / JV:** `README.md`, `01-insumos/`, `02-analisis/`, `03-ejecucion/`, `05-entregables/` (`04-comunicaciones/` if external stakeholders).
4. Flag **legacy four-folder** trees (`fuentes/`, `borradores/`, `entregables/`, `proceso/`) as *valid in transition* — propose migration to profile via `sec-cowork-fit` diagnose, do not treat as hard error.
5. Flag deliverables or relational drafts sitting outside `proyectos/<slug>/`.
6. Flag design systems outside `marca/` (see policy §2 design systems).
7. Cross-check naming: local `<cliente_slug>_<desc>` vs Drive `<año> <descripción>` (inform only).
8. **Native Drive pointers** — run `~/.claude/scripts/cowork-nativos-check.sh` (or the same `find` for `*.gsheet`/`*.gdoc`/… under `$COWORK_ROOT`). Flag each path; remediate in Drive only — never `rm` the local pointer (`rules/drive-cowork.md` · spec 004).

Optional: read latest `pm-trainee` PR proposals if one is open (`gh pr list` on Cowork repos).

### Step 2 — Report (no moves)

Output table:

| path | finding | policy ref | proposed action |
|------|---------|------------|-----------------|
| … | missing `02-insumos/` (perfil cliente) | sistemas-ordenamiento §3.2 | `sec-cowork-fit` bootstrap/diagnose |
| … | legacy `fuentes/` only | §3.3 | migrate → `02-insumos/` via fit (gated) |
| … | draft at repo root | §6.1 | move → `proyectos/<slug>/04-comunicaciones/…` |

**Gate:** any `mv`/`git mv`/`mkdir` that reshapes a live project requires 🚧 owner OK. This skill only proposes. Hand single-folder reshape to `sec-cowork-fit`.

## Integration

| Consumer | Role |
|----------|------|
| `sec-cowork-fit` | Apply skeleton to **one** folder (bootstrap / diagnose / apply) |
| `sec-recall` | Paso 1 after workspace questions — delegates Paso 0 here |
| `pm-trainee` | Weekly batch auditor; this skill is interactive fresh-first |
| `drive-crawler` | Drive-side proposals; complementary, not duplicate |

## Out of scope

- CI validators on Cowork repos (instance repo only has `.secretary` allowlist).
- Physical migration of project folders without owner OK (use `sec-cowork-fit` apply after 🚧).
- Mass multi-project migration in one shot.
- Drive mutations / Dev moves.
- `~/Cowork/CLAUDE.md` edits (spec 003 — deferred until Álvaro closes §9 open questions).
- Inventing EDT phases under `03-ejecucion/` (owner decides phase names).
