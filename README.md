# secretary

An AI-powered personal assistant that processes your email, WhatsApp, meetings, and Google Drive — then consolidates everything into a personal wiki. Runs autonomously via scheduled routines that report back through Pull Requests.

**This repo is the engine.** Your private data (policies, contacts, wiki articles, chat history) lives in a separate instance repository that you control.

## Quick start — paste this into your AI coding agent

Copy the prompt below into [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Cursor, Windsurf, Codex, or any AI coding assistant that can run shell commands and edit files:

```
Clone https://github.com/alvaroemur/secretary-core and help me set it up
as my personal assistant. Read the README.md thoroughly first — it explains
the architecture, the core/instance split, and how routines work.

Then walk me through:
1. Creating my instance repo (private, holds my data)
2. Picking which channels to activate (email, WhatsApp, meetings, Drive)
3. Adapting the routine templates in routines/ for my setup
4. Setting up the wiki and running the first build
5. Scheduling the routines to run daily

Ask me questions as you go — I'll tell you which email tool I use,
which chats matter, what my Drive looks like, and what language I prefer.
```

That's it. The agent will read the docs, ask you the right questions, and configure everything.

## How it works

```
         Email ─┐
      WhatsApp ──┤──▶ [ Extraction ]──▶ memory/ ──▶ [ Wiki sync ]──▶ wiki/
      Meetings ──┤        routines        evidence       routine       articles
  Google Drive ──┘                                                       │
                                                                         ▼
                                                            HTML dashboard
                                                          (static, self-hosted)
```

**Three-stage pipeline:**

1. **Extraction** — Scheduled routines pull data from your channels (email, WhatsApp, meetings, Drive). Each produces structured evidence in `memory/` files (people, organizations, topics, actions). Each run opens a PR as its report.

2. **Transformation** — The wiki-sync routine reads all evidence, integrates it into Markdown articles, rebuilds the static HTML, and deploys. It also merges the extraction PRs automatically (after checking for unresolved comments).

3. **Dispatch** *(planned)* — Handovers and notes pushed to external repos or systems based on actions extracted from your channels.

## Architecture

```
secretary-core/          ← this repo (engine, public)
├── architecture/        # System diagrams (Mermaid DFD + flowcharts)
├── mail/                # Email policy + settings templates
├── whatsapp/            # WhatsApp engine (Baileys) + policy template
├── meetings/            # Meeting transcript processing
├── wiki/                # Static-site generator (Python, zero deps)
│   ├── build/           #   article → HTML builder
│   ├── assets/          #   CSS + JS for the viewer
│   ├── serve.py         #   local dev server
│   └── worker/          #   Cloudflare Pages worker (optional)
├── routines/            # Routine templates (the scheduled AI agents)
│   ├── mail-review.md
│   ├── wiki-sync.md
│   ├── meetings-processor.md
│   ├── whatsapp-monitor.md
│   └── drive-crawler.md
└── README.md
```

Open `architecture/index.html` via a local server to browse the system diagrams interactively.

## Core / instance split

The engine (this repo) contains no personal data. Your **instance** is a separate private repo with your actual policies, contacts, wiki articles, memory files, and chat history.

```
my-secretary/                ← your instance (private)
├── mail/
│   ├── policy.md            # your real classification rules
│   ├── settings.md          # your tone, corrections, preferences
│   ├── estado.md            # rolling state from last run
│   └── memory/              # daily memos + consolidated entities
├── whatsapp/
│   ├── policy.md            # your whitelist + blocked chats
│   ├── estado.md
│   ├── memory/
│   ├── inbox/               # captured messages (gitignored)
│   ├── auth/                # Baileys session (gitignored)
│   └── resumenes/           # per-chat summaries
├── meetings/
│   ├── memory/
│   └── resumenes/
├── drive/
│   ├── estado.md
│   └── memory/
├── wiki/
│   └── articulos/           # your wiki articles (Markdown)
└── .secretary.yml           # paths + env config
```

Connect them via environment variables:

```bash
export SECRETARY_CORE=~/Dev/secretary-core
export SECRETARY_INSTANCE=~/path/to/my-secretary
```

## Routines

Each file in `routines/` is a complete, self-contained prompt for an AI agent that runs on a schedule. They are designed for [Claude Code scheduled tasks](https://docs.anthropic.com/en/docs/claude-code) but work with any AI coding agent that can:

- Read and write files
- Run shell commands (git, CLI tools)
- Call APIs (Gmail, Google Drive, Calendar)
- Spawn sub-agents for parallel work

### The five routines

| Routine | Schedule | What it does |
|---------|----------|-------------|
| **mail-review** | Daily AM | Summarizes email, creates draft replies, cleans inbox, tracks follow-ups |
| **meetings-processor** | Daily PM | Processes new meeting transcriptions, extracts actions and entities |
| **whatsapp-monitor** | Daily PM | Processes approved chats, triages the rest, surfaces candidates |
| **drive-crawler** | Daily PM | Indexes new/modified files, proposes Drive organization improvements |
| **wiki-sync** | Daily late PM | Merges extractor PRs, integrates all evidence into wiki, rebuilds HTML |

### How routines report

Every routine works in an **isolated git worktree** (never touches your working copy), commits its changes, and opens a **Pull Request** that serves as both the report and the version-controlled diff. You read the PR on GitHub, review what the agent did, and merge.

### Routine conventions

All routines follow the same patterns:

- **Worktree isolation** — creates a temporary branch from `origin/main`, works there, opens PR
- **Policy files** — each channel has a `policy.md` that the user maintains (classification rules, whitelists, blocked senders)
- **Estado (state) files** — rolling state that carries context between runs
- **Memory consolidation** — evidence is written to `memory/` files (personas.md, organizaciones.md, acciones.md) that wiki-sync consumes
- **Anti-hallucination gates** — new entities default to `pending_wiki: false` until the user confirms; no guessing surnames or inventing data
- **Append-only evidence** — extractors only add to memory files; wiki-sync is the only one that cleans up after integration

## Wiki

The wiki is a static site generator with zero external dependencies (Python standard library only). It turns Markdown articles with YAML frontmatter into a browsable HTML dashboard with search, categories, and wikilinks.

Article format:
```markdown
---
title: Article Title
type: person           # person | organization | topic | profile
infobox:
  Field: Value
categories: [people]
last_updated: 2025-01-15
sources:
  - type: email
    ref: <message-id>
  - type: meeting
    ref: <drive-id>
---

## Section
Content with [[wikilinks]] to other articles.
```

Build: `SECRETARY_DATA="$SECRETARY_INSTANCE" python3 wiki/build/build.py`

## Prerequisites

The routines are modular — activate only the channels you use:

| Channel | Requirements |
|---------|-------------|
| **Email** | Gmail account + CLI tool with search/label/archive/draft commands (e.g. [gog](https://github.com/pterm/gog), or Gmail MCP tools) |
| **WhatsApp** | Node.js + the Baileys engine in `whatsapp/src/` (requires QR auth once) |
| **Meetings** | Meeting transcription service that saves to Google Drive (e.g. Tactiq, Otter) |
| **Drive** | Google Drive desktop app (filesystem mount) and/or Drive API access |
| **Wiki** | Python 3.8+ (standard library only) |
| **Calendar** | Google Calendar API access (for meeting enrichment) |

For Claude Code scheduled tasks, you also need the [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated.

## Language

The engine and all templates are in **English**. Your instance (policies, wiki articles, routine prompts) can be in any language — just tell the AI agent your preference during setup and it will adapt everything.

## Getting started manually

If you prefer to set things up yourself instead of using the AI prompt above:

1. **Fork/clone this repo** as your engine
2. **Create your instance repo** (private) following the structure above
3. **Copy and adapt** the template files:
   - `mail/policy.example.md` → `your-instance/mail/policy.md`
   - `mail/settings.example.md` → `your-instance/mail/settings.md`
   - `whatsapp/policy.example.md` → `your-instance/whatsapp/policy.md`
4. **Adapt routine templates** from `routines/` — replace placeholders with your paths, tools, and preferences
5. **Create your first wiki article** about yourself in `wiki/articulos/your-name.md`
6. **Run the wiki build** to verify: `SECRETARY_DATA="$INSTANCE" python3 wiki/build/build.py`
7. **Schedule the routines** in your AI coding agent

## Contributing

This is a personal-assistant framework that grew out of real daily use. Contributions welcome — especially:

- New channel integrations (Slack, Telegram, Notion, etc.)
- Routine improvements and new patterns
- Wiki builder enhancements
- Documentation and examples

## License

MIT
