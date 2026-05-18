# secretary-core

Engine for the **secretary** personal-assistant system: extraction, transformation/loading, and dispatch of personal information across multiple channels (mail, WhatsApp, meetings) into a structured wiki and actionable handovers.

> ⚠️ This repo currently mixes generic engine code with templates that may still reference the original author's context. It will be made public once a full scrub for privacy is complete.

## Architecture

See [`architecture/`](./architecture/) for the live system diagrams (Mermaid). Open `architecture/index.html` through a local HTTP server to navigate between levels.

```
secretary-core/
├── architecture/    # Live system diagrams (DFD + flowcharts + ER if added)
├── mail/            # Email processing engine + policy/settings templates
├── whatsapp/        # WhatsApp processing engine + policy template
├── meetings/        # Meeting transcript processing (Tactiq + Calendar matching)
├── wiki/            # Static-site generator: build, serve, sync-comments, worker
└── README.md
```

## How it connects to an instance

`secretary-core` is the engine. Your **instance** (private data, configurations, real policies, memory, articles) lives in a separate repository.

The instance points to the core via environment variable:

```bash
export SECRETARY_CORE=~/Cowork/secretary-core
export SECRETARY_INSTANCE=~/Cowork/secretary
```

Core scripts read paths from `$SECRETARY_INSTANCE` rather than hard-coding locations.

## Status

- [x] Architecture diagrams (DFD L1 + flowcharts M1, M2, M3)
- [ ] Mail engine: scrub policy/settings templates of private references
- [ ] WhatsApp engine: extract from `src/` into reusable shape
- [ ] Meetings engine: extract from instance into reusable shape
- [ ] Wiki engine: confirm assets/templates are generic
- [ ] CI: lint, basic tests
- [ ] Documentation: setup guide
