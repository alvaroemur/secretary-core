---
name: desk-tablero
description: >-
  Mirror and operate the owner's physical Scrum board — read state, persist moves, hydrate from
  secretary (brief, recall, meetings, wip), extract components from a board photo, and link
  components to Desk calendar blocks. Human HITL work plane; separate from the agentic loop.
  Triggers: "/desk-tablero", "tablero", "scrumb board", "what's on the board", "mover tarjeta",
  "foto del tablero", "bloque desk", "componente en progreso", "urgente en el tablero".
---

# desk-tablero — physical Scrum board mirror

**Mission:** keep the physical Scrum board (swimlanes Workspace → Proyecto, unit = Componente,
columns BACKLOG → DONE) aligned with secretary — read it, persist it, fill it from recent signals,
scan photos, and associate components with **💻 Desk** calendar blocks for focused human work.

Doctrine: `rules/skills-contract.md` · board semantics: wiki article `temas/tablero-scrum`

## Instance setup

```bash
eval "$(secretary env)"
CFG=$(secretary config show)
INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
BRIEF_LABEL=$(echo "$CFG" | jq -r '.brief.label // "tipo:informe-diario"')
if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
TABLERO_DIR=$(secretary config path subsystem.tablero 2>/dev/null || echo "$INSTANCE/subsystem/tablero")
STATE_FILE="$TABLERO_DIR/state.yaml"
DOCTRINE_SLUG="temas/tablero-scrum"
```

Resolve **Desk** calendar at runtime (do not hardcode calendar id):

```bash
DESK_CAL_ID=$(gog calendar calendars --account="$PERSONAL_ACCOUNT" --plain --no-input \
  | awk -F'\t' '$2 ~ /Desk/ {print $1; exit}')
```

Desk events (read):

```bash
[ -n "$DESK_CAL_ID" ] && gog calendar events "$DESK_CAL_ID" \
  --from="$TODAY" --to="$(date -v+14d +%Y-%m-%d 2>/dev/null || date -d '+14 days' +%Y-%m-%d)" \
  --account="$PERSONAL_ACCOUNT" --plain --no-input
```

## Guardrails

- **Human work plane.** Tablero tracks the owner's real work (HITL). Do not treat agent delegate
  queues, open PR babysitting, or routine auto-PRs as components unless the owner explicitly asks.
- **Doctrine vs state.** Column semantics and swimlane rules live in the wiki article — read, do not
  duplicate prose in `state.yaml`. State file = live mirror of cards on the board.
- **Propose before bulk hydrate or photo scan.** `hydrate` and `scan` output a diff table; persist
  only after owner confirms (or explicit "apply all").
- **Desk calendar mutations = 🚧 gate.** Never `gog calendar create` / update / delete without
  explicit OK. Show proposed `--summary`, `--from`, `--to`, and linked `component_id` first.
- **Resolve paths via CLI** — never hardcode instance roots or calendar ids.
- **Do not write wiki doctrine** from routine tablero ops. Use `desk-sys-annotate` only when the
  owner asks to record a durable fact about the board system itself.
- **WIP is not tablero.** `subsystem/wip/` = per-repo session parking; tablero = cross-repo human
  front-of-mind. Cross-read wip on hydrate, but do not merge stores.

## Inputs

| Field | Values |
|-------|--------|
| `intent` | `status` (default) \| `update` \| `hydrate` \| `scan` \| `desk` |
| `component_id` | Stable id for `update` / `desk` |
| `column` | `BACKLOG` \| `URGENTE` \| `EN_PROGRESO` \| `BLOQUEADO` \| `REVISAR` \| `DONE` |
| `title` | New component title |
| `workspace` | Swimlane workspace (e.g. `ennui`, `inspiro`, `studio`) |
| `proyecto` | Swimlane project slug |
| `image_path` | Absolute path to board photo for `scan` |
| `desk` | For `desk`: `link` \| `create` \| `show` |
| `desk_from` / `desk_to` | RFC3339 or local datetime for `create` |
| `brief_ref` | Optional `#N` or `acc-id` link |

## Column semantics (operational — wiki is source)

| Column | Meaning |
|--------|---------|
| `BACKLOG` | Ready to work, not started |
| `URGENTE` | Interrupt lane (pink sticky) — displaces in-progress, not "high priority backlog" |
| `EN_PROGRESO` | Actively being worked |
| `BLOQUEADO` | Blocked on external input or owner decision |
| `REVISAR` | Ready for owner HITL validation |
| `DONE` | Closed — no further work |

## Loop

### Step 0 — Load state (all intents)

```bash
mkdir -p "$TABLERO_DIR"
[ -f "$STATE_FILE" ] && cat "$STATE_FILE"
git -C "$INSTANCE" show "origin/main:knowledge/wiki/articulos/$DOCTRINE_SLUG.md" 2>/dev/null | head -45
```

If `state.yaml` missing → empty board; offer first `hydrate` or manual `update`.

### `intent=status`

1. Group components by `workspace` → `proyecto`, then by `column`.
2. Cross-check **Desk** events for blocks linked via `desk.event_id` or title prefix
   `[workspace/proyecto]`.
3. Note stale cards (`moved_at` > 7d in `EN_PROGRESO` or `URGENTE`) and empty swimlanes.

### `intent=update`

1. Parse owner instruction: add card, move card, remove card, edit title/workspace/proyecto.
2. Assign `id` on create: `comp-YYYYMMDD-NNN` (increment NNN within day).
3. Set `moved_at` to `$TODAY` on column change; append `history` entry (from → to, date).
4. Write `state.yaml` (`updated`, `updated_by: desk-tablero`).
5. If moved to `DONE` and `brief_ref` set → offer `secretary status "✅" "<ref>" "tablero done"`.
6. If moved to `URGENTE` → warn that it should displace current `EN_PROGRESO` on the physical board.

