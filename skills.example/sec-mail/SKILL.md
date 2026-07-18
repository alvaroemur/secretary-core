---
name: sec-mail
description: >-
  Read Gmail fresh and create in-thread drafts via gog — account, recipients (To/Cc/Bcc),
  signature, and mail policy. Use when a session needs live mail context or a reply draft,
  not only sec-recall. Triggers: "/sec-mail", "read my mail", "draft to reply", "gmail today".
---

# sec-mail — mail fresh-first (read + draft)

**Mission:** ensure Gmail context **fresher than `state.md`**, and create in-thread drafts with correct
account, recipients, and signature. **Never sends.**

Doctrine: `rules/skills-contract.md`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
WORK_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.inspiro // .accounts.work // empty')
```

## Guardrails

- **NEVER** `--add TRASH`. Archive with `--remove INBOX` only when owner or `revision-correo` explicitly asks.
- **NEVER** `gog gmail send` or UI send without explicit OK (🚧 gate).
- In-thread drafts: **always** `--reply-to-message-id <messageId>`.
- Prefer `gog … --plain` for sweeps; `--json`/`--full` only for the thread you will reply to.
- **MD mirror location:** per `operational/sistemas-ordenamiento.md` §6.1 — project deliverables in Cowork, **not** `extractors/mail/drafts/`.
- **Persist before copy-ready:** write the MD file before showing draft text in chat (§7).

## Policies (read before classify or persist)

| Policy | Config key |
|--------|------------|
| Inbox classification | `mail.policy` |
| Signature, tone, settings | `mail.settings` |
| MD mirror location, naming, persistence | `operational.sistemas_ordenamiento` |
| Routine triage mirror | `mail.drafts` |
| Borrador template | `templates/borrador-correo-proyecto` (under `paths.templates`) |

```bash
secretary config path mail.policy
secretary config path mail.settings
secretary config path operational.sistemas_ordenamiento

git -C "$SECRETARY_INSTANCE" show origin/main:extractors/mail/policy.md | head -80
git -C "$SECRETARY_INSTANCE" show origin/main:extractors/mail/settings.md
git -C "$SECRETARY_INSTANCE" show origin/main:operational/sistemas-ordenamiento.md
```

Skills vs policies: `operational/skills-vs-operational.md`.

## Inputs (declarative)

| Field | Values |
|-------|--------|
| `intent` | `read` \| `search` \| `thread` \| `draft` |
| `account` | `personal` \| `inspiro` → resolve from `.accounts` |
| `query` | Gmail search (e.g. `from:contact newer_than:3d`) |
| `thread_id` | For `thread` / `draft` |
| `to` / `cc` / `bcc` | Lists for `draft` |
| `subject` | Subject (`Re: …` if reply) |
| `body` | Body without signature |
| `reply_to_message_id` | From `thread get --plain` — required for reply |
| `tone` | `warm` (default) \| `formal` — rules in `mail.settings` |

Verify work account:

```bash
[ -n "$WORK_ACCOUNT" ] && gog gmail search 'newer_than:1d' --account="$WORK_ACCOUNT" --max 1 --plain --no-input 2>/dev/null && echo work=ok || echo work=off
```

## Loop fresh-first

### Step 0 — Fresh (required)

```bash
secretary fresh mail
secretary fresh mail --format json
secretary fresh mail --local

git -C "$SECRETARY_INSTANCE" show origin/main:extractors/mail/state.md 2>/dev/null | head -25
```

### Step 0b — Policies (if `intent=draft` or classification)

Load `mail.policy`, `mail.settings`, `operational.sistemas_ordenamiento` (§6.1 borradores, §7 persistencia).

### Step 1 — Recall

If person/org involved → `sec-recall`. For recent relational draft (<48h meeting) → consider
`sec-compose` (`channel: correo`).

### Step 2 — Action

Per `intent` below. Report with source `gog:<threadId>` or `state.md:date`.

## Canonical commands

### `intent=read` / `search`

```bash
ACC="$PERSONAL_ACCOUNT"   # or WORK_ACCOUNT per intent

