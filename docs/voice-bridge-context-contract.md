# Voice bridge context file: contract v1 (draft)

Status: contract v1.
The producer (a `secretary` subcommand) writes this file. The bridge only reads it. The bridge does not know secretary, its skills or its prompts; it knows only this contract.

## File

One UTF-8 JSON file at a path the bridge is configured with. The bridge feature is off until the path is set.
The producer writes atomically: write `<path>.tmp`, then rename. The bridge never sees a partial file.

```json
{
  "version": 1,
  "generated_at": "2026-11-19T08:00:00-05:00",
  "generator": "secretary 0.0.0",
  "items": [
    {
      "id": "c-3f2a91",
      "category": "commitment",
      "text": "Send the revised proposal to the client by Friday.",
      "date": "2026-11-21"
    }
  ]
}
```

## Fields

| field | type | rule |
|-------|------|------|
| `version` | integer | Required. This document is `1`. The bridge rejects unknown versions and shows state `error`. |
| `generated_at` | string, ISO 8601 with offset | Required. The bridge computes age from it. |
| `generator` | string | Optional. Shown in the preview for debugging. |
| `items` | array | Required. Ordered by relevance, most relevant first. Max 40 entries. |
| `items[].id` | string | Required. Stable for the same underlying fact across runs, so a checkbox exclusion survives a refresh. Unique in the file. |
| `items[].category` | string | Required. One of `commitment`, `brief`, `session`, `repo`, `mail`, `wiki`. The bridge maps unknown values to `other`. |
| `items[].text` | string | Required. One short plain-text sentence, max 200 characters, no newlines, no markdown. |
| `items[].date` | string, `YYYY-MM-DD` | Optional. Due date or event date. |

Default sources (producer side): `commitment`, `brief`, `session`. `repo`, `mail` and `wiki` appear only if the user turns them on.

## Repo source (`repo`, opt-in)

One item per git repo: current branch, uncommitted changes, ahead/behind of the upstream, and open pull requests when `gh` is available (a missing or failing `gh` yields no PR info, silently). Example: `api: branch feat/x, 3 uncommitted, ahead 1, 2 open PRs (PR 7 Fix login; PR 9 Bump deps)`.

- Enabled only with `--sources ...,repo`. The default sources do not change.
- The repo list is producer-side configuration, never in the bridge: `--repo-root <dir>` (repeatable), else `voice_context.repo_roots` in the instance config, else `~/Dev` and `~/Cowork`. Only the direct subfolders of each root that are git repos are inspected (at most 30).
- At most 6 items, 160 characters each. Repos with open PRs come first, then those with uncommitted or unpushed work, then the rest by latest commit. Items sort after `session`, so the 1,600-character cap drops them first.
- Ahead/behind reflect the last fetch; the producer does not fetch.
- Item `id` is stable per `<root name>/<repo name>`. No `date`.

## Size cap

- The producer targets at most ~400 tokens (~1,600 characters) of `text` in total, and selects the most relevant items to fit.
- The bridge enforces the cap too: it keeps items in file order until the sum of `text` lengths plus category labels reaches 1,600 characters, and drops the rest. The preview shows which items were dropped.

## Bridge behavior (summary, for the n6 spec)

- Reads the file on connect and on Refresh. Never calls the producer on connect.
- Status indicator states: `none` (no file), `running` (Refresh in progress), `pending` (new file not approved), `approved` (with age), `stale` (age over a configurable threshold, default 36 h), `error` (unreadable, bad version, producer failed or timed out).
- Preview: one checkbox per item, all checked by default; actions Approve and Discard. The approved text uses only checked items. Approval state and exclusions live on the bridge side, not in this file.
- Until a new file is approved, the last approved summary stays in use.
- An approved summary applies at the next Gemini session open (connect, Apply or restart).
- Injection: section "About the user (as of <generated_at date>)" after the name note, with the note that it may be out of date. Gemini uses it only when asked or when relevant, and never reads it out in full.
- Refresh runs a configurable command with a timeout. Its output goes to the log.

## Open questions for the owner

1. `generator`: keep, or drop to avoid leaking tool names into the UI?
2. Per-item `text` max 200 characters: enough for session lines (project, last request, state)?
3. Language of `text`: follow the user's language setting (from the language plan), or always the user's primary language? Proposal: the producer writes in the user's primary language; the bridge does not translate.
