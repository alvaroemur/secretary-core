<!-- agent-generated:sesion runtime=claude-code branch=claude/estado-n0-evaluacion-b86fbe -->

# Status n0: tool evaluation for a live status view and a conductor

**Date:** 2026-11-10. **Source plan:** [frontier-estado-visual-y-conductor-2026-11-10.md](frontier-estado-visual-y-conductor-2026-11-10.md) (record copy, rounds 12 to 14; kept in its original language).
**Scope:** node n0, read-only. Each candidate's code was cloned (`--depth 1`, git hooks disabled) into a separate directory and read without running it. Nothing was installed, no binary or script was run, and no transcript was read.
**Maintenance data as of:** 2026-11-10 (GitHub API). "Issues" is `open_issues_count`, which includes open PRs.

## Summary

No candidate meets all the owner's criteria at once. The ones that cover several agent harnesses own the sessions (tmux, their own terminals, or their own worktrees). The ones that observe without owning cover Claude Code only, expose transcript content, or have no license. None reads `docs/plans`.

**Recommendation:** a thin layer of our own (transcript adapters, metadata only) plus a plan reader and the conductor, borrowing two proven designs: the `kanban-code` reconciler (session → branch → path) and the hooks + transcript watcher scheme of `claude-vigie`. No candidate is adopted as a whole. Details and reasons are in "Recommendation".

## Comparison table

Legend: ✅ meets, ⚠️ partial or unverified, ❌ does not meet.

| Criterion | kanban-code | agent-of-empires (AoE) | Nimbalyst | herdr |
|---|---|---|---|---|
| Harnesses | ⚠️ Claude Code. The Windows app adds Codex and Gemini (`windows/src-tauri/src/session_discovery.rs:230-236`). Cursor: no evidence | ✅ Claude, Codex, Gemini, Cursor (`src/agents.rs:744,766,791`) and others | ⚠️ Claude Code and Codex; OpenCode and Copilot in alpha. Cursor not listed (`README.md:26`) | ✅ Claude Code, Codex, Cursor, OpenCode, Grok (`README.md:35`) |
| Sees Claude desktop app sessions | ⚠️ Discovers `~/.claude/projects` (`README.md:134`), so it should; not tested | ⚠️ Only imports Claude sessions into its structured view (`src/session/claude_import.rs:1-5`); no evidence it observes foreign sessions | ❌ Owns its own sessions; no evidence it observes foreign ones | ❌ "Owns their terminals" (`README.md:35`); does not observe sessions started by other apps |
| Reads `docs/plans` (`id`/`goal`/`status`, nodes) | ❌ No plan reader (searched `Sources/` and `cli/src/`) | ❌ No | ⚠️ Has a planning system, but in `plans/` with `planStatus.planId` frontmatter (`docs/PLANNING_SYSTEM.md:15-34`), a different schema | ❌ No |
| Creates no worktrees, owns no sessions | ⚠️ Worktree and tmux are optional, and it reconciles existing ones (`README.md:140-144,315`) | ❌ One tmux session per agent, optional worktree (`README.md:28,66`) | ❌ One worktree per session (`README.md:23`) | ❌ Owns the terminals |
| License | ✅ Apache-2.0 | ✅ MIT | ✅ MIT (sync server is separate, `LICENSING.md`) | ✅ Apache-2.0 |
| Last push · issues · release | 2026-11-08 · 19 · v0.1.32 (2026-08-10) | 2026-11-10 · 355 · v1.22.3 (2026-11-09) | 2026-11-10 · 824 · v0.83.0 (2026-11-10) | 2026-11-07 · 460 · v0.9.5 (2026-10-14) |
| Context cost | ✅ CLI with `--json` on every command (`README.md:90,103`) | ⚠️ `aoe list --json` (`docs/cli/reference.md:278,307`) and an HTTP API; large surface | ❌ Large Electron app; no status CLI | ✅ CLI with JSON on most commands (`skills/herdr/SKILL.md:45`) and a socket |
| Live local HTML | ⚠️ Native app (macOS 26 or Windows); a `web/` folder exists but I did not verify that it serves status | ✅ `aoe serve`, loopback with token by default (`docs/guides/mcp-control.md:14`) | ❌ Desktop app; no documented local web view | ❌ TUI; no documented web |
| Metadata only (no content) | ⚠️ Reads transcripts for tokens and context; no metadata-only guarantee | ❌ Extracts the first human prompt as the title (`claude_import.rs:15-17`) | ❌ Shows session content by design | ⚠️ Does not read transcripts; does capture terminals |
| Risk to `~/.claude/settings.json` | ⚠️ Offers to install hooks on first launch (`README.md:217-219`) | ✅ Only reads `tui` (`src/claude_settings.rs:10-31`); own per-agent sidecar hooks | ⚠️ Not verified | ⚠️ Writes hooks into settings.json (`src/integration/claude_settings.rs:13,68`) |

