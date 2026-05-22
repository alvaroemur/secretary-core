# Processing policy — WhatsApp

> Example template. Replace `<...>` placeholders with the user's actual
> chats, groups, and contacts.

## General rule (strict whitelist)

**Only chats explicitly listed in the whitelist (Approved) are processed.**
All other WhatsApp chats (potentially hundreds) are captured in `inbox/chats/` but NO automatic memos are generated.

This is because WhatsApp contains a mix of personal, professional, and casual conversations. Once a chat is identified as worth processing, it gets added to the whitelist.

## Exceptions

### New contacts
If a new contact appears (first time writing) and is NOT on the whitelist, it is noted in `estado.md` as "New contact detected" so the user can decide whether to add them.

### Pending approval
If a whitelisted chat was inactive for >30 days and reactivates, it continues to be processed (already approved).

## Whitelist — Approved

> Replace the following examples with the user's actual chats.
> Keep a `kebab-case` slug per chat for naming the associated memo file.

### Project groups (always process — actionable info)
- `<PROJECT_GROUP_1>` (`<project-group-1>.md`)
- `<PROJECT_GROUP_2>` (`<project-group-2>.md`)
- `<PROJECT_GROUP_3>` (`<project-group-3>.md`) — operations channel; deliveries with real deadlines

### Radar groups (monitor for news)
- `<RADAR_GROUP_1>` (`<radar-group-1>.md`)
- `<RADAR_GROUP_2>` (`<radar-group-2>.md`)
- `<RADAR_GROUP_3>` (`<radar-group-3>.md`) — calls for proposals, org searches, relevant ecosystem
- `<RADAR_GROUP_4>` (`<radar-group-4>.md`) — Demo Days, ecosystem events

### People (1-on-1)
- `<CONTACT_NAME_1>` (`<contact-1>.md`)
- `<CONTACT_NAME_2>` — `<PHONE>` — no chat yet
- `<CONTACT_NAME_3>` (`<contact-3>.md`)
- `<CONTACT_NAME_4>` (`<contact-4>.md`) — JID `<JID>@lid` (privacy variant of the number already in glossary; confirm identity)
- `<CONTACT_NAME_5>` (`<contact-5>.md`) — lead via `<REFERRER_NAME>` (`<JID>@lid`)
- `<CONTACT_NAME_6>` (`<contact-6>.md`) — close relationship; important context about group dynamics

<!-- TODO: fill in with the user's actual contacts -->

## Explicitly blocked
<!-- JIDs/names that must never be processed or appear in the triage report -->
(none for now)

## Triage for chats outside the whitelist

The routine does NOT generate memos for chats outside the whitelist, but it DOES **triage** their activity and lists candidates in `estado.md` for the user to decide.

### Triage classification rules (sub-agent "triage")

- **high_signal** → appears in `estado.md` as "whitelist candidate". Meets >= 1 of:
  - >5 new messages with actual text
  - Mentions >= 1 existing entity in wiki (person, org, topic)
  - New contact (first time writing in a 1-on-1 chat)
  - Message with keyword: "deadline", "call for proposals", "grant", "proposal", "meeting", "invoice", "payment", URLs to docs/forms

- **medium_signal** → appears in `estado.md` as "minor activity" (1-liner). 1-3 messages with minimal text content (scheduling, "ok", "thanks")

- **low_signal** → appears only in `estado.md` stats. Media-only without caption, emoji-only/reactions

### How to adjust the routine

- **To add a chat to deep processing**: add slug/JID to the Approved section (in the appropriate category)
- **To permanently silence a chat**: add to Blocked
- **To stop a new contact from being reported as new again**: add to `memory/_glosario.md` with their aliases

## Operational notes

- **Processing type by category**:
  - *Projects*: extract actions, deadlines, decisions, evidence for wiki
  - *Radar*: extract news, opportunities, interesting links; no forced actions
  - *People*: extract commitments, relevant personal/professional info for their wiki profiles
- **Messages with unknown sender (`?`)**: in historical dumps, some group messages lack a `participant` field. These messages are included in **topic** analysis (what was discussed) but are **omitted from person analysis** (not attributed to anyone). In memos they appear without author or as "unidentified sender".
- **Live messages (captured by the fetch routine)**: carry the correct `participant`, 100% reliable attribution.
