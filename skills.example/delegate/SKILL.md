---
name: delegate
description: >-
  Offload an idea, task, or datum from the current session without derailing active work. With an
  active thread, spawns a local continuable chip session for triage (wiki / issue / execute). Modes
  — STARTUP (empty session: this session becomes the work session), WITH-CONTEXT (idea builds
  on current work), BLOB (unrelated "aha" — opaque note, processed from secretary like extractor
  output), CROSS-SESSION (send to an already-active sibling session instead of spawning a new one).
  Triggers: "/delegate", "delegate this", "note for later", "aha", "not now but remember", "send
  this to the other session". NOT for completed-work handovers (/handover).
---

# delegate — offload without derailing

When the owner thinks of something **while working on something else**, delegate removes it from
this session without losing the thread.

Doctrine: `rules/skills-contract.md`

## Core model — platform-agnostic

At its core, delegate is two things, independent of tooling:

1. **An issue** in the destination repo — the durable, referenceable record of the work.
2. **A clean-context restart strategy** — a self-contained prompt/brief that lets any session
   (any platform) pick the work up fresh.

Everything below — chips via `spawn_task`, STARTUP mode — is the **Codex playbook** of
that core. Other platforms apply their own playbook: **Cursor** → issue + brief in the target
repo's `.briefs/` + paste-ready prompt (cf. `to-cursor`). When no playbook exists for the
active platform, fall back to the core: create the issue and emit the restart prompt.

**Pick the playbook by capability, not by platform name.** This file is read by more than one
client (Cursor discovers `~/.agents/skills/` too). If the `spawn_task` tool exists in your
toolset → chip playbook below. If not (Cursor, plain CLI) → Cursor/core playbook: create the
issue, write the self-contained brief (`.briefs/` when in Cursor; resolve via
`secretary config path session.briefs` in an instance, else literal `.briefs/`), and hand the
owner a paste-ready restart prompt. Never call tools you don't have.

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
```

**Resolve working directories** from config and instance doctrine — never hardcode absolute paths:

```bash
# Instance root (blob mode default; secretary domain work)
echo "$SECRETARY_INSTANCE"

# Dispatch allowlist: repo slug + local path
echo "$CFG" | jq -r '.dispatch.executor.repos[] | "\(.repo)\t\(.path)"'