gog gmail search 'newer_than:1d -in:chats' --max 50 --plain --no-input --account="$ACC"
gog gmail search 'in:inbox is:unread' --max 30 --plain --no-input --account="$ACC"
gog gmail search 'in:sent newer_than:7d' --max 30 --plain --no-input --account="$ACC"
gog gmail search '<query>' --max 20 --plain --no-input --account="$ACC"
```

### `intent=thread`

```bash
gog gmail thread get <threadId> --plain --no-input --account="$ACC"
gog gmail thread get <threadId> --plain --full --no-input --account="$ACC"
```

Extract `Message N/N: <messageId>` from `--plain` output for drafts.

### `intent=draft`

**Defaults** (unless owner requests otherwise): plain Gmail-style text, no elaborate HTML.

1. Get `messageId` of the message being replied to.
2. Apply signature rules from `mail.settings`.
3. Convert MD → Gmail body (table below).
4. **Typo review (mandatory)** — re-read full body before `gog gmail drafts create`; fix typos,
   broken words, dates, double spaces. Fix source `.md` in Cowork if applicable.
5. Create Gmail draft:

```bash
cat > /tmp/draft-mail.txt <<'EOF'
<converted body>
EOF

gog gmail drafts create \
  --to "dest@example.com" \
  --cc "cc@example.com" \
  --subject "Re: subject" \
  --body-file /tmp/draft-mail.txt \
  --reply-to-message-id <messageId> \
  --account "$ACC" \
  --json --no-input
```

6. **MD mirror:** per `sistemas-ordenamiento.md` §6.1 — naming `borrador-correo-<slug>-YYYY-MM-DD.md`,
   YAML frontmatter (`templates/borrador-correo-proyecto.md`); Cowork `borradores/` or contact subfolder;
   `mail.drafts` for routine triage only. Persist file **before** copy-ready in chat (§7).

#### Draft style (plain-first)

- Default: `--body-file` plain text. Agent converts Markdown before writing the file.
- Emphasis: strip `**bold**` for plain (or `<b>` only with `--body-html` on explicit request).
- No headers, code blocks, tables, or colors unless rich format requested.
- Rich HTML only on owner request → minimal `--body-html`.

#### MD → Gmail body

| MD source | Gmail file content |
|-----------|---------------------|
| `**text**` | `text` (plain) or `<b>text</b>` (html only) |
| `- item` | `- item` or `• item` |
| Paragraphs | Blank line between |
| `## title` | Prose line — no MD syntax |
| `` `code` `` | Plain or omit — no blocks unless requested |

## Signature

Canonical source: `mail.settings` (`extractors/mail/settings.md`). Read before building body.

Decision summary (detail in settings file):

1. No signature in source → add default from settings.
2. Minimal close (name only) → extend with default signature.
3. Explicit multi-line block → respect as-is.
4. Formal only if `tone=formal` or thread requires it.

## Report

Header: `📬 **Mail — <intent>** · account <personal|inspiro>`. Compact table or list (from, subject,
age, action). For drafts: copy-ready body + note it lives in Gmail Drafts, not sent. Include **MD
mirror path** if persisted. Line: **Typos corrected:** … or **No typos detected.**

If responding to a brief item:

> Already sent? `secretary status "✅" "<ref>" "<note>"`

## CLI integration

| Tool | Use |
|------|-----|
| `secretary fresh mail` | Step 0 |
| `secretary config path <key>` | Policies |
| `secretary config show` | Accounts, instance root |
| `sec-recall` | Step 1 |
| `sec-compose` | Relational draft → handoff here with `intent=draft` |

Doctrine: `rules/extractor-ops.md` · Spec: `_diseño/specs/010-extractor-skills/spec.md`
