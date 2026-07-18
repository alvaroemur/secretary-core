# secretary

An AI-powered personal assistant framework that processes your email, WhatsApp, meetings, and Google Drive — then consolidates everything into a personal wiki. Runs autonomously via scheduled routines that report back through Pull Requests.

**This repo is the engine.** Your private data (policies, contacts, wiki articles, chat history) lives in a separate private instance repository that you control.

## Quick start — paste this into your AI coding agent

Copy the prompt below into [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Cursor, Windsurf, or any AI coding assistant that can run shell commands and edit files:

```
Clone https://github.com/yourusername/secretary-core and help me set it up
as my personal assistant. Read the README.md thoroughly first — it explains
the architecture, the core/instance split, and how routines work.

Then walk me through:
1. Creating my instance repo (private, holds my data)
2. Picking which channels to activate (email, WhatsApp, meetings, Drive)
3. Adapting the routine templates in playbooks.example/ for my setup
4. Setting up the wiki and running the first build using the secretary CLI
5. Scheduling the routines to run daily using LaunchAgents or your scheduler

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
secretary-core/            ← this repo (engine, public)
├── architecture/          # System diagrams (Mermaid DFD + flowcharts)
├── cli/                   # CLI documentation and scripts
├── mail/                  # Email settings templates
├── whatsapp/              # WhatsApp engine (Baileys) + policy template
├── wiki/                  # Static-site generator (Python, zero deps)
│   ├── build/             #   article → HTML builder
│   ├── assets/            #   CSS + JS for the viewer
│   └── serve.py           #   local dev server
├── secretary/             # Main Python CLI engine (status, validate, recall)
│   └── routines/          #   Routines engine logic, LaunchAgents setup wizard
├── secd/                  # Local daemon server (bridge to Axon browser extension)
├── playbooks.example/     # Anonymized templates for scheduled routine prompts
└── skills.example/        # Anonymized templates for agentic assistant skills
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

## CLI (`secretary`) & Daemon (`secd`)

The engine provides a python-based CLI tool and a local daemon:

- **CLI (`secretary`)**: Offers atomic, scriptable, non-LLM operations. Commands include:
  - `secretary config` — Instance config and path resolution.
  - `secretary status` — Persist progress on today's briefing.
  - `secretary validate` — Run instance CI validators.
  - `secretary recall` — Deterministic memory search.
  - `secretary wiki build` — Safe legacy-to-instance wiki builds.
  - `secretary routines setup` — Interactive wizard to schedule LaunchAgents.
- **Daemon (`secd`)**: A loopback-only Node.js HTTP server. It serves as a bridge to browser extensions (like Axon), exposing context cards, objectives, modules, and accepting signals back into Secretary.

## Routines

Each folder in `playbooks.example/` contains structured prompts/instructions for scheduled tasks. They are designed for [Claude Code scheduled tasks](https://docs.anthropic.com/en/docs/claude-code) or cron schedules:

| Routine | Schedule | What it does |
|---------|----------|-------------|
| **revision-correo** | Daily AM | Summarizes email, creates draft replies, cleans inbox, tracks follow-ups |
| **reuniones-update** | Daily PM | Processes new meeting transcriptions, extracts actions and entities |
| **whatsapp-monitor** | Daily PM | Processes approved chats, triages the rest, surfaces candidates |
| **drive-crawler** | Daily PM | Indexes new/modified files, proposes Drive organization improvements |
| **wiki-update** | Daily late PM | Merges extractor PRs, integrates all evidence into wiki, rebuilds HTML |

### How routines report

Every routine works in an **isolated git worktree** (never touches your working copy), commits its changes, and opens a **Pull Request** that serves as both the report and the version-controlled diff. You read the PR on GitHub, review what the agent did, and merge.

## Wiki

The wiki is a static site generator with zero external dependencies (Python standard library only). It turns Markdown articles with YAML frontmatter into a browsable HTML dashboard with search, categories, and wikilinks.

Build via CLI: `secretary wiki build`

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

## Language

The engine and all templates are in **English**. Your instance (policies, wiki articles, routine prompts) can be in any language — just tell the AI agent your preference during setup and it will adapt everything.

## Getting started manually

If you prefer to set things up yourself instead of using the AI prompt above:

1. **Fork/clone this repo** as your engine.
2. **Create your instance repo** (private) following the structure above.
3. **Copy and adapt** the template files:
   - `mail/policy.example.md` → `your-instance/mail/policy.md`
   - `mail/settings.example.md` → `your-instance/mail/settings.md`
   - `whatsapp/policy.example.md` → `your-instance/whatsapp/policy.md`
4. **Copy routine templates** from `playbooks.example/` into your local `playbooks/` folder and adapt them (replace placeholders with your paths, tools, and preferences).
5. **Create your first wiki article** about yourself in `wiki/articulos/your-name.md`.
6. **Run the wiki build** via the CLI: `SECRETARY_INSTANCE="$INSTANCE" secretary wiki build`
7. **Schedule the routines** using the setup wizard: `secretary routines setup`

## License

MIT
