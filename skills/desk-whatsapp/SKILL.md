---
name: desk-whatsapp
description: >-
  Fresh check on a WhatsApp chat or contact — capture-stream health, whitelist
  status, memory/inbox state, and copy-ready draft composition. Stream is
  currently paused (Baileys session unauthenticated); this skill surfaces that
  status honestly instead of pretending live data exists. Triggers:
  "/desk-whatsapp", "whatsapp con X", "qué me escribió X por whatsapp",
  "borrador de whatsapp para X".
---

# desk-whatsapp — WhatsApp fresh-first (read + draft)

**What this does:** answer "what's the state of this WhatsApp chat" with an honest freshness
check — including reporting when the capture stream itself is stale or down — then
read whitelist/memory state and optionally produce a copy-ready draft. **Never sends.**

Doctrine: `rules/skills-contract.md` · `rules/extractor-ops.md` § desk-whatsapp

## Instance setup

```bash
eval "$(secretary env)"
```

## Inputs

| Field | Values |
|-------|--------|
| `intent` | `fresh` (default) \| `recall` \| `draft` |
| `contact_or_chat` | Name, JID, or chat file slug (e.g. `roger-hidalgo`) |

## Loop fresh-first

### Step 0 — Fresh (required)

```bash
secretary fresh whatsapp --format json
# main: extractors/whatsapp/state.md + last merge; auto_pr: open whatsapp/auto-* PRs; fuente_viva: capture health
```

**Read `state.md` for stream health before anything else** — as of the last known state
(2026-07-02) the Baileys `auth/` session directory is **absent from the instance**, meaning
**no live capture is happening**. If `fuente_viva` / `state.md` still shows this, say so
plainly instead of implying fresh data exists: *"stream paused since ~2026-05-20, no new
messages captured — this is memory/inbox as of last capture, not live."*

### Step 0b — Whitelist check

```bash
git -C "$SECRETARY_INSTANCE" show origin/main:extractors/whatsapp/policy.md | head -80
```

Only whitelisted chats get processed memos; everything else lands in `inbox/chats/` unprocessed. If `contact_or_chat` isn't on the whitelist, say so — the answer will be raw inbox at best, not a memo.

### Step 0c — Memory/inbox read

```bash
secretary config path whatsapp.memory
secretary config path whatsapp.inbox
git -C "$SECRETARY_INSTANCE" show origin/main:extractors/whatsapp/memory/<slug>.md 2>/dev/null | tail -40
ls "$(secretary config path whatsapp.inbox)/chats/" 2>/dev/null | grep -i "<slug>"
```

Read unmerged proposals if `auto_pr` non-empty (same pattern as `desk-mail`/`desk-meeting`):

```bash
git -C "$SECRETARY_INSTANCE" show origin/<branch>:extractors/whatsapp/memory/<slug>.md
```

### Step 1 — Recall

`desk-recall` on the contact/topic. Mark any evidence as stale-since-2026-05-20 if the stream is still down — this is a stronger caveat than the usual `⏳ tentativo (PR #N)` marker, since it's not "pending merge" but "pending capture at all".

### Step 2 — Action (`intent=draft`)

1. If owner wants to message someone → produce copy-ready draft (optionally via `desk-compose` for relational context).
2. Apply the `GLADoS:` prefix rule only for Andrés Pereyra (see `feedback_whatsapp_glados_prefix.md`); no prefix otherwise.
3. **Never send** — WhatsApp send is UI-only and always requires explicit owner action.
4. If a new contact appears who isn't whitelisted, report it as "contacto nuevo detectado" per policy — don't add to whitelist unilaterally.

## Guardrails

- **Stream health first.** Don't answer a WhatsApp question as if data is current without checking `state.md`/`fresh whatsapp` — the known failure mode here isn't "PR unmerged," it's "nothing captured in weeks."
- Non-whitelisted chats: report their existence from `inbox/chats/` if asked, but don't fabricate a processed memo that doesn't exist.
- Drafts are copy-ready text for the owner to paste/send manually or via WhatsApp Web — this skill has no send capability by design. Paste-ready text follows `canon/rules/skills/skills-contract.md` § Output templates: one fenced ```text block per piece, no nested fences.

## Integration

| Skill / routine | Role |
|------------------|------|
| `desk-recall` | Step 1; delegates Paso 0 here for WhatsApp freshness questions |
| `desk-compose` | Relational drafts once context is fresh |
| `whatsapp-monitor` | Batch capture routine (currently paused — this skill surfaces that, doesn't fix it) |
| `secretary fresh whatsapp` | Atomic step 0 (main, auto-pr, stream health) |

Doctrine: `rules/extractor-ops.md` · Spec: `_diseño/specs/L3-captura/010-extractor-skills/spec.md` § desk-whatsapp
