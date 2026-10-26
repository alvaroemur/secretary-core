---
name: desk-merge
description: >-
  Persistent secretary mode that keeps session work "current" (merged to main). When a session PR
  becomes mergeable, raises a 🚧 gate and, on confirmation, merges with a merge commit and
  fast-forwards the local main — tier-gated: data/prose merges on "yes", executable code shows
  diff first. The only merge executor; wind-down proposes, desk-merge merges. Secretary's merge-on-confirm layer above
  babysit. Triggers: "/desk-merge", "keep this current", "merge-on-confirm on/off", or at session
  start when owner wants OKs to close PRs.
---

# desk-merge — merge on confirmation

**What this does:** close the gap between "reviewed in chat" and "merged to `main`". Owner review in live
sessions becomes what merges, instead of leaving PRs hanging until `wiki-update` W0 or manual GitHub.

Doctrine: `rules/skills-contract.md` · instance git policy `canon/rules/git/integracion.md`

## Instance setup

```bash
eval "$(secretary env)"
```

Haptics: `secretary` CLI or instance harness scripts for compuerta/delivery signals (see
`rules/sec-haptics.md`). Do not hardcode script paths — resolve from harness `AGENTS.md` if needed.

## What this is NOT

- **Not babysit.** Babysit brings PR to merge-ready and stops. desk-merge merges on confirm.
- **Not a general cleanup.** After its own merge it removes that PR's remote branch, local
  branch and worktree (step 5c). Other integrated worktrees are wind-down's job.
- **Not for autonomous routines.** Without a human present, mode is inert; `auto-*` merges stay with
  `wiki-update` W0.
- **Not third-party sends.** Mail/WhatsApp gates are separate.

## Mode state (on / off)

Persistent for the session until turned off.

- **on** (`/desk-merge`, "keep this current"): after producing/updating a session PR, follow loop below.
- **local** (`/desk-merge local`): same as on, but **force local-gate path** for CI (skip remote-green
  requirement; still block on conflicts, human comments, and local validator failures).
- **off** (`/desk-merge off`): no gates; explicit "merge #N" only.

On activate: confirm in one line which session PRs are under care.

## Tier (friction level)

Classify by **files touched** — `gh pr diff <N> --name-only` — not by repo name.

| Tier | PR touches… | On confirm |
|---|---|---|
| **low** | data/prose only: `*.md`, `*/memory/`, `wiki/`, summaries, `*state*.md`, notes | 🚧 → merge without diff |
| **high** | executable: code, workflows, `package.json`, `Makefile`, `.secretary.yml`, build scripts | show diff/summary → merge only after diff confirm |
| **mixed** | any executable line | **high wins** |
| **unclear** | — | default **high** |

## CI gate: remote vs local

Remote CI green is the default merge signal. When CI is **infra-blocked** (GitHub Actions never
actually ran the checks), desk-merge may accept a **local validation gate** instead — but only after
classifying the failure and running validators on the **PR head** (worktree or checkout at branch tip,
not `main`).

| Remote CI state | Classification | desk-merge action |
|---|---|---|
| All required checks **SUCCESS** | `remote-green` | Proceed to tier gate (normal path) |
| Checks **FAILURE** with jobs that **ran** steps and logged test/lint errors | `code-failure` | **Block** — babysit first; do not propose merge |
| All checks **FAILURE** / **CANCELLED** with **~0 steps** (jobs never started or aborted in 2–5s) | `infra-blocked` | Run **local validation gate** on PR head; propose merge if pass |
| Annotation mentions billing, spending limits, quota, or "workflow run was not triggered" | `infra-blocked` | Same local gate |
| `/desk-merge local` active | forced `infra-blocked` path | Local gate even if remote state is ambiguous |
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
- Unresolved **human** PR comments (`Codex-generated` / `agent-generated` marks do not block)
- Local validators failing (`secretary validate` or `validate_module_contract.py` non-zero)
- CI red because jobs **actually ran** and failed (`code-failure`)

## Loop (when on)

