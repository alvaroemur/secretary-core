---
name: sec-compose
description: >-
  Distill material plus a recipient into 1-2 copy-ready message drafts, anchored in prior
  conversation history with that person. Use when a session wants to share something with a
  contact and needs a draft contextualized by the relationship — never to send.
---

# sec-compose — relationship-anchored drafts

**Mission:** turn `(material, recipient)` into copy-ready message drafts, anchored in prior
conversation history with that recipient — so sharing lands in relationship context, not cold.

Doctrine: `rules/skills-contract.md`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
```

## Guardrails

- **Persist before copy-ready.** Write the MD file (or confirm no writable path applies) before
  returning drafts in chat — per `operational/sistemas-ordenamiento.md` §7.
- **Never sends.** Output is always text to copy. Delivering to a third party is a separate,
  explicitly authorized step — out of scope here.
- **Run isolated.** Do heavy reading (recall + meetings scan + drafting) inside a spawned subagent
  so the calling session stays clean. Return only drafts and the anchor note.
- **Read-only over memory.** Do not write to wiki or module memory. No `sec:pending` annotation
  of "shared X" until the owner confirms it was actually sent.
- **Anchor by topic, not recency.** The relevant prior conversation is about *this* material's
  subject, not merely the latest one.
- **Do not invent shared history.** If no prior conversation touches the topic, say so and return
  only the cold-open variant.

## Policies (read before persisting MD or `channel: correo`)

| Policy | Config key |
|--------|------------|
| Signature and tone | `mail.settings` → `extractors/mail/settings.md` |
| Routing, naming, persistence (borradores) | `operational.sistemas_ordenamiento` |
| Skills vs config pattern | `operational.skills_vs_operational` |

```bash
secretary config path mail.settings
secretary config path operational.sistemas_ordenamiento
git -C "$SECRETARY_INSTANCE" show origin/main:extractors/mail/settings.md
git -C "$SECRETARY_INSTANCE" show origin/main:operational/sistemas-ordenamiento.md
```

## Loop

1. Gather inputs: `material` (text/link/idea), `recipient` (person in memory), optionally `channel`,
   `tone`, and `tema` (explicit topic override — skip inference when provided).
2. **Read policy** if `channel: correo` or persisting an MD file (`mail.settings`, `sistemas_ordenamiento` §6–7).
3. Spawn an isolated subagent for the rest (steps 4–9). Read + draft only — no write skills.
4. Resolve recipient → wiki article via `.secretary.yml`; run `sec-recall` on the person.
5. **Infer or accept tema** → if `tema` was passed, use it as the search query as-is; otherwise extract
   key concepts from `material` (e.g. "vector DBs", "embeddings", "RAG").
6. **Anchor search** → scan meeting summaries and memory for prior conversations with this recipient
   where the tema appears. Resolve paths via `secretary config path meetings.summaries` and
   `meetings.memory`; also run the *Unmerged scan* below so same-day reunions not yet on `main` are
   not missed.
7. **Select anchor** → among candidates, pick the **most topically relevant** conversation — not the
   most recent by default. Report the choice explicitly: source, date, and why it fits the material.
   If User prefers another candidate, he can correct before sending.
8. Compose 1–2 drafts for `channel`: **cold open** and, if an anchor exists, **continuation**.
   Match the natural register of the relationship.
9. Return drafts plus the anchor report. **No memory writes** — `sec-write` only if User later
   confirms the message was sent (outside this pipeline).

### Unmerged scan (anchor search)

Evidence captured by `reuniones-update` but not yet merged lives on an open `auto-*` PR branch,
invisible to the checkout on `main`. Mirror `sec-recall`'s anti-amnesia pass — a meeting summarized
this morning won't be on `main` until the PR merges.

```bash
CFG=$(secretary config show)
INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
PAT='^(mail|correo|meetings|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$'
git -C "$INSTANCE" fetch origin --quiet

gh pr list --repo "$BRIEF_REPO" --state open \
  --json number,headRefName,title \
  --jq ".[] | select(.headRefName | test(\"$PAT\"))"

# Read a file from a PR branch without checkout:
git -C "$INSTANCE" show "origin/<branch>:<path>"
gh pr diff <N> --repo "$BRIEF_REPO" | grep -i "<tema-or-recipient>"
```

Only surface unmerged evidence that matches the recipient + tema. Mark tentative anchors
`⏳ tentative (unmerged, PR #N)` in the anchor report.

### Signature (`channel: correo`)

Apply rules from `mail.settings` — closing, register, formal vs warm. Do not duplicate signature
blocks in this skill.

### Persist MD mirror (when deliverable is a file, not chat only)

Per `operational/sistemas-ordenamiento.md` §6.1 (instance `CLAUDE.md` for Cowork workspace layout):

- Active project → `proyectos/<slug>/borradores/` or `<contacto-slug>/` when applicable.
- **Not** `extractors/mail/drafts/` for project work.
- Naming: `borrador-correo-<slug>-YYYY-MM-DD.md` with YAML frontmatter — template
  `templates/borrador-correo-proyecto.md` (`status`, `para`, `asunto`, `fecha`, …).

**Handoff to Gmail:** for in-thread draft → `sec-mail` with `intent=draft`; sec-mail applies
MD→plain conversion, signature from settings, and typo review before `gog gmail drafts create`.

## Report

Render **inline**. Header: `✉️ **Drafts — for <recipient>** · 📌 anchor: `` `source:date` `` — <why it fits>` (or "no prior anchor" → cold open only). Tentative unmerged anchors keep the `⏳ tentative (unmerged, PR #N)` marker. Then 1–2 drafts on labeled lines: **Cold open** › "…" and **Continuation** › "…". If an MD file was written, include its absolute path. Keep commentary minimal — drafts are the deliverable.

If the draft responds to a brief item:

> Already sent? `secretary status "✅" "<ref>" "<note>"`

Do not run the script — offer the copy-ready line only.
