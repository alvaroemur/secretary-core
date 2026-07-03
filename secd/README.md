# secd — Secretary local daemon

A tiny loopback-only HTTP server that exposes Secretary's context to a browser
extension ([Axon](https://github.com/alvaroemur/axon)) while you read a WhatsApp
conversation, and accepts signals back into Secretary. It is the bridge defined
in **Feature 007 — Axon × Secretary** (RFC in the instance repo at
`_design/specs/007-axon-secretary-relay/spec.md`).

> **Status: MVP (P1 + P2).** Read side is real and tested against a live instance.
> The relay now runs a **real LLM** when one is configured (OpenAI by default;
> provider-swappable to Claude), and falls back to a deterministic stub otherwise.
> Zero-dependency ESM JavaScript so it runs with a bare `node` (to be ported to TS).

## Relay LLM config

The relay reads credentials from, in order:

1. `<instance>/.secd/llm.json` → `{ "provider": "openai"|"anthropic", "apiKey": "…", "model": "…" }` (gitignored)
2. env `OPENAI_API_KEY` (→ `gpt-4o-mini`) or `ANTHROPIC_API_KEY` (→ Claude Haiku)

With nothing configured, `/relay` returns the deterministic stub. `GET /health`
reports `relay: { configured, provider, model }`.

## Run

```bash
export SECRETARY_INSTANCE=~/.secretary   # your private instance dir
node secd/server.mjs                      # listens on http://127.0.0.1:8910
```

On first run it mints an auth token and prints it (also stored at
`<instance>/.secd/token`, gitignored). Paste that token into Axon → options →
Secretary bridge.

```bash
npm test     # offline checks against $SECRETARY_INSTANCE (resolver, context, objectives)
```

## Security model

- Binds **127.0.0.1 only** — never reachable from the network.
- Every endpoint **except `/health`** requires `Authorization: Bearer <token>`.
- CORS allows `chrome-extension://…` and localhost origins so Axon can call it.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | no | reachability + entity count (proves MV3 ↔ localhost) |
| GET | `/context?name=&chatId=` | yes | **context card**: entity + summary + orgs + open actions + objectives + voice rules |
| GET | `/objectives?entity=&estado=&nivel=` | yes | query the objectives store |
| POST | `/objectives` | yes | create/update an objective (daemon mints id/date) |
| GET | `/recall?q=` | yes | free-text search over wiki articles |
| POST | `/relay` | yes | LLM-backed (or stub) intention + objective + reply suggestions |
| POST | `/signal` | yes | record a durable fact (scaffold → `whatsapp/memory/relay-signals.md`) |
| POST | `/capture` | yes | persist a scraped conversation (scaffold → `whatsapp/inbox/axon/`) |
| GET | `/modules` | yes | list extractors + loops with contract metadata (spec 015) |
| GET | `/modules/:id` | yes | full contract + computed health |
| GET | `/modules/:id/health` | yes | `{ freshness_ok, health, criteria[] }` |
| GET | `/modules/:id/contract` | yes | raw `contract.yaml` as JSON |
| PUT | `/modules/:id/contract` | yes | shallow-merge admin update (human gate) |

## How it resolves a chat to an entity

The reliable signal from a DOM scrape is the contact's display name, so
[`lib/resolver.mjs`](lib/resolver.mjs) matches the normalized name against wiki
person/organization titles and slugs (jid is a secondary hint). Matches are
conservative: clearly-ahead → `matched`; close calls → `ambiguous` (returns
candidates); nothing → `unknown` (card flags `pendiente_wiki`).

## Layout

```
secd/
  server.mjs          HTTP server, routing, auth, CORS
  lib/
    config.mjs        instance path (SECRETARY_INSTANCE), port, token
    memory.mjs        wiki/articles, open actions, recall, frontmatter parse
    resolver.mjs      chat name/alias → wiki entity (cached index)
    context.mjs       assemble the context card
    objectives.mjs    read/write the objetivos/ store
    relay.mjs         deterministic stub (LLM goes here later)
    modules.mjs       module contracts via `secretary modules` CLI (spec 015)
  test/run.mjs        offline checks
```

## Not done yet (see RFC)

- Relay is live on OpenAI; switching to Claude is a config change (`provider: "anthropic"`).
- `secd` lifecycle (login item / Secretary runtime) — currently run by hand.
- `/capture` and `/signal` are scaffolds; full wiki-lazy integration is P3.
- Tighter objective↔entity grounding (e.g. relationship objectives linked to the
  people in an org, not just the org) so replies cite the right numbers.