| Criterion | agent-console (eqtylab) | ccmon (elct9620) / ccmonitor (tobyilee) | claude-vigie (haribo) | vigie (stoneariel491-sudo) |
|---|---|---|---|---|
| Harnesses | ❌ Claude Code only (README title). The plan said Claude and Codex; I did not find that | ❌ Claude Code only | ❌ Claude Code only (`README.md`, no mention of Codex or Cursor) | ✅ Claude, Codex, Gemini, OpenCode, Cursor (experimental) (`README.md:56,126`) |
| Sees desktop app sessions | ⚠️ Reads Claude Code transcripts | ccmon: ❌ does not see sessions (OTLP telemetry only). ccmonitor: ⚠️ reads `~/.claude` every 2 s (`README.md:7`) | ⚠️ The watcher scans transcripts and covers sessions without hooks (`README.md:72-74`) | ⚠️ Reads `.claude/projects` (`README.md:72`) |
| Reads `docs/plans` | ❌ | ❌ ccmonitor only shows the session's own plan file (`README.md:54,92`) | ❌ | ❌ |
| Owns no sessions | ✅ Read-only | ✅ Read-only | ✅ Read-only ("watches and signals, never steers") | ✅ Read-only |
| License | ❌ None (all rights reserved) | ✅ ccmon Apache-2.0; ccmonitor MIT | ✅ MIT | ✅ MIT |
| Last push · issues · release | 2025-12-30 · 1 · no releases | ccmon 2026-09-02 · 2 · v0.9.4 (2026-03-19). ccmonitor 2026-10-10 · 1 | 2026-11-08 · 5 · no release verified | 2026-11-03 · 0 · repository created 2026-10-29, 0 stars |
| Context cost | ⚠️ Tauri app; no CLI | ccmon: TUI with an OTLP server. ccmonitor: TUI | ⚠️ Go binary with TUI, web and `vigie ...` commands | ⚠️ Desktop app |
| Live local HTML | ❌ Desktop app | ❌ TUI | ✅ Read-only web dashboard served by the daemon, default `--addr` `127.0.0.1:8080` (`docs/deployment.md:14`) | ❌ Desktop app |
| Metadata only | ❌ Shows the full conversation | ❌ ccmonitor shows the last prompt (`README.md:99`) | ⚠️ Names the session from the transcript (`README.md:29`); content not verified | ❌ Shows what the agents "think" and writes translated copies of transcripts (`README.md:79`) |
| Risk to `~/.claude/settings.json` | ✅ No hooks | ✅ ccmon uses environment variables | ⚠️ `vigie hooks install` edits settings.json; optional, a hook-free watcher exists (`README.md:149-152`) | ✅ No hooks |

## Notes per candidate

- **kanban-code** has the data model closest to the request: a card links session, worktree, branch and PR, and a reconciler merges them by session ID, then branch, then path (`README.md:315`). It falls short on harness coverage and does not know about plans. It is a native app that requires macOS 26 (`README.md:48`).
- **agent-of-empires** is the only multi-harness candidate with a local web view, but its model is to own the session (tmux). Living next to the Claude desktop app sessions would mean two parallel worlds.
- **Nimbalyst** competes with the whole product (editor, worktrees, plans). Its plan schema (`planStatus`, `plans/` folder) does not match this repo's. Maintenance is very active, but it has 824 issues and a huge scope.
- **herdr** has strong traction (49,844 stars) and a good CLI and socket, but its premise is to own the terminals.
- **agent-console** is discarded: no license, no maintenance since December 2025, Claude Code only, and it exposes content.
- **ccmon** and **ccmonitor** measure cost and usage, not per-repo status. Discarded for this purpose.
- **vigie**: the name is ambiguous (see "Not verified"). `haribo/claude-vigie` matches the pattern described in the plan (hooks and a transcript watcher feeding a local server with SSE and a read-only web dashboard). `stoneariel491-sudo/vigie` is multi-harness but exposes content, is a week old and has an author with no history; running it over transcripts is not recommended.
- **La Vigie** (`la-vigie/la-vigie`, MIT, last commit 2026-09-15) showed up in the search: another app that creates a worktree per task. Out by the no-worktrees criterion.

