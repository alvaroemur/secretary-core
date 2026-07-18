---
name: sec-merge
description: >-
  Persistent secretary mode that keeps session work "current" (merged to main). When a session PR
  becomes mergeable, raises a 🚧 gate and, on confirmation, merges+prunes — tier-gated: data/prose
  merges on "yes", executable code shows diff first. Secretary's merge-on-confirm layer above
  babysit. Triggers: "/sec-merge", "keep this current", "merge-on-confirm on/off", or at session
  start when owner wants OKs to close PRs.
user-invocable: true
---

# sec-merge — merge on confirmation

**Mission:** close the gap between "reviewed in chat" and "merged to `main`". Owner review in live
sessions becomes what merges, instead of leaving PRs hanging until `wiki-update` W0 or manual GitHub.

Doctrine: `rules/skills-contract.md`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
```

Haptics: `secretary` CLI or instance harness scripts for compuerta/delivery signals (see
`rules/sec-haptics.md`). Do not hardcode script paths — resolve from harness `CLAUDE.md` if needed.

## What this is NOT

- **Not babysit.** Babysit brings PR to merge-ready and stops. sec-merge merges+prunes on confirm.
- **Not for autonomous routines.** Without a human present, mode is inert; `auto-*` merges stay with
  `wiki-update` W0.
- **Not third-party sends.** Mail/WhatsApp gates are separate.

## Mode state (on / off)

Persistent for the session until turned off.

- **on** (`/sec-merge`, "keep this current"): after producing/updating a session PR, follow loop below.
- **local** (`/sec-merge local`): same as on, but **force local-gate path** for CI (skip remote-green
  requirement; still block on conflicts, human comments, and local validator failures).
- **off** (`/sec-merge off`): no gates; explicit "merge #N" only.

On activate: confirm in one line which session PRs are under care.

## Tier (friction level)

Classify by **files touched** — `gh pr diff <N> --name-only` — not by repo name.

| Tier | PR touches… | On confirm |
|---|---|---|
| **low** | data/prose only: `*.md`, `*/memory/`, `wiki/`, summaries, `*state*.md`, notes | 🚧 → merge+prune without diff |
| **high** | executable: code, workflows, `package.json`, `Makefile`, `.secretary.yml`, build scripts | show diff/summary → merge only after diff confirm |
| **mixed** | any executable line | **high wins** |
| **unclear** | — | default **high** |

## CI gate: remote vs local

Remote CI green is the default merge signal. When CI is **infra-blocked** (GitHub Actions never
actually ran the checks), sec-merge may accept a **local validation gate** instead — but only after
classifying the failure and running validators on the **PR head** (worktree or checkout at branch tip,
not `main`).

| Remote CI state | Classification | sec-merge action |
|---|---|---|
| All required checks **SUCCESS** | `remote-green` | Proceed to tier gate (normal path) |
| Checks **FAILURE** with jobs that **ran** steps and logged test/lint errors | `code-failure` | **Block** — babysit first; do not propose merge |
| All checks **FAILURE** / **CANCELLED** with **~0 steps** (jobs never started or aborted in 2–5s) | `infra-blocked` | Run **local validation gate** on PR head; propose merge if pass |
| Annotation mentions billing, spending limits, quota, or "workflow run was not triggered" | `infra-blocked` | Same local gate |
| `/sec-merge local` active | forced `infra-blocked` path | Local gate even if remote state is ambiguous |
| `~/Dev/*` repo without equivalent local validators | — | **Stay conservative** — report infra-blocked, do not propose merge until remote green or owner explicitly overrides |

**Infra heuristics** (any of these → `infra-blocked`):

- `gh pr checks <N>` or `statusCheckRollup`: all failing checks show 0 steps or near-instant abort
  (2–5s) with no job logs.
- Run annotation / workflow summary mentions Actions billing, spending limit, quota, or org policy
  blocking execution.
- Required checks stuck in `PENDING` then flip to `FAILURE`/`CANCELLED` without a runner picking up.

**Local validation gate** (blocking before merge proposal — run from PR head worktree):

```bash
export SECRETARY_INSTANCE=<pr-worktree-or-checkout>   # absolute path to PR head, NOT main
cd "$SECRETARY_INSTANCE"
secretary validate
python3 scripts/ci/validate_module_contract.py
# contract_health.py + validate_harness_paths.py: warn-only — report in gate, do not block
```

For `~/Dev/*` repos: local gate applies only when the repo exposes an equivalent validator suite
(instance: the four scripts above). If not, stay conservative — surface infra-blocked state and
wait for remote CI or explicit owner override.

**Still block merge** regardless of infra-blocked local gate:

- Merge conflicts (`mergeable: CONFLICTING`)
- Unresolved **human** PR comments (`claude-generated` / `agent-generated` marks do not block)
- Local validators failing (`secretary validate` or `validate_module_contract.py` non-zero)
- CI red because jobs **actually ran** and failed (`code-failure`)

## Loop (when on)

1. **Session PR?** Only PRs this session produced/updated unless owner asks explicitly.
2. **Mergeable?** `gh pr view <N> --json mergeable,mergeStateStatus,statusCheckRollup`.
   - Conflicts or unresolved human comments → babysit first.
   - If `mergeStateStatus` is `BLOCKED` or checks are red → go to **2b**.
   - If green + mergeable → step 3.
2b. **Classify CI** (skip if `/sec-merge local` — treat as `infra-blocked` and run local gate):
   - `infra-blocked` → checkout PR head worktree, run **local validation gate**; on pass → step 3
     with local-gate copy; on fail → babysit / report blockers.
   - `code-failure` → babysit first; do not propose merge until remote green.
   - Ambiguous → default `code-failure` (conservative).
3. **Classify tier** via diff file list.
4. **Raise gate** 🚧 (in-chat + alert per haptics doctrine):
   - low, remote-green: `🚧 _secretary: <PR title> ready — make official?_`
   - low, local-gate: `🚧 _secretary: CI bloqueado (cuota Actions) — validación local OK — ¿merge?_`
   - high, local-gate: diff first, then `🚧 _secretary: <PR title> ready (local gate) — make official?_`
   - high, remote-green: diff first, then same gate as low remote-green.
5. **On confirm:** `gh pr merge <N> --squash --delete-branch` (instance repo: squash only; respect
   other repos' policies).
6. **Signal delivery:** `📬 _secretary delivered — #N merged, branch pruned_`.
7. **Fold linked actions:** if PR or heartbeat cites `acc-id` with open state in meetings memory:

```bash
# Resolve meetings actions path
ACTIONS=$(secretary config path meetings.memory 2>/dev/null)
# Use instance harness acc-fold script if configured — see CLAUDE.md
```

8. **Refresh heartbeat:** invoke `sec-heartbeat`, **commit+push `main`**.

## Guardrails

- Session PRs only unless explicit ask.
- Never merge with **code-failure** CI (jobs ran and failed), conflicts, or unresolved human comments
  (`claude-generated` marks do not block). **Infra-blocked** CI may pass via local validation gate on
  PR head — never substitute local gate when remote jobs actually ran and failed.
- Wiki changes always via PR (CI / `validate_wikilinks.py`).
- High tier always requires diff before merge.
- Gate OK must be explicit for *that* PR.
- Default off for `~/Dev` sessions unless activated there.
- Post-merge heartbeat push is mandatory.

## Output

On activate: `📎 **sec-merge on** — confirmations close PRs (tier-gated)`. Gates and deliveries use
haptics (🚧 / 📬), not skill headers.