### `intent=hydrate`

Gather **proposals only** — do not write until confirmed.

1. **Brief** — today's issue (`BRIEF_LABEL` on `BRIEF_REPO`): unchecked items in *Your list for
   today* and carry-over; map to workspace/proyecto when obvious from text or linked issue.
2. **`desk-recall`** — active topics the owner cares about this week (read-only pass).
3. **Meetings** — open rows in `extractors/meetings/memory/acciones.md` with owner as actor and
   state open/in-progress; prefer items without agent branch/PR (`loose-acc` human actions).
4. **`desk-state` / wip** — human-facing threads (decisions pending owner, sends, trámites) — skip
   pure git/PR hygiene.
5. **Heartbeat** — `loose-acc` rows that are clearly owner actions, not agent loops.

Filter out: `delegate:execute`, routine PR titles, extractor maintenance, "merge PR #N" unless
owner flagged as personal work.

Render proposal table:

| propose | title | workspace | proyecto | column | source |
|---------|-------|-----------|----------|--------|--------|

Owner confirms rows → `update` loop for each accepted row.

### `intent=scan`

1. Accept `image_path` (chat attachment saved to disk, or wiki media reference).
2. Read the image; extract visible sticky text, infer column from header position, infer swimlane
   from row labels (Workspace / Proyecto).
3. Diff against `state.yaml`: `new`, `moved`, `missing_on_photo`, `unreadable`.
4. Show diff table; on confirm → batch `update`.
5. Optional: copy scan to `$TABLERO_DIR/scans/YYYYMMDD-HHMM.jpg` for audit (only if owner wants).

### `intent=desk`

Link a component to a **💻 Desk** block (focused internal work time).

**`desk=show`** — list Desk events ±14d with linked `component_id` (from `desk.event_id` or
`private-prop tablero.component_id`).

**`desk=link`** — attach existing event id to `component_id` in state; set `desk.event_id`.

**`desk=create`** — propose event:

```bash
# After owner OK:
gog calendar create "$DESK_CAL_ID" \
  --account="$PERSONAL_ACCOUNT" \
  --summary="[${workspace}/${proyecto}] ${title}" \
  --from="<RFC3339>" --to="<RFC3339>" \
  --description="tablero:${component_id}" \
  --private-prop="tablero.component_id=${component_id}" \
  --json --no-input
```

Store returned `event_id` on the component. Prefer **focus-time** blocks for deep work; default
duration 90–120 min unless owner specifies.

## State file (`state.yaml`)

Proposed path: `subsystem/tablero/state.yaml` (register in `.secretary.yml` → `paths.subsystem.tablero`).

```yaml
schema_version: 1
updated: YYYY-MM-DD
updated_by: desk-tablero | owner | scan

components:
  - id: comp-YYYYMMDD-001
    title: "Human-readable card text"
    workspace: ennui          # swimlane
    proyecto: erp-clab        # swimlane
    column: EN_PROGRESO       # enum — see Column semantics
    brief_ref: "#12"          # optional brief item or acc-id
    desk:
      event_id: null          # Google Calendar event id
      block_label: null       # e.g. "Wed 14:00–16:00" (human shorthand)
    sources:
      - type: brief | meeting | wip | recall | manual | scan
        ref: "<id or path>"
        date: YYYY-MM-DD
    notes: ""
    created: YYYY-MM-DD
    moved_at: YYYY-MM-DD
    history:
      - from: BACKLOG
        to: EN_PROGRESO
        date: YYYY-MM-DD
```

Optional audit folder: `subsystem/tablero/scans/` (photo copies). Add `subsystem/tablero/README.md`
mirroring `subsystem/wip/README.md` when the store is first created.

## Integration

| Skill / tool | Role |
|--------------|------|
| `desk-recall` | Read-only hydrate source |
| `desk-overview` | Brief loader for hydrate; tablero does not replace desk-overview |
| `desk-meeting` | Fresh meeting actions for hydrate |
| `desk-state` | Wip cross-read on hydrate |
| `desk-write` | Not for tablero state — write `state.yaml` directly |
| `wiki-write` | Doctrine updates to `temas/tablero-scrum` only when asked |
| `secretary status` | Optional when component done + `brief_ref` linked |

## Report

Header: `📋 **Tablero** · <intent>` · status `<loaded|updated|proposed|linked>`.

**`status`:** swimlane table — columns as columns or grouped list; flag `URGENTE` and `BLOQUEADO`
first. Show linked Desk blocks. Close with `→` one suggested action if something stands out.

**`update`:** one line per change — id, column move, path to `state.yaml`.

**`hydrate` / `scan`:** proposal table + "confirm rows to apply".

**`desk`:** event summary, times, linked `component_id`; or 🚧 proposed create payload awaiting OK.

Use judgment on the detail; don't enumerate every case. Anything invariant about
the user (language, git conventions, what's private, folder layout) lives in the
runtime's AGENTS.md, not here. Current-moment data comes from the runtime (the
engine's lookup sources), not this file.

## Atomic ops

```bash
secretary config path subsystem.tablero   # after YAML registration
gog calendar calendars --account="$PERSONAL_ACCOUNT" --plain   # resolve Desk id
secretary recall "<topic>" --format json   # hydrate index
secretary fresh meeting --format json      # recent meeting actions
```