## Recommendation

**A thin layer of our own, without adopting a complete candidate.** Reasons:

1. The decisive criteria exclude each other in the market reviewed. Multi-harness plus a local web panel (AoE, herdr) implies owning the sessions. Observing without owning (kanban-code, claude-vigie) implies Claude Code only.
2. The privacy requirement (PRV-1: metadata only) rules out the ones that show content (agent-console, stoneariel491's vigie, ccmonitor, Nimbalyst) or extract it as a title (AoE).
3. Nobody reads `docs/plans` or the `nX` nodes. That part has to be written whichever option is chosen, and it is the core value of the conductor.
4. The transcripts of all three harnesses are already on disk and the owner verified their paths. An adapter that reads only metadata fields (session id, `cwd`, branch, timestamps) is small and does not depend on a third-party project that changes formats.
5. The hooks in `~/.claude/settings.json` already cover 10 events. A layer of our own can rely on the transcript watcher and avoid writing new hooks.

**What is taken from the candidates (ideas, not code):**
- From kanban-code: reconcile by session ID, branch and path; a card with optional sub-structures (`README.md:313-315`).
- From claude-vigie: hooks as an optional fast signal and a transcript watcher as fallback; a read-only web panel on `127.0.0.1` with SSE.
- From herdr: JSON on every command, with output designed for an agent to consume.
- From Nimbalyst: consider accepting its `planStatus` frontmatter as a read alias, only if the owner uses Nimbalyst.

**Alternative if the owner prefers to adopt:** `claude-vigie` as the Claude Code panel while the rest is built. It covers one harness only and forces edits to settings.json if hooks are enabled; it is not a base for the conductor.

## Not verified

- **Claude desktop app sessions.** No candidate shows evidence of treating them as such. I do not know where the app stores its session metadata (title, worktree, parent/child relation) outside the transcripts. This is the biggest risk of n1 and needs a spike before building.
- **Real execution.** Nothing was installed or run. Every claim comes from READMEs, documentation and source code.
- **Cursor support in kanban-code, Nimbalyst and claude-vigie.** No evidence; not fully ruled out.
- **kanban-code `web/`.** A web client exists; I did not check whether it serves local status or on which interface it listens.
- **herdr, full documentation.** It lives at herdr.dev, which I did not consult. The absence of a web view or status JSON is based on the README and `skills/herdr/SKILL.md`.
- **AoE observing foreign sessions.** I found no evidence that it does, and no statement that it cannot.
- **Which "ccmon" and "vigie" the plan means.** Several projects share those names. I evaluated `elct9620/ccmon`, `tobyilee/ccmonitor`, `haribo/claude-vigie` and `stoneariel491-sudo/vigie`. If the owner meant others, say so.
- **Nimbalyst telemetry.** The documentation mentions analytics; I did not check what it sends.
- **Transcript formats.** I did not open them, per the rules. The plan already records the paths; the exact field names are left for the n1 spike.
- **Issue counters.** They include PRs and do not separate bugs from requests.

## Proposed next nodes

All wait for the owner's approval of this evaluation (given on 2026-11-10 for n0). None has been built.

| Node | What | Depends on | Notes |
|---|---|---|---|
| n1a | Source spike: where the Claude desktop app stores each session's title, branch and worktree; which metadata fields Claude Code, Codex and Cursor expose. Field names only | n0 approval | Resolves the biggest risk. No content is read |
| n1 | Core: `secretary estado --json`. Per-harness adapters, the PRV-1 metadata schema, plan reader (PLN-1), session → branch → path → PR reconciler | n1a | Stable contract for everything else. Does not touch `~/.claude/settings.json` |
| n2 | Live HTML: server on `127.0.0.1` with SSE over the core; read-only | n1 | HTM-1. No external access |
| n3 | Minimal conductor: thin skill that reads the core (or `desk-overview` meanwhile) and speaks on open, relation detected and close | n1 (can start earlier with current sources, CND-5) | CND-1 to CND-4. Writes to the plan only with approval |
| n4 | Cross-harness handoff: 4 KB block, `.briefs`, paste-ready block per harness | n1, n3 | SAL-1 |
| n5 | Chat over the status | n2 | CHT-1: after v0 |

Suggested order: n1a → n1 → (n2, n3 in parallel) → n4 → n5.
