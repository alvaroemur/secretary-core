---
name: sec-cowork-fit
description: >-
  Apply proyecto-cowork skeleton (sistemas-ordenamiento §3) to one Cowork
  folder — bootstrap empty trees, diagnose drift, apply mkdir/mv only after
  explicit owner OK. Triggers: "/sec-cowork-fit", "esqueleto este proyecto",
  "bootstrap proyecto Cowork", "ajusta la carpeta al perfil", "fit skeleton".
---

# sec-cowork-fit — single-folder proyecto-cowork skeleton

**Mission:** bring **one** `~/Cowork/.../proyectos/.../<slug>/` folder into the
canonical profile + numbered skeleton (§3). Portfolio-wide drift stays in
`sec-cowork-audit`.

Doctrine: `rules/skills-contract.md` · policy: `paths.operational.sistemas_ordenamiento` §3–§3.4, §8

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
ORDENAMIENTO=$(secretary config path operational.sistemas_ordenamiento)
ESQUELETO="$SECRETARY_INSTANCE/templates/esqueleto-proyecto-cowork.md"
PROCESO="$SECRETARY_INSTANCE/templates/proceso-constitutivo.md"
```

| Constant | Resolution |
|----------|------------|
| `TARGET` | Absolute path to **one** project folder (required) |
| `POLICY` | `$ORDENAMIENTO` §3–§3.4, §8 |
| Templates | `$ESQUELETO` (README seed), `$PROCESO` (phase MD under ejecución — copy only when owner asks for a phase) |

## Inputs

| Field | Values |
|-------|--------|
| `path` | Absolute or `~/Cowork/...` path to the project folder |
| `mode` | `diagnose` (default for existing trees) \| `bootstrap` \| `apply` |
| `perfil` | optional override: `proyecto-cliente` \| `producto-jv` |

If `path` missing → ask. If owner says "ordena Cowork" without a folder → hand off to `sec-cowork-audit`.

## Mode selection

| Condition | Mode |
|-----------|------|
| Folder empty or near-empty (≤ README / `.DS_Store` / empty dirs) and owner wants skeleton | `bootstrap` |
| Existing tree, no explicit apply OK | `diagnose` (default) |
| Owner gave explicit 🚧 OK on a listed plan | `apply` |

Never jump to `apply` from ambient intent.

## Context inference (perfil)

Resolve in order; stop at first solid signal:

1. **Path** — under `…/clientes/…` → lean `proyecto-cliente`; under `…/propios/…` or product/JV naming → lean `producto-jv`.
2. **Existing tree** — CLab-lite / Ali (`01-admin`…`05-bitacora` / `01-inputs`…) → `proyecto-cliente`; historic four (`fuentes|borradores|entregables|proceso`) → transition, still infer cliente unless path says otherwise; `.drivesync` / public-folder mirrors inform homes map only, not perfil alone.
3. **README** — frontmatter or checked perfil box in template.
4. **Ask** — if still ambiguous, 🚧 ask owner before bootstrap/apply.

Do **not** invent EDT phase names under `03-ejecucion/`.

## Loop

### Step 0 — Policy + target (required)

```bash
# Read (do not paste tables into chat):
#   $ORDENAMIENTO §3–§3.4, §8
#   $ESQUELETO
ls -la "$TARGET"
find "$TARGET" -maxdepth 2 \( -type d -o -type f \) | head -80
```

Confirm `TARGET` is under `~/Cowork/` and looks like a project folder (not workspace root, not `marca/`, not `_referencias/`).

### Step 1 — Infer perfil + mode

Record: inferred perfil, confidence, signals used. Pick mode per table above.

### Step 2a — `bootstrap`

Only when near-empty (or owner confirms overwrite of empty stubs):

1. Create skeleton dirs for the perfil (§3.2 / `$ESQUELETO`).
   - **proyecto-cliente:** `01-admin/` (optional — create unless owner says skip), `02-insumos/`, `03-ejecucion/`, `04-comunicaciones/`, `05-entregables/`, `06-bitacora/` (optional).
   - **producto-jv:** `01-insumos/`, `02-analisis/`, `03-ejecucion/`, `04-comunicaciones/`, `05-entregables/`.
2. Write `README.md` from `$ESQUELETO` — fill `proyecto`, `workspace`, `perfil`, `fecha_bootstrap` (America/Lima `YYYYMMDD`); leave Drive/Dev homes as `…` if unknown.
3. Report created paths. Do **not** create phase files unless owner names a phase (then copy `$PROCESO` → `03-ejecucion/NN_<fase>.md`).

### Step 2b — `diagnose` (default)

Emit action table only — **no** mkdir/mv:

| action | from | to / note | risk |
|--------|------|-----------|------|
| mkdir | — | `02-insumos/` | low |
| mv | `fuentes/` | `02-insumos/` | med — review contents |
| write | — | `README.md` (perfil + homes) | low if absent |
| skip | `03-ejecucion/` phases | owner names EDT | — |

Map legacy via §3.3. Flag optional dirs. End with: "Say **apply** (or OK on the listed rows) for 🚧 gated execution."

### Step 2c — `apply` (gated)

**Requires** explicit owner OK on the plan (🚧). MVP behavior:

1. **mkdir** missing skeleton dirs from the agreed plan.
2. **README** — create from template if missing; if present, only patch perfil/homes when owner OK'd that row.
3. **mv** — show the exact `mv` list again; execute **only** rows the owner confirmed. Prefer `mv` over copy; never delete sources as cleanup in the same step.
4. Re-run a short diagnose summary (remaining gaps).

If OK was vague ("sí") but plan had medium/high-risk mvs → re-list mv rows and ask for confirmation on those only.

## Guardrails

- **One folder** per run — no portfolio sweeps (that's `sec-cowork-audit`).
- **No Drive mutations** — mirrors/pointers stay; organization via `sec-drive` / `drive-crawler`.
- **No Dev moves** — code stays in `~/Dev/`; only document in README homes map.
- **No mass multi-project migration.**
- **No inventing EDT phases.**
- Do not migrate Ali / ERP / Nativas / Alma "in cold" from policy alone — only if this `TARGET` is that folder **and** owner OK'd the plan.
- Native `*.gdoc` / `*.gsheet` pointers: never `rm`; move only with owner OK and awareness they are Drive stubs.

## Report shape

```
## sec-cowork-fit — <slug>
- mode: diagnose|bootstrap|apply
- perfil: proyecto-cliente|producto-jv (inferred|declared|asked)
- path: ~/Cowork/...

### Actions
| … table … |

### Next
- diagnose → wait for 🚧 OK to apply
- bootstrap/apply → remaining gaps or done
```

## Integration

| Skill / routine | Role |
|-----------------|------|
| `sec-cowork-audit` | Portfolio scan; points single folders here |
| `sec-workspace` | Compat alias → audit, not fit |
| `pm-trainee` | Batch proposals; interactive apply stays here |
| `sec-drive` | Drive-side; complementary |

## Out of scope

- Portfolio audit / "ordena todo Cowork".
- CI on Cowork repos.
- Editing `~/Cowork/CLAUDE.md`.
- Creating full Mundo CLab Drive trees (`01 ADMINISTRACIÓN` with spaces) unless TARGET is already a Drive mirror that uses that convention — then respect existing convention, don't dual-create.