# Cowork / Dev workspace map (client → workspace)
# → instance AGENTS.md + operational/sistemas-ordenamiento.md
```

## Modes

**Gate 0 — empty / just-started session?** If `/delegate` is the first substantive action and no
thread to protect → **STARTUP mode**: do not spawn a chip; *this* session becomes the work session.

**Gate 0.5 — is there an already-active sibling session for this item?** See **Cross-session mode**
below. Only enters when the owner asks explicitly, or a narrow same-`cwd` heuristic fires — this
gate does not fire on every delegate.

If a thread needs protection and Gate 0.5 didn't fire, choose chip mode by **framing**, not content:

- **WITH-CONTEXT** — idea builds on current work (references artifacts being touched).
- **BLOB** — unrelated "remember this"; treat as opaque; do not analyze content for routing.

Owner can force: "startup" / "with-context" / "blob" / "cross-session". When unsure between chip
modes → **blob**.

## Cross-session mode

**When it exists:** a sibling session is already active on the same external object (a Gmail
thread, a sheet, a PR) and the item belongs there instead of a new chip. Spawning a third session
to coordinate two others doesn't scale — this mode sends the payload directly to the sibling
turn.

**Entry (Gate 0.5) — narrow by design, to avoid noise:**

- **Explicit** — owner says "/delegate cross-session", "/delegate → <session>", "mándale esto a la
  sesión X", or similar. Always honored.
- **Heuristic (only case where the skill asks proactively)** — `mcp__ccd_session_mgmt__list_sessions`
  shows **exactly one** other active session whose `cwd` matches the current session's `cwd`. In
  that narrow case,
  offer once: "¿Esto es para la sesión activa en este mismo repo, o delegate normal?" Any other
  shape (zero matches, more than one match, matches in a different `cwd`) → **do not ask**, fall
  through to the normal chip/startup flow. This keeps the gate quiet by default (DD-2, spec 002).

**Protocol:**

1. **Capture the payload verbatim** (same as chip modes).
2. **List active sessions** — `mcp__ccd_session_mgmt__list_sessions` (harness session catalog;
   distinct from `mcp__ccd_session__*`, which is this skill's own spawn/chip toolset). Filter/sort
   for presentation (DD-3):
   - If invoked with a target already named (explicit entry), skip straight to matching by title
     substring or `sessionId`.
   - Otherwise show a short numbered list, same-`cwd` sessions first, then `isRunning: true`
     before idle ones, each row: `title` · `cwd` (basename) · PR if any · running flag. Cap at
     ~5 rows; more than that, ask the owner to name the session instead of dumping the full list.
3. **Owner picks the destination** (number, title, or `sessionId`). No match / owner says "new
   session instead" → fall back to spawn (chip mode), do not force cross-session.
4. **Build the message** with an explicit marker as the first line (DD-4) — cheap to add, makes
   the turn greppable/self-describing for the destination session even though the harness already
   attributes the sender automatically:

   ```
   [DISPATCH CROSS-SESSION desde: <título de la sesión origen>]

   Álvaro te manda esto desde otra sesión:

   <payload verbatim>

   [Referencias: <threadId / draftId / spreadsheetId / PR# si los hay>]

   [Acción solicitada: <instrucción breve si Álvaro dio una — opcional>]
   ```

5. **Send** via `mcp__ccd_session_mgmt__send_message` with the chosen `sessionId`. The harness
   requires the owner's explicit confirmation before delivery — never bypass or assume
   auto/bypass-permissions mode; this is a non-negotiable guardrail, not something the skill
   re-implements.
6. **Confirm in one line** and resume the current thread — no third session opened, no chip
   spawned.

**No relevant active sessions** → say so in one line and fall back to the normal spawn flow (chip
or startup mode) as if Gate 0.5 had not fired.

## Principles (chip modes)

1. **Do not process the item in this session** — only delegate and resume your work.
2. **Do not reinterpret or improve text** — pass verbatim (obvious typos only).
3. **Do not use the `Agent` subagent tool** — destination is a real continuable session (`spawn_task`).
4. **Do not interrogate** — unless input is empty ("What should I delegate?").
5. **In blob mode, do not touch content** — no routing, titling, or summarizing.

## Chip mode steps

> STARTUP mode → skip to **Startup mode** section.

1. Capture text verbatim.
2. Choose mode (with-context / blob).
3. **Determine `cwd`:**
   - **Blob → always `SECRETARY_INSTANCE`.** Processed like extractor routine output.
   - **With-context → route by topic:**
     - Mail, wiki, whatsapp, meetings, agenda, secretary → `SECRETARY_INSTANCE`
     - Client/workspace repos → match path from `dispatch.executor.repos` or instance `AGENTS.md`
       Cowork map (`inspiro`, `ennui`, other workspaces)
     - Dev code repo → path from allowlist entry or instance `AGENTS.md` Dev section
     - If unclear, omit `cwd`
   - **Granularity:** workspace level only — never a deep project subfolder as `cwd`; put specific
     paths in the `prompt`, not `cwd`.
4. **Spawn chip** (`mcp__ccd_session__spawn_task`):
   - `title`: short imperative, <60 chars. Blob: neutral generic title.
   - `tldr`: 1–2 sentences. Blob: triage note for wiki/issue/actions.
   - `cwd`: from step 3 (blob → instance root).
   - `prompt`: mode template below with verbatim `<BLOB>`.
5. **Confirm in one line** and resume. Example: *"Dispatched (blob) → chip created."*

## Startup mode (empty session)

This session **is** the destination. Process and interpret content to choose repo and branch.

1. Capture topic from owner input.
2. **Choose workspace repo** using allowlist + instance `AGENTS.md` (secretary / Cowork / Dev).
   If truly ambiguous, ask which workspace (only allowed question in startup).
3. `cd` to repo. Fresh `origin/main`. **Do not build on merged/dead branches** (`[gone]` upstream).
4. Open work path:
   - `git switch -c <scope>/<short-desc> origin/main`
   - Minimal initial commit if needed
   - Open **draft PR** (Conventional Commits per instance `AGENTS.md`)
5. Confirm setup (repo, branch, PR link) and **continue developing here**.

Default axis is execute (develop in PR). Durable knowledge → `wiki-write`; backlog → issue.

## Destination triage (chip modes)

Classify into one or more:

- **WIKI** — durable knowledge → `wiki-write`, source `delegate`
- **ISSUE** — do later / blocked / vague → `gh issue create` with repo labels if any (**signature
  mandatory** — see below). If the new
  issue lists related issues under `## Relacionado`, add the reciprocal link back on each of those
  (short comment suffices) — see `rules/issues-relacionados.md`. One-way links are how related
  issues go stale without anyone noticing.
- **EXECUTE** — actionable now (~15 min concrete progress) → branch + PR (draft if incomplete); no
  merge without owner review

When unsure issue vs execute → issue. Can combine wiki + issue/execute.

## GitHub signature (mandatory)

Before `gh issue create`, `gh pr create`, or `gh issue comment`, set context and generate the
signature (`rules/github-signatures.md`):

```bash
export SECRETARY_SKILL=delegate
export SECRETARY_BRANCH=$(git branch --show-current 2>/dev/null || true)
SIG_MARK=$(~/.claude/scripts/sec-signature.sh delegate --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh delegate --footer)
# Body: "${SIG_MARK}\n\n<content>\n\n---\n${SIG_FOOT}"
```

Unsigned issues (e.g. #493) are a regression — never skip this step.

## Template — BLOB

```
This is a note the owner dispatched in BLOB mode from another session — an unrelated "remember this"
without your context. Treat as raw extractor-style input.

NOTE (verbatim):
<BLOB>

Process autonomously (owner is not waiting for check-in). Triage:

- WIKI: durable knowledge → wiki-write, source "delegate"
- ISSUE: backlog → gh issue create
- EXECUTE: actionable → branch + PR (draft if incomplete); no merge without review

Report briefly with links (wiki, issue, PR).
```

`cwd` = `SECRETARY_INSTANCE`.

## Template — WITH-CONTEXT

```
The owner dispatched this from a session working on the following. Use as context.

ORIGIN CONTEXT:
<brief summary: repo/files/PR and state>

IDEA (verbatim):
<BLOB>

Triage; state choice in one line, then proceed (wiki / issue / execute per criteria above).
```

## Suggested delegate — domain gate (session-initiated)

Besides owner-triggered delegate, any session may **offer** delegate when it detects the work
does not belong to the active repo (issue #191 of the instance):

- **Trigger moment:** intent to *produce* — creating deliverable files, opening a branch,
  generating an artifact for an org/project with its own home in `~/Cowork/` or `~/Dev/`.
- **Test:** does this output have a natural home other than the active repo? Answer with the
  active repo's declared role (its `AGENTS.md`) + the instance workspace map.
- **Strongest case:** the secretary instance is capture/consolidation — almost any *execution*
  starting there is a delegate candidate.
- **Suggestion, not action:** signal `💡` (notice tier) and offer delegate to the right repo
  using the active platform's playbook (Codex: STARTUP mode or chip; elsewhere: issue +
  restart prompt). The owner decides; never migrate work unilaterally.

## Notes

- One idea = one chip. Click-to-open is intentional validation before the destination runs.
- Embodies manual "delegate" from secretary README — owner-triggered, not auto-extracted.


## Registro y ejecución

Lee `../desk-context/references/control.md`. Crear un issue o una sesión no habilita un trabajo autónomo. Registra propuestas como `desk:decision` si requieren elección. Si ya existe una instrucción explícita de ejecutar, respeta su alcance y registra la fuente. Para trabajo preparable por la regla `prepare-pr-v1`, registra el metadato de propuesta y deja que work-runner compruebe elegibilidad; no inventes una autorización del propietario. Selecciona la mecánica por capacidad: spawn_task; si falta y se autorizó una nueva sesión, create_thread (list_projects primero); sin ambas, issue y prompt de reinicio. Un hilo activo se protege con una sesión continuable, no con un subagente. En STARTUP esta sesión sigue siendo el destino.


Sin Secretary disponible, usa las reglas y remoto del repo destino, crea el issue autorizado y prepara el prompt/brief de reinicio. No exige memoria, heartbeat ni el brief para funcionar. Mantén los mismos límites de autorización.