1. **Session PR?** Only PRs this session produced/updated unless owner asks explicitly.
2. **Mergeable?** `gh pr view <N> --json mergeable,mergeStateStatus,statusCheckRollup`.
   - Conflicts or unresolved human comments → babysit first.
   - If `mergeStateStatus` is `BLOCKED` or checks are red → go to **2b**.
   - If green + mergeable → step 3.
2b. **Classify CI** (skip if `/desk-merge local` — treat as `infra-blocked` and run local gate):
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
5. **On confirm:** `gh pr merge <N> --merge`. Merge commit only: squash and rebase are disabled
   by policy. Do not pass `--delete-branch`: step 5c removes the branches after checking the
   worktree. If the repo still rejects merge commits
   (`gh api repos/<owner/repo> -q .allow_merge_commit` is false), stop and report; never fall
   back to squash.
5b. **Update the local main:** in the repo's main checkout, only if it is on `main` and clean:
   `git -C <main-checkout> fetch origin && git -C <main-checkout> merge --ff-only origin/main`.
   Otherwise report why it was skipped.
5c. **Remove what the merge integrated** (CLN-2). After `git fetch origin`, confirm
   `git merge-base --is-ancestor <branch> origin/main`, then:
   - remote branch: `git push origin --delete <branch>` if `git ls-remote --exit-code --heads origin <branch>` finds it;
   - worktree `<repo>/.wt/<branch-slug>`: `git worktree remove <wt>` only if it is clean
     (`git -C <wt> status --porcelain` empty, untracked included), no process has its cwd there
     (`lsof -a -d cwd -Fn | grep -F <wt>` empty) and it is not the folder this session runs in;
   - local branch: `git branch -d <branch>` once no worktree holds it.
   If a condition fails, keep that piece and name the condition in the delivery line. Never remove a
   harness-managed worktree (`.claude/worktrees`, `~/.codex/worktrees`, `~/.cursor/worktrees`).
6. **Signal delivery:** `📬 _secretary delivered — #N merged (merge commit), main updated, branch and worktree removed_`
   (or name what was kept and why).
7. **Fold linked actions:** if PR or heartbeat cites `acc-id` with open state in meetings memory:

```bash
# Resolve meetings actions path
ACTIONS=$(secretary config path meetings.memory 2>/dev/null)
# Use instance harness acc-fold script if configured — see AGENTS.md
```

8. **Heartbeat:** the heartbeat routine (`playbooks/sec-heartbeat/procedure.md`) picks the merge
   up on its next run; do not run it by hand.

## Owner override → lesson (dream/desk-drone PRs only)

Detectable signal for `cowork-secretary#509` (loop de aprendizajes): at step 4 (raise gate), if the
PR's branch is `dream/*` (or otherwise authored by the dream routine, `playbooks/sec-dream/procedure.md`,
or desk-drone) **and** the owner's response
is a **substantive correction** rather than a plain confirmation ("yes", "dale", "ok") — e.g. they
point out a wrong interpretation, ask to re-verify a claim, or edit the deliverable's content before
merging — treat that as an owner override. Append a stub entry to
`$SECRETARY_INSTANCE/subsystem/dream/lessons.md` (same append-only format as existing entries: what
failed, the correction, the rule going forward) before merging. A plain "looks good, merge" is not an
override — do not log noise.

## Guardrails

- Session PRs only unless explicit ask.
- Never merge with **code-failure** CI (jobs ran and failed), conflicts, or unresolved human comments
  (`Codex-generated` marks do not block). **Infra-blocked** CI may pass via local validation gate on
  PR head — never substitute local gate when remote jobs actually ran and failed.
- Wiki changes always via PR (CI / `validate_wikilinks.py`).
- High tier always requires diff before merge.
- Gate OK must be explicit for *that* PR.
- Default off for `~/Dev` sessions unless activated there, or invoked by wind-down after the
  owner confirms that PR's merge.
- Never squash, never `--delete-branch`; remove branches and worktree only through step 5c.

## Output

On activate: `📎 **desk-merge on** — confirmations close PRs (tier-gated)`. Gates and deliveries use
haptics (🚧 / 📬), not skill headers.
